from __future__ import annotations

import argparse
import ast
import importlib.util
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

ValidateContentCallable = Callable[..., list[str]]

from bugteam_scripts_constants.bugteam_code_rules_gate_constants import (
    ALL_CODE_FILE_EXTENSIONS,
    ALL_COLUMN_MAGIC_FALSE_VALUES,
    ALL_GIT_DIFF_CACHED_ARGS,
    ALL_JS_FILE_EXTENSIONS,
    BUGTEAM_CODE_RULES_GATE_PREFIX,
    EXIT_CODE_ENFORCER_MISSING,
    HUNK_HEADER_RAW_PATTERN,
    MAXIMUM_COLUMN_TUPLE_ELEMENT_COUNT,
    MAXIMUM_ISSUES_TO_REPORT,
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


def check_wrapper_plumb_through(content: str, file_path: str) -> list[str]:
    """Flag public wrappers that drop optional kwargs of a same-file delegate.

    Walks the AST. For every public function (name does not start with '_'),
    if its body contains exactly one direct call to another same-file
    function and that delegate's signature accepts optional kwargs that the
    wrapper does not also accept, emit a finding with both line numbers.

    Args:
        content: The source code content to inspect.
        file_path: The file path for JS/TS extension exemption.

    Returns:
        List of violation messages, or an empty list when no violations are found.
    """
    if file_path.endswith(ALL_JS_FILE_EXTENSIONS):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    function_signatures: dict[str, set[str]] = {}
    for each_node in ast.walk(tree):
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            optional_kwargs: set[str] = set()
            for each_kwonly, each_default in zip(each_node.args.kwonlyargs, each_node.args.kw_defaults):
                if each_default is not None:
                    optional_kwargs.add(each_kwonly.arg)
            function_signatures[each_node.name] = optional_kwargs
    issues: list[str] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if each_node.name.startswith("_"):
            continue
        wrapper_kwargs = function_signatures.get(each_node.name, set())
        for each_call in ast.walk(each_node):
            if not isinstance(each_call, ast.Call):
                continue
            if not isinstance(each_call.func, ast.Attribute):
                continue
            delegate_name = each_call.func.attr
            delegate_kwargs = function_signatures.get(delegate_name)
            if delegate_kwargs is None:
                continue
            missing = delegate_kwargs - wrapper_kwargs
            if missing:
                issues.append(
                    f"Line {each_node.lineno}: Wrapper {each_node.name!r} drops optional kwargs {sorted(missing)!r} of delegate {delegate_name!r}"
                )
                if len(issues) >= MAXIMUM_ISSUES_TO_REPORT:
                    print(
                        f"{BUGTEAM_CODE_RULES_GATE_PREFIX}check_wrapper_plumb_through "
                        f"cap reached at {MAXIMUM_ISSUES_TO_REPORT} issues for {file_path}; "
                        "additional matches were dropped.",
                        file=sys.stderr,
                    )
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
        total_lines = len(file_path.read_text().splitlines())
    except OSError as read_error:
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


def split_violations_by_scope(
    all_issues: list[str],
    all_added_line_numbers: set[int] | None,
) -> tuple[list[str], list[str]]:
    """Split violations into blocking and advisory groups by line number.

    Args:
        all_issues: All violation messages to split.
        all_added_line_numbers: Set of added line numbers, or None for full-file scope.

    Returns:
        Tuple of (blocking_issues, advisory_issues).
    """
    if all_added_line_numbers is None:
        return list(all_issues), []
    blocking: list[str] = []
    advisory: list[str] = []
    for each_issue in all_issues:
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


def run_gate(
    validate_content: ValidateContentCallable,
    all_file_paths: list[Path],
    repository_root: Path,
    all_added_lines_map: dict[Path, set[int]] | None,
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
        try:
            resolved = each_file_path.resolve()
        except OSError:
            continue
        try:
            resolved.relative_to(repository_root.resolve())
        except ValueError:
            continue
        if not is_code_path(resolved):
            continue
        if not resolved.is_file():
            continue
        try:
            content = resolved.read_text(encoding="utf-8")
        except OSError:
            print(f"{BUGTEAM_CODE_RULES_GATE_PREFIX}skip unreadable {resolved}", file=sys.stderr)
            skipped_unreadable_count += 1
            continue
        relative = resolved.relative_to(repository_root.resolve())
        issues = validate_content(content, str(relative).replace("\\", "/"), old_content=content)
        issues.extend(check_database_column_string_magic(content, str(relative).replace("\\", "/")))
        issues.extend(check_wrapper_plumb_through(content, str(relative).replace("\\", "/")))
        if not issues:
            continue
        added_for_file = None if all_added_lines_map is None else all_added_lines_map.get(resolved)
        blocking, advisory = split_violations_by_scope(issues, added_for_file)
        if blocking:
            blocking_by_file[resolved] = blocking
        if advisory:
            advisory_by_file[resolved] = advisory
    blocking_count = sum(len(each_list) for each_list in blocking_by_file.values())
    advisory_count = sum(len(each_list) for each_list in advisory_by_file.values())
    if blocking_count:
        if all_added_lines_map is None:
            header = f"{BUGTEAM_CODE_RULES_GATE_PREFIX}{blocking_count} violation(s) reported."
        else:
            header = (
                f"{BUGTEAM_CODE_RULES_GATE_PREFIX}{blocking_count} violation(s) "
                "introduced on changed lines:"
            )
        print_violation_section(
            header,
            blocking_by_file,
            repository_root,
        )
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
