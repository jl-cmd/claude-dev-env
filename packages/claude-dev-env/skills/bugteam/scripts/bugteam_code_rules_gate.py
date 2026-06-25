from __future__ import annotations

import argparse
import ast
import importlib.util
import re
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

ValidateContentCallable = Callable[..., list[str]]

from bugteam_scripts_constants.bugteam_code_rules_gate_constants import (
    ALL_CODE_FILE_EXTENSIONS,
    ALL_COLUMN_MAGIC_FALSE_VALUES,
    ALL_GIT_DIFF_CACHED_ARGS,
    BUGTEAM_CODE_RULES_GATE_PREFIX,
    EXIT_CODE_ENFORCER_MISSING,
    FUNCTION_LENGTH_DEFINITION_LINE_GROUP_INDEX,
    FUNCTION_LENGTH_SPAN_GROUP_INDEX,
    FUNCTION_LENGTH_VIOLATION_PATTERN,
    BANNED_NOUN_DEFINITION_LINE_GROUP_INDEX,
    BANNED_NOUN_SPAN_GROUP_INDEX,
    BANNED_NOUN_VIOLATION_PATTERN,
    INLINE_DUPLICATE_BODY_ENCLOSING_LINE_GROUP_INDEX,
    INLINE_DUPLICATE_BODY_ENCLOSING_SPAN_GROUP_INDEX,
    INLINE_DUPLICATE_BODY_HELPER_LINE_GROUP_INDEX,
    INLINE_DUPLICATE_BODY_HELPER_SPAN_GROUP_INDEX,
    INLINE_DUPLICATE_BODY_VIOLATION_PATTERN,
    HUNK_HEADER_RAW_PATTERN,
    ISOLATION_DEFINITION_LINE_GROUP_INDEX,
    ISOLATION_SPAN_GROUP_INDEX,
    ISOLATION_VIOLATION_PATTERN,
    MAX_VIOLATIONS_PER_CHECK,
    MAXIMUM_COLUMN_TUPLE_ELEMENT_COUNT,
    MAXIMUM_ISSUES_TO_REPORT,
    PYTHON_FILE_EXTENSION,
    VIOLATION_LINE_RAW_PATTERN,
)


def hunk_header_pattern() -> re.Pattern[str]:
    return re.compile(HUNK_HEADER_RAW_PATTERN)


def violation_line_pattern() -> re.Pattern[str]:
    return re.compile(VIOLATION_LINE_RAW_PATTERN)


def resolve_claude_dev_env_root() -> Path:
    environment_value = (Path(__file__).resolve().parents[3]).resolve()
    return environment_value


def load_validate_content() -> ValidateContentCallable:
    """Load and return the validate_content function from the CODE_RULES enforcer.

    Dynamically imports the code_rules_enforcer module by resolving its path
    relative to the current file's location. Temporarily removes the gate
    script's ``config`` from ``sys.modules`` to avoid a namespace clash with
    the enforcer's ``hooks/config/`` package.

    Not thread-safe: mutates the process-global ``sys.modules`` mapping. Call
    only from single-threaded contexts (the CLI entry point at ``main`` is
    safe; concurrent invocations from multiple threads must wrap calls in an
    external lock).

    Returns:
        The validate_content callable from the loaded enforcer module.

    Raises:
        SystemExit: When the enforcer file is missing or cannot be loaded.
    """
    package_root = resolve_claude_dev_env_root()
    enforcer_path = package_root / "hooks" / "blocking" / "code_rules_enforcer.py"
    if not enforcer_path.is_file():
        print(
            f"missing enforcer at {enforcer_path}",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_CODE_ENFORCER_MISSING)
    previously_cached_config = {}
    for each_cached_module_name in [
        each_module_key
        for each_module_key in list(sys.modules)
        if each_module_key == "config" or each_module_key.startswith("config.")
    ]:
        previously_cached_config[each_cached_module_name] = sys.modules.pop(
            each_cached_module_name
        )
    hooks_config_init = package_root / "hooks" / "config" / "__init__.py"
    if hooks_config_init.is_file():
        hooks_config_spec = importlib.util.spec_from_file_location(
            "config",
            hooks_config_init,
        )
        if hooks_config_spec is not None and hooks_config_spec.loader is not None:
            hooks_config_module = importlib.util.module_from_spec(hooks_config_spec)
            sys.modules["config"] = hooks_config_module
            hooks_config_spec.loader.exec_module(hooks_config_module)
    try:
        specification = importlib.util.spec_from_file_location(
            "code_rules_enforcer",
            enforcer_path,
        )
        if specification is None or specification.loader is None:
            print("could not load code_rules_enforcer.", file=sys.stderr)
            raise SystemExit(EXIT_CODE_ENFORCER_MISSING)
        module = importlib.util.module_from_spec(specification)
        specification.loader.exec_module(module)
        return module.validate_content
    finally:
        sys.modules.update(previously_cached_config)


def resolve_merge_base(repository_root: Path, base_reference: str) -> str:
    """Resolve the merge-base commit between HEAD and a base reference.

    Args:
        repository_root: The root directory of the git repository.
        base_reference: The git reference to compare against (e.g., origin/main).

    Returns:
        The merge-base commit hash as a string.

    Raises:
        SystemExit: When git merge-base fails.
    """
    merge_result = subprocess.run(
        ["git", "merge-base", "HEAD", base_reference],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if merge_result.returncode != 0:
        print(
            f"git merge-base HEAD {base_reference} failed:\n"
            f"{merge_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_CODE_ENFORCER_MISSING)
    return merge_result.stdout.strip()


def filter_paths_under_prefixes(
    all_file_paths: list[Path],
    repository_root: Path,
    all_prefixes: list[str],
) -> list[Path]:
    """Filter a list of file paths to keep only those under the given prefixes.

    Args:
        all_file_paths: File paths to filter.
        repository_root: The repository root for resolving relative paths.
        all_prefixes: Prefixes to match against (POSIX-style, relative to root).

    Returns:
        Filtered list of file paths whose repo-relative path starts with a prefix.
    """
    if not all_prefixes:
        return all_file_paths
    normalized_prefixes = [
        each_prefix.strip().replace("\\", "/").rstrip("/")
        for each_prefix in all_prefixes
        if each_prefix.strip()
    ]
    if not normalized_prefixes:
        return all_file_paths
    resolved_root = repository_root.resolve()
    filtered: list[Path] = []
    for each_path in all_file_paths:
        try:
            relative_posix = each_path.resolve().relative_to(resolved_root).as_posix()
        except ValueError:
            continue
        if any(
            relative_posix == each_prefix or relative_posix.startswith(each_prefix + "/")
            for each_prefix in normalized_prefixes
        ):
            filtered.append(each_path)
    return filtered


def paths_from_git_staged(repository_root: Path) -> list[Path]:
    """Retrieve file paths that are staged for commit.

    Uses ``git diff --cached --name-only -z`` to get the list of staged files.

    Args:
        repository_root: The repository root for running git commands.

    Returns:
        List of absolute Path objects for each staged file.

    Raises:
        SystemExit: When the git command fails.
    """
    name_result = subprocess.run(
        list(ALL_GIT_DIFF_CACHED_ARGS),
        cwd=str(repository_root),
        capture_output=True,
        check=False,
    )
    if name_result.returncode != 0:
        stderr_text = name_result.stderr.decode("utf-8", errors="replace")
        print(
            f"{BUGTEAM_CODE_RULES_GATE_PREFIX}git diff --cached --name-only -z failed:\n{stderr_text}",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_CODE_ENFORCER_MISSING)
    raw_paths = name_result.stdout.split(b"\x00")
    resolved_paths = []
    for each_raw_path in raw_paths:
        if not each_raw_path:
            continue
        try:
            relative_path = each_raw_path.decode("utf-8")
        except UnicodeDecodeError:
            print(
                f"{BUGTEAM_CODE_RULES_GATE_PREFIX}skipping staged path with non-UTF-8 filename: {each_raw_path!r}",
                file=sys.stderr,
            )
            continue
        resolved_paths.append(repository_root / relative_path)
    return resolved_paths


def staged_file_line_count(
    repository_root: Path,
    relative_path_posix: str,
) -> int:
    """Count lines in a staged file.

    Args:
        repository_root: The repository root.
        relative_path_posix: POSIX-style relative path to the staged file.

    Returns:
        Number of lines in the staged file (zero only when the file is genuinely empty).

    Raises:
        SystemExit: When ``git show`` fails. Returning zero on git errors
            would be indistinguishable from an empty file and would silently
            cause the gate to skip validating a newly added file.
    """
    show_result = subprocess.run(
        ["git", "show", f":{relative_path_posix}"],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if show_result.returncode != 0:
        print(
            f"{BUGTEAM_CODE_RULES_GATE_PREFIX}git show :{relative_path_posix} failed:\n"
            f"{show_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_CODE_ENFORCER_MISSING)
    staged_content = show_result.stdout
    if not staged_content:
        return 0
    return len(staged_content.splitlines())


def is_staged_file_newly_added(
    repository_root: Path,
    relative_path_posix: str,
) -> bool:
    """Check whether a staged file is newly added (not previously tracked).

    Args:
        repository_root: The repository root.
        relative_path_posix: POSIX-style relative path to the staged file.

    Returns:
        True when the file status starts with 'A' (added).

    Raises:
        SystemExit: When ``git diff --cached --name-status`` fails. Returning
            False on git errors would be indistinguishable from "modified, not
            added" and would cause the gate to silently skip validating a
            newly added file.
    """
    status_result = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "--", relative_path_posix],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if status_result.returncode != 0:
        print(
            f"{BUGTEAM_CODE_RULES_GATE_PREFIX}git diff --cached --name-status failed for "
            f"{relative_path_posix}:\n{status_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_CODE_ENFORCER_MISSING)
    for each_line in status_result.stdout.splitlines():
        stripped_line = each_line.strip()
        if stripped_line:
            return stripped_line.startswith("A")
    return False


def added_lines_for_staged_file(
    repository_root: Path,
    relative_path_posix: str,
) -> set[int]:
    """Determine which lines were added in a staged file.

    Uses ``git diff --cached --unified=0``. For newly added files, returns
    the full range of line numbers.

    Args:
        repository_root: The repository root.
        relative_path_posix: POSIX-style relative path to the staged file.

    Returns:
        Set of added line numbers (1-based).

    Raises:
        SystemExit: When the git diff command fails.
    """
    diff_result = subprocess.run(
        ["git", "diff", "--cached", "--unified=0", "--", relative_path_posix],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if diff_result.returncode != 0:
        print(
            f"{BUGTEAM_CODE_RULES_GATE_PREFIX}git diff --cached --unified=0 failed for {relative_path_posix}:\n"
            f"{diff_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_CODE_ENFORCER_MISSING)
    if diff_result.stdout.strip():
        return parse_added_line_numbers(diff_result.stdout)
    if is_staged_file_newly_added(repository_root, relative_path_posix):
        total_lines = staged_file_line_count(repository_root, relative_path_posix)
        if total_lines > 0:
            return set(range(1, total_lines + 1))
    return set()


def added_lines_by_file_staged(
    repository_root: Path,
    all_file_paths: list[Path],
) -> dict[Path, set[int]]:
    """Map each staged file path to the set of added line numbers.

    Args:
        repository_root: The repository root.
        all_file_paths: Staged file paths to check.

    Returns:
        Dictionary mapping resolved file paths to their added line numbers.
    """
    resolved_root = repository_root.resolve()
    added_by_path: dict[Path, set[int]] = {}
    for each_path in all_file_paths:
        try:
            resolved = each_path.resolve()
        except OSError:
            continue
        try:
            relative = resolved.relative_to(resolved_root)
        except ValueError:
            continue
        relative_posix = str(relative).replace("\\", "/")
        added_numbers = added_lines_for_staged_file(resolved_root, relative_posix)
        added_by_path[resolved] = added_numbers
    return added_by_path


def paths_from_git_diff(repository_root: Path, base_reference: str) -> list[Path]:
    """Retrieve file paths changed between merge-base and HEAD.

    Args:
        repository_root: The repository root.
        base_reference: The git reference for the merge-base comparison.

    Returns:
        List of absolute Path objects for changed files.

    Raises:
        SystemExit: When the git diff command fails.
    """
    merge_base = resolve_merge_base(repository_root, base_reference)
    name_result = subprocess.run(
        ["git", "diff", "--name-only", f"{merge_base}..HEAD"],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if name_result.returncode != 0:
        print(
            f"{BUGTEAM_CODE_RULES_GATE_PREFIX}git diff --name-only failed:\n{name_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_CODE_ENFORCER_MISSING)
    relative_paths = [line.strip() for line in name_result.stdout.splitlines() if line.strip()]
    return [repository_root / each_relative_path for each_relative_path in relative_paths]


def is_code_path(file_path: Path) -> bool:
    """Check whether a file path has a recognized code file extension.

    Args:
        file_path: The file path to check.

    Returns:
        True when the file extension is in the set of code extensions.
    """
    suffix = file_path.suffix.lower()
    return suffix in ALL_CODE_FILE_EXTENSIONS


def _path_is_eligible_for_validation(
    resolved_path: Path,
    repository_root: Path,
    read_staged_content_flag: bool,
) -> bool:
    """Decide whether *resolved_path* should be validated by the gate.

    Args:
        resolved_path: A resolved candidate path already confirmed to live
            under *repository_root*.
        repository_root: The repository root used to compute the relative path.
        read_staged_content_flag: When True, require staged-index presence so
            files staged for add or modify are validated and staged deletions
            are skipped; when False, require working-tree presence.

    Returns:
        True when the path carries a code extension and exists in the source
        the gate will read; False otherwise.
    """
    if not is_code_path(resolved_path):
        return False
    if read_staged_content_flag:
        relative_posix = str(
            resolved_path.relative_to(repository_root.resolve())
        ).replace("\\", "/")
        return staged_blob_exists(repository_root.resolve(), relative_posix)
    return resolved_path.is_file()


def _resolve_eligible_code_path(
    candidate_path: Path,
    repository_root: Path,
    read_staged_content_flag: bool = False,
) -> Path | None:
    """Resolve *candidate_path* and return it only when the gate should scan it.

    Args:
        candidate_path: One file path from the gate's candidate set.
        repository_root: The repository root the resolved path must fall under.
        read_staged_content_flag: When True, eligibility requires staged-index
            presence; when False, it requires working-tree presence.

    Returns:
        The resolved path when it lives under *repository_root*, carries a code
        extension, and is present in the source the gate will read; otherwise
        None.
    """
    try:
        resolved = candidate_path.resolve()
    except OSError:
        return None
    try:
        resolved.relative_to(repository_root.resolve())
    except ValueError:
        return None
    if not _path_is_eligible_for_validation(
        resolved, repository_root, read_staged_content_flag
    ):
        return None
    return resolved


def check_database_column_string_magic(content: str, file_path: str) -> list[str]:
    """Flag string literals that look like database/HTTP column or key names inside function bodies.

    Triggers when a snake_case string literal appears as the first element of a
    two-element tuple inside a function body (the characteristic column-name/value
    pair pattern). Files under ``config/`` and test files are exempt.

    Args:
        content: The source code content to inspect.
        file_path: The file path for exemption checks.

    Returns:
        List of violation messages, or an empty list when no violations are found.
    """
    if "/config/" in file_path.replace("\\", "/") or "\\config\\" in file_path:
        return []
    if "/tests/" in file_path.replace("\\", "/") or file_path.endswith(("_test.py", ".spec.py")):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    column_key_pattern = re.compile(r"^[a-z][a-z0-9_]{2,}$")
    for each_node in ast.walk(tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_child in ast.walk(each_node):
            if not isinstance(each_child, ast.Tuple):
                continue
            if len(each_child.elts) != MAXIMUM_COLUMN_TUPLE_ELEMENT_COUNT:
                continue
            first_element = each_child.elts[0]
            if not isinstance(first_element, ast.Constant):
                continue
            if not isinstance(first_element.value, str):
                continue
            literal_text = first_element.value
            if not column_key_pattern.match(literal_text):
                continue
            if literal_text in ALL_COLUMN_MAGIC_FALSE_VALUES:
                continue
            issues.append(
                f"Line {first_element.lineno}: Column-name string magic {literal_text!r} - extract to config"
            )
            if len(issues) >= MAXIMUM_ISSUES_TO_REPORT:
                print(
                    f"{BUGTEAM_CODE_RULES_GATE_PREFIX}check_database_column_string_magic "
                    f"cap reached at {MAXIMUM_ISSUES_TO_REPORT} issues for {file_path}; "
                    "additional matches were dropped.",
                    file=sys.stderr,
                )
                return issues
    return issues


def is_test_path(file_path: str) -> bool:
    """Return True when *file_path* matches CODE_RULES.md test-file detection patterns.

    Mirrors the test-file detection rule documented in CODE_RULES.md:
    filename matches test_*.py OR *_test.py OR *.test.* OR *.spec.* OR
    conftest.py, OR path contains the segment /tests/.

    Args:
        file_path: Path string to classify; backslashes are normalized to
            forward slashes before pattern matching.

    Returns:
        True when the path matches any test-file pattern; False otherwise.
    """
    tests_path_segment = "/tests/"
    conftest_filename = "conftest.py"
    test_filename_prefix = "test_"
    all_test_filename_suffixes = ("_test.py",)
    all_test_filename_glob_suffixes = (".test.", ".spec.")
    normalized_posix = file_path.replace("\\", "/")
    filename_only = normalized_posix.rsplit("/", maxsplit=1)[-1]
    if tests_path_segment in normalized_posix:
        return True
    if filename_only == conftest_filename:
        return True
    if filename_only.startswith(test_filename_prefix) and filename_only.endswith(
        PYTHON_FILE_EXTENSION
    ):
        return True
    if any(
        filename_only.endswith(each_suffix)
        for each_suffix in all_test_filename_suffixes
    ):
        return True
    if any(
        each_glob_suffix in filename_only
        for each_glob_suffix in all_test_filename_glob_suffixes
    ):
        return True
    return False


def _iter_calls_excluding_nested_functions(node: ast.AST) -> Iterator[ast.Call]:
    for each_child in ast.iter_child_nodes(node):
        if isinstance(each_child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(each_child, ast.Call):
            yield each_child
            continue
        yield from _iter_calls_excluding_nested_functions(each_child)


def _module_level_optional_kwargs_by_name(tree: ast.Module) -> dict[str, set[str]]:
    function_signatures: dict[str, set[str]] = {}
    for each_node in ast.iter_child_nodes(tree):
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            optional_kwargs: set[str] = set()
            for each_kwonly, each_default in zip(
                each_node.args.kwonlyargs, each_node.args.kw_defaults
            ):
                if each_default is not None:
                    optional_kwargs.add(each_kwonly.arg)
            positional_defaults = each_node.args.defaults
            positional_args_with_defaults = (
                each_node.args.args[-len(positional_defaults):]
                if positional_defaults
                else []
            )
            for each_positional_arg in positional_args_with_defaults:
                optional_kwargs.add(each_positional_arg.arg)
            function_signatures[each_node.name] = optional_kwargs
    return function_signatures


def _class_method_node_ids(tree: ast.Module) -> set[int]:
    class_method_node_ids: set[int] = set()
    for each_class_def in ast.walk(tree):
        if not isinstance(each_class_def, ast.ClassDef):
            continue
        for each_class_body_node in each_class_def.body:
            if isinstance(
                each_class_body_node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                class_method_node_ids.add(id(each_class_body_node))
    return class_method_node_ids


def _wrapper_dropped_kwarg_findings(
    wrapper_node: ast.FunctionDef | ast.AsyncFunctionDef,
    kwargs_by_function_name: dict[str, set[str]],
) -> Iterator[str]:
    wrapper_kwargs = kwargs_by_function_name.get(wrapper_node.name, set())
    for each_call in _iter_calls_excluding_nested_functions(wrapper_node):
        if isinstance(each_call.func, ast.Name):
            delegate_name = each_call.func.id
        elif isinstance(each_call.func, ast.Attribute):
            delegate_name = each_call.func.attr
        else:
            continue
        delegate_kwargs = kwargs_by_function_name.get(delegate_name)
        if delegate_kwargs is None:
            continue
        missing = delegate_kwargs - wrapper_kwargs
        if missing:
            yield (
                f"Line {wrapper_node.lineno}: Wrapper {wrapper_node.name!r} drops optional kwargs {sorted(missing)!r} of delegate {delegate_name!r}"
            )


def check_wrapper_plumb_through(content: str, file_path: str) -> list[str]:
    """Flag calls inside public functions that drop a same-file delegate's optional kwargs.

    Walks the AST. For every public function (name does not start with '_'),
    inspects every ast.Call inside its body and emits one finding per call
    whose target name matches a same-file function that exposes optional
    kwargs the enclosing public function does not also accept. Emission is
    capped at MAX_VIOLATIONS_PER_CHECK findings per call to run_gate.

    Limitations:
    - Only module-level FunctionDef nodes contribute signatures, and ClassDef
      methods are skipped both as signature sources and as wrapper candidates:
      a class method's signature is unrelated to a free-function delegate's
      keyword surface, so treating it as a wrapper produces false positives.
    - ast.Attribute calls match by attribute name only; the receiver type is
      not checked, so `self.fetch(...)` and `other.fetch(...)` both match a
      module-level `fetch` definition.
    - Nested call expressions inside another call's arguments are not treated as
      separate call sites; only the enclosing Call is inspected. This avoids
      false positives where a callee nested as an argument is confused with a
      top-level delegate invocation (for example `delegate(helper(x))`).

    Args:
        content: File content as a single string for AST parsing.
        file_path: Repository-relative POSIX path of the file (used to
            skip non-Python code extensions and test files early).

    Returns:
        List of violation strings, one per dropped optional kwarg. Empty for
        a non-Python file, a test file, or a file with a syntax error.
    """
    non_python_code_extensions = ALL_CODE_FILE_EXTENSIONS - {PYTHON_FILE_EXTENSION}
    lowercase_file_path = file_path.lower()
    if any(
        lowercase_file_path.endswith(each_extension)
        for each_extension in non_python_code_extensions
    ):
        return []
    if is_test_path(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    function_signatures = _module_level_optional_kwargs_by_name(tree)
    class_method_node_ids = _class_method_node_ids(tree)
    issues: list[str] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if id(each_node) in class_method_node_ids:
            continue
        if each_node.name.startswith("_"):
            continue
        for each_finding in _wrapper_dropped_kwarg_findings(each_node, function_signatures):
            issues.append(each_finding)
            if len(issues) >= MAX_VIOLATIONS_PER_CHECK:
                return issues
    return issues


def parse_added_line_numbers(unified_diff_text: str) -> set[int]:
    """Parse unified diff text and return the set of added line numbers.

    Args:
        unified_diff_text: The unified diff output to parse.

    Returns:
        Set of line numbers (1-based) that were added in the diff.
    """
    header_regex = hunk_header_pattern()
    added_line_numbers: set[int] = set()
    for each_line in unified_diff_text.splitlines():
        header_match = header_regex.match(each_line)
        if header_match is None:
            continue
        new_start_text, new_count_text = header_match.groups()
        new_start = int(new_start_text)
        new_count = 1 if new_count_text is None else int(new_count_text)
        if new_count <= 0:
            continue
        for each_number in range(new_start, new_start + new_count):
            added_line_numbers.add(each_number)
    return added_line_numbers


def is_file_new_at_base(
    repository_root: Path,
    merge_base: str,
    relative_path_posix: str,
) -> bool:
    """Check whether a file did not exist at the merge-base commit.

    Args:
        repository_root: The repository root.
        merge_base: The merge-base commit reference.
        relative_path_posix: POSIX-style relative path to check.

    Returns:
        True when the file does not exist in the base commit.
    """
    cat_result = subprocess.run(
        ["git", "cat-file", "-e", f"{merge_base}:{relative_path_posix}"],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return cat_result.returncode != 0


def added_lines_for_file(
    repository_root: Path,
    merge_base: str,
    relative_path_posix: str,
) -> set[int]:
    """Determine which lines were added in a file between merge-base and HEAD.

    Args:
        repository_root: The repository root.
        merge_base: The merge-base commit reference.
        relative_path_posix: POSIX-style relative path to the file.

    Returns:
        Set of added line numbers (1-based).

    Raises:
        SystemExit: When the git diff command fails.
    """
    diff_result = subprocess.run(
        ["git", "diff", "--unified=0", f"{merge_base}..HEAD", "--", relative_path_posix],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if diff_result.returncode != 0:
        print(
            f"{BUGTEAM_CODE_RULES_GATE_PREFIX}git diff --unified=0 failed for {relative_path_posix}:\n"
            f"{diff_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_CODE_ENFORCER_MISSING)
    if not diff_result.stdout.strip():
        return set()
    return parse_added_line_numbers(diff_result.stdout)


def whole_file_line_set(file_path: Path) -> set[int]:
    """Return a set of all line numbers in a file.

    Args:
        file_path: Path to the file.

    Returns:
        Set of line numbers (1-based), or an empty set when the file is empty.

    Raises:
        SystemExit: When the file cannot be read; an empty set must not be
            returned on read failure because the caller treats it as
            "no lines changed" and silently downgrades blocking violations.
    """
    try:
        total_lines = len(file_path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError) as read_error:
        print(
            f"{BUGTEAM_CODE_RULES_GATE_PREFIX}whole_file_line_set could not read "
            f"{file_path}: {type(read_error).__name__}: {read_error}",
            file=sys.stderr,
        )
        raise SystemExit(EXIT_CODE_ENFORCER_MISSING) from read_error
    if total_lines <= 0:
        return set()
    return set(range(1, total_lines + 1))


def added_lines_by_file(
    repository_root: Path,
    base_reference: str,
    all_file_paths: list[Path],
) -> dict[Path, set[int]]:
    """Map each changed file path to the set of added line numbers vs merge-base.

    Args:
        repository_root: The repository root.
        base_reference: The base reference for merge-base comparison.
        all_file_paths: File paths to check.

    Returns:
        Dictionary mapping resolved file paths to their added line numbers.
    """
    merge_base = resolve_merge_base(repository_root, base_reference)
    resolved_root = repository_root.resolve()
    added_by_path: dict[Path, set[int]] = {}
    for each_path in all_file_paths:
        try:
            resolved = each_path.resolve()
        except OSError:
            continue
        try:
            relative = resolved.relative_to(resolved_root)
        except ValueError:
            continue
        relative_posix = str(relative).replace("\\", "/")
        added_numbers = added_lines_for_file(resolved_root, merge_base, relative_posix)
        if not added_numbers and resolved.is_file():
            if is_file_new_at_base(resolved_root, merge_base, relative_posix):
                added_numbers = whole_file_line_set(resolved)
        added_by_path[resolved] = added_numbers
    return added_by_path


def extract_violation_line_number(violation_text: str) -> int | None:
    """Extract the line number from a violation message.

    Args:
        violation_text: The violation message text.

    Returns:
        The extracted line number, or None when no line number is present.
    """
    match_result = violation_line_pattern().match(violation_text)
    if match_result is None:
        return None
    return int(match_result.group(1))


def function_length_span_range(violation_text: str) -> range | None:
    """Return the declared line range of a function-length violation, or None.

    The enforcer's function-length message carries the definition line and
    the function's line span: ``Function 'NAME' (defined at line X) is Y
    lines - ...``. The function occupies lines ``X`` through ``X + Y - 1``
    inclusive.

    Args:
        violation_text: A single violation string emitted by the enforcer.

    Returns:
        A ``range`` covering the function's declared line span, or None when
        the text is not a function-length violation.
    """
    span_match = FUNCTION_LENGTH_VIOLATION_PATTERN.search(violation_text)
    if span_match is None:
        return None
    definition_line = int(span_match.group(FUNCTION_LENGTH_DEFINITION_LINE_GROUP_INDEX))
    line_span = int(span_match.group(FUNCTION_LENGTH_SPAN_GROUP_INDEX))
    return range(definition_line, definition_line + line_span)


def isolation_span_range(violation_text: str) -> range | None:
    """Return the enclosing test-function line range of an isolation violation.

    The enforcer's HOME/TMP isolation message carries the enclosing test
    function's definition line and span: ``Line N: Test 'NAME' (defined at
    line X, spanning Y lines) probes ...``. The function occupies lines ``X``
    through ``X + Y - 1`` inclusive, so a signature-line change that
    un-isolates an unchanged-body probe is scoped by the same span the
    enforcer uses rather than by the ``Line N:`` probe line alone.

    Args:
        violation_text: A single violation string emitted by the enforcer.

    Returns:
        A ``range`` covering the enclosing test function's declared line span,
        or None when the text is not an isolation violation.
    """
    span_match = ISOLATION_VIOLATION_PATTERN.search(violation_text)
    if span_match is None:
        return None
    definition_line = int(span_match.group(ISOLATION_DEFINITION_LINE_GROUP_INDEX))
    line_span = int(span_match.group(ISOLATION_SPAN_GROUP_INDEX))
    return range(definition_line, definition_line + line_span)


def banned_noun_span_range(violation_text: str) -> range | None:
    """Return the one-line binding span of a banned-noun violation, or None.

    The enforcer's banned-noun message carries the binding line and a one-line
    span: ``Line N: Identifier 'NAME' ... (binding span at line X, spanning 1
    lines)``. A banned-noun binding is a point fact about one identifier, so the
    span is always the binding line alone (``X`` through ``X``) — never the
    enclosing function span. Scoping to the binding line keeps a pre-existing
    parameter or local-name binding out of scope when an unrelated line of its
    enclosing function is edited.

    Args:
        violation_text: A single violation string emitted by the enforcer.

    Returns:
        A ``range`` covering the binding's one-line span, or None when the text
        is not a banned-noun violation.
    """
    span_match = BANNED_NOUN_VIOLATION_PATTERN.search(violation_text)
    if span_match is None:
        return None
    definition_line = int(span_match.group(BANNED_NOUN_DEFINITION_LINE_GROUP_INDEX))
    line_span = int(span_match.group(BANNED_NOUN_SPAN_GROUP_INDEX))
    return range(definition_line, definition_line + line_span)


def inline_duplicate_body_span_lines(violation_text: str) -> frozenset[int] | None:
    """Return the union of both spans of a same-file inline-duplicate issue, or None.

    The same-file inline-duplicate message names two functions that share a body —
    the helper and the enclosing function carrying the inline copy — and the live
    Write/Edit hook scopes the violation by the UNION of both spans, blocking when
    an edit touches either function. So the message carries both spans: ``(inline
    duplicate body spans: helper at line H spanning P lines, enclosing at line E
    spanning Q lines)``. The two spans can be disjoint (an unrelated function may
    sit between the helper and its inline copy), so this returns the union as a
    line-number set rather than a single contiguous range — a range covering the
    gap would wrongly block an edit confined to that intervening function, which
    the PreToolUse path leaves unflagged.

    Args:
        violation_text: A single violation string emitted by the enforcer.

    Returns:
        The frozenset of every line in the helper span and the enclosing span, or
        None when the text is not a same-file inline-duplicate violation.
    """
    span_match = INLINE_DUPLICATE_BODY_VIOLATION_PATTERN.search(violation_text)
    if span_match is None:
        return None
    helper_line = int(span_match.group(INLINE_DUPLICATE_BODY_HELPER_LINE_GROUP_INDEX))
    helper_span = int(span_match.group(INLINE_DUPLICATE_BODY_HELPER_SPAN_GROUP_INDEX))
    enclosing_line = int(
        span_match.group(INLINE_DUPLICATE_BODY_ENCLOSING_LINE_GROUP_INDEX)
    )
    enclosing_span = int(
        span_match.group(INLINE_DUPLICATE_BODY_ENCLOSING_SPAN_GROUP_INDEX)
    )
    helper_lines = range(helper_line, helper_line + helper_span)
    enclosing_lines = range(enclosing_line, enclosing_line + enclosing_span)
    return frozenset(helper_lines) | frozenset(enclosing_lines)


def _all_span_range_extractors() -> tuple[Callable[[str], range | None], ...]:
    return (
        function_length_span_range,
        isolation_span_range,
        banned_noun_span_range,
    )


def enclosing_span_range(violation_text: str) -> range | None:
    """Return the enclosing-unit line range of a span-tagged violation, or None.

    Every diff-scoped enforcer check tags its message with an enclosing-unit
    span fragment. This dispatcher tries each span extractor from
    ``_all_span_range_extractors`` so the gate reconstructs every scoped
    check's span through one shared mechanism — adding a new scoped check means
    adding one extractor to that registry rather than threading a new branch
    through ``split_violations_by_scope``.

    Args:
        violation_text: A single violation string emitted by the enforcer.

    Returns:
        The first non-None span range any extractor recovers, or None when the
        text carries no enclosing-unit span fragment.
    """
    for each_extractor in _all_span_range_extractors():
        span_range = each_extractor(violation_text)
        if span_range is not None:
            return span_range
    return None


def split_violations_by_scope(
    all_issues: list[str],
    all_added_line_numbers: set[int] | None,
) -> tuple[list[str], list[str]]:
    """Partition issues into blocking vs advisory based on touched lines.

    Args:
        all_issues: Violation strings emitted by the enforcer.
        all_added_line_numbers: Lines added in the current diff, or None
            to treat every violation as blocking.

    Returns:
        Tuple ``(blocking, advisory)``. When *all_added_line_numbers* is
        None, every issue is blocking. A same-file inline-duplicate violation
        carries both the helper span and the enclosing span;
        ``inline_duplicate_body_span_lines`` reconstructs their union as a
        line-number set, and the violation is blocking when an added line falls
        in either span — matching the live Write/Edit hook's union scoping. Every
        other diff-scoped violation (function-length, HOME/TMP isolation,
        banned-noun) carries one enclosing-unit span fragment that
        ``enclosing_span_range`` reconstructs through one shared extractor
        registry; such a violation is blocking
        when its declared span intersects the added lines (the unit grew or its
        signature changed in this diff) and advisory otherwise (a pre-existing
        untouched unit). Every other issue is blocking when its ``Line N:``
        prefix names an added line and advisory otherwise.
    """
    if all_added_line_numbers is None:
        return list(all_issues), []
    blocking: list[str] = []
    advisory: list[str] = []
    for each_issue in all_issues:
        inline_duplicate_lines = inline_duplicate_body_span_lines(each_issue)
        if inline_duplicate_lines is not None:
            if inline_duplicate_lines & all_added_line_numbers:
                blocking.append(each_issue)
            else:
                advisory.append(each_issue)
            continue
        span_range = enclosing_span_range(each_issue)
        if span_range is not None:
            if any(each_line in all_added_line_numbers for each_line in span_range):
                blocking.append(each_issue)
            else:
                advisory.append(each_issue)
            continue
        violation_line = extract_violation_line_number(each_issue)
        if violation_line is None:
            blocking.append(each_issue)
            continue
        if violation_line in all_added_line_numbers:
            blocking.append(each_issue)
        else:
            advisory.append(each_issue)
    return blocking, advisory


def print_violation_section(
    header_message: str,
    violations_by_file: dict[Path, list[str]],
    repository_root: Path,
) -> None:
    """Print a section of grouped violation messages grouped by file.

    Args:
        header_message: The section header to print first.
        violations_by_file: Violations grouped by file path.
        repository_root: Root for computing relative file paths.
    """
    print(header_message, file=sys.stderr)
    resolved_root = repository_root.resolve()
    for each_path in sorted(violations_by_file.keys()):
        relative = each_path.relative_to(resolved_root)
        print(f"{relative}:", file=sys.stderr)
        for each_issue in violations_by_file[each_path]:
            print(f"  {each_issue}", file=sys.stderr)


def read_prior_committed_content(
    repository_root: Path, relative_path_posix: str
) -> str:
    """Return the HEAD-committed content for *relative_path_posix*.

    Args:
        repository_root: The repository root for running git commands.
        relative_path_posix: POSIX-style relative path to read.

    Returns:
        The committed file content at HEAD, or an empty string when the
        path is not tracked or ``git show`` returns non-zero.
    """
    git_show_process = subprocess.run(
        ["git", "show", f"HEAD:{relative_path_posix}"],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if git_show_process.returncode != 0:
        return ""
    return git_show_process.stdout


def read_staged_content(
    repository_root: Path, relative_path_posix: str
) -> str | None:
    """Return the staged-blob content for *relative_path_posix*.

    Args:
        repository_root: The repository root for running git commands.
        relative_path_posix: POSIX-style relative path to read.

    Returns:
        The staged blob content, or None when the path is not staged, when
        ``git show`` returns non-zero, or when the staged bytes are not
        decodable Unicode (the caller skips and fails closed).
    """
    git_show_process = subprocess.run(
        ["git", "show", f":{relative_path_posix}"],
        cwd=str(repository_root),
        capture_output=True,
        check=False,
    )
    if git_show_process.returncode != 0:
        return None
    try:
        return git_show_process.stdout.decode(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def staged_blob_exists(
    repository_root: Path, relative_path_posix: str
) -> bool:
    """Report whether *relative_path_posix* is present in the staged index.

    Args:
        repository_root: The repository root for running git commands.
        relative_path_posix: POSIX-style relative path to probe.

    Returns:
        True when the path is staged for add or modify (its blob exists in the
        index); False when it is absent, such as a staged deletion.
    """
    git_cat_file_process = subprocess.run(
        ["git", "cat-file", "-e", f":{relative_path_posix}"],
        cwd=str(repository_root),
        capture_output=True,
        check=False,
    )
    return git_cat_file_process.returncode == 0


def _scoped_violations_for_file(
    validate_content: ValidateContentCallable,
    resolved_path: Path,
    repository_root: Path,
    all_added_lines_for_file: set[int] | None,
    read_staged_content_flag: bool = False,
) -> tuple[list[str], list[str]] | None:
    """Validate one resolved file and partition its violations by diff scope.

    Args:
        validate_content: The validator function from code_rules_enforcer.
        resolved_path: The resolved code file to validate.
        repository_root: The repository root for relative path resolution.
        all_added_lines_for_file: Lines added in the current diff for this file,
            or None to treat every violation as blocking.
        read_staged_content_flag: When True, source the content from the staged
            blob so it matches the staged diff that scoped the added lines.

    Returns:
        ``(blocking, advisory)`` for the file, or None when the file could not
        be read (the caller logs the skip and counts it).
    """
    relative_posix = str(
        resolved_path.relative_to(repository_root.resolve())
    ).replace("\\", "/")
    if read_staged_content_flag:
        staged_content = read_staged_content(repository_root.resolve(), relative_posix)
        if staged_content is None:
            print(f"{BUGTEAM_CODE_RULES_GATE_PREFIX}skip unreadable {resolved_path}", file=sys.stderr)
            return None
        content = staged_content
    else:
        try:
            content = resolved_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            print(f"{BUGTEAM_CODE_RULES_GATE_PREFIX}skip unreadable {resolved_path}", file=sys.stderr)
            return None
    prior_content = read_prior_committed_content(
        repository_root.resolve(), relative_posix
    )
    issues = validate_content(
        content,
        relative_posix,
        old_content=prior_content,
        defer_scope_to_caller=True,
    )
    issues.extend(check_database_column_string_magic(content, relative_posix))
    issues.extend(check_wrapper_plumb_through(content, relative_posix))
    if not issues:
        return [], []
    return split_violations_by_scope(issues, all_added_lines_for_file)


def run_gate(
    validate_content: ValidateContentCallable,
    all_file_paths: list[Path],
    repository_root: Path,
    all_added_lines_map: dict[Path, set[int]] | None,
    read_staged_content_flag: bool = False,
) -> int:
    """Run the CODE_RULES gate on a set of file paths.

    Applies validate_content, column-string-magic, and wrapper-plumb-through
    checks to each file, then reports violations grouped by file.

    Args:
        validate_content: The validator function from code_rules_enforcer.
        all_file_paths: File paths to validate.
        repository_root: The repository root for relative path resolution.
        all_added_lines_map: Optional map of resolved path to added line numbers.
            When provided, violations on added lines are blocking; others are advisory.
        read_staged_content_flag: When True, validate each file's staged blob
            so the content source matches the staged diff.

    Returns:
        Zero when every targeted file was validated and no blocking
        violations were found. Non-zero when any blocking violations were
        found OR when one or more files could not be read (a skipped file
        means the gate could not vouch for it).
    """
    blocking_by_file: dict[Path, list[str]] = {}
    advisory_by_file: dict[Path, list[str]] = {}
    skipped_unreadable_count = 0
    for each_file_path in sorted(set(all_file_paths)):
        resolved = _resolve_eligible_code_path(
            each_file_path, repository_root, read_staged_content_flag
        )
        if resolved is None:
            continue
        all_added_lines_for_file = (
            None if all_added_lines_map is None else all_added_lines_map.get(resolved)
        )
        scoped_violations = _scoped_violations_for_file(
            validate_content, resolved, repository_root,
            all_added_lines_for_file, read_staged_content_flag,
        )
        if scoped_violations is None:
            skipped_unreadable_count += 1
            continue
        blocking, advisory = scoped_violations
        if blocking:
            blocking_by_file[resolved] = blocking
        if advisory:
            advisory_by_file[resolved] = advisory
    return _report_partitioned_violations(
        blocking_by_file,
        advisory_by_file,
        repository_root,
        all_added_lines_map is None,
        skipped_unreadable_count,
    )


def _report_partitioned_violations(
    blocking_by_file: dict[Path, list[str]],
    advisory_by_file: dict[Path, list[str]],
    repository_root: Path,
    is_whole_file_scope: bool,
    skipped_unreadable_count: int,
) -> int:
    """Print the blocking and advisory sections and return the gate exit code.

    Args:
        blocking_by_file: Blocking violations grouped by resolved file path.
        advisory_by_file: Advisory violations grouped by resolved file path.
        repository_root: Repository root used to compute relative paths.
        is_whole_file_scope: True when no per-file added-line map was supplied,
            which selects the whole-file header wording.
        skipped_unreadable_count: Count of files that could not be read; a
            non-zero count forces a non-zero exit because the gate cannot
            vouch for those files.

    Returns:
        Zero when no blocking violations were found and no file was skipped;
        non-zero otherwise.
    """
    blocking_count = sum(len(each_list) for each_list in blocking_by_file.values())
    advisory_count = sum(len(each_list) for each_list in advisory_by_file.values())
    if blocking_count:
        if is_whole_file_scope:
            header = f"{BUGTEAM_CODE_RULES_GATE_PREFIX}{blocking_count} violation(s) reported."
        else:
            header = (
                f"{BUGTEAM_CODE_RULES_GATE_PREFIX}{blocking_count} violation(s) "
                "introduced on changed lines:"
            )
        print_violation_section(header, blocking_by_file, repository_root)
    if advisory_count:
        if blocking_count:
            print("", file=sys.stderr)
        print_violation_section(
            (
                f"{BUGTEAM_CODE_RULES_GATE_PREFIX}{advisory_count} pre-existing violation(s) "
                "in touched files (advisory, not blocking):"
            ),
            advisory_by_file,
            repository_root,
        )
    if skipped_unreadable_count:
        print(
            f"{BUGTEAM_CODE_RULES_GATE_PREFIX}{skipped_unreadable_count} file(s) "
            "skipped due to read errors; gate cannot vouch for those files.",
            file=sys.stderr,
        )
    if blocking_count or skipped_unreadable_count:
        return 1
    return 0


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the bugteam CODE_RULES gate.

    Args:
        all_argv: Command-line argument list.

    Returns:
        Parsed namespace with repo_root, base, staged, only_under, and paths.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Run CODE_RULES validators (validate_content) on files in the working tree. "
            "Default file set: git diff --name-only merge-base(base)..HEAD."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: cwd).",
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Merge-base ref for git diff (default: origin/main).",
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        default=False,
        help=(
            "Scope to staged changes only (git diff --cached). "
            "Blocks on violations introduced on staged-added lines; "
            "reports pre-existing violations in touched files as advisory."
        ),
    )
    parser.add_argument(
        "--only-under",
        action="append",
        default=[],
        dest="only_under",
        metavar="PREFIX",
        help=(
            "After resolving the merge-base diff, keep only files whose repo-relative path "
            "uses POSIX slashes and starts with PREFIX or equals PREFIX (repeatable)."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        help="Optional explicit files; if set, git diff is not used.",
    )
    return parser.parse_args(all_argv)


def main(all_arguments: list[str]) -> int:
    """Entry point for the bugteam CODE_RULES gate.

    Parses arguments, loads the validate_content function, determines the
    file scope (staged, diff against base, or explicit paths), and runs
    the gate.

    Args:
        all_arguments: Command-line arguments to parse.

    Returns:
        Zero when all checks pass, non-zero on violations or errors.
    """
    arguments = parse_arguments(all_arguments)
    repository_root = (
        arguments.repo_root.resolve()
        if arguments.repo_root is not None
        else Path.cwd().resolve()
    )
    validate_content = load_validate_content()
    if arguments.paths:
        all_parsed_paths = [repository_root / each_path for each_path in arguments.paths]
        return run_gate(validate_content, all_parsed_paths, repository_root, all_added_lines_map=None)
    if arguments.staged:
        staged_file_paths = paths_from_git_staged(repository_root)
        staged_file_paths = filter_paths_under_prefixes(
            staged_file_paths,
            repository_root,
            arguments.only_under,
        )
        if not staged_file_paths:
            return 0
        staged_added_lines = added_lines_by_file_staged(repository_root, staged_file_paths)
        return run_gate(
            validate_content,
            staged_file_paths,
            repository_root,
            all_added_lines_map=staged_added_lines,
            read_staged_content_flag=True,
        )
    all_diff_paths = paths_from_git_diff(repository_root, arguments.base)
    all_diff_paths = filter_paths_under_prefixes(
        all_diff_paths,
        repository_root,
        arguments.only_under,
    )
    if not all_diff_paths:
        return 0
    scoped_added_lines = added_lines_by_file(repository_root, arguments.base, all_diff_paths)
    return run_gate(
        validate_content,
        all_diff_paths,
        repository_root,
        all_added_lines_map=scoped_added_lines,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
