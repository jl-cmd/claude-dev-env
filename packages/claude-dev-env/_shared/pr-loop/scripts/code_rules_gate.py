import argparse
import ast
import importlib.util
import re
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

parent_directory = str(Path(__file__).resolve().parent)
if parent_directory not in sys.path:
    sys.path.insert(0, parent_directory)

from pr_loop_shared_constants.code_rules_gate_constants import (  # noqa: E402
    ALL_CODE_FILE_EXTENSIONS,
    ALL_GIT_DIFF_CACHED_NAME_ONLY_NULL_TERMINATED_COMMAND,
    ALL_GIT_DIFF_NAME_ONLY_NULL_TERMINATED_COMMAND_PREFIX,
    ALL_TEST_FILENAME_GLOB_SUFFIXES,
    ALL_TEST_FILENAME_SUFFIXES,
    EXPECTED_NON_RENAME_COLUMN_COUNT,
    EXPECTED_RENAME_COLUMN_COUNT,
    BANNED_NOUN_DEFINITION_LINE_GROUP_INDEX,
    BANNED_NOUN_SPAN_GROUP_INDEX,
    BANNED_NOUN_VIOLATION_PATTERN,
    DUPLICATE_BODY_DEFINITION_LINE_GROUP_INDEX,
    DUPLICATE_BODY_SPAN_GROUP_INDEX,
    DUPLICATE_BODY_VIOLATION_PATTERN,
    FUNCTION_LENGTH_DEFINITION_LINE_GROUP_INDEX,
    FUNCTION_LENGTH_SPAN_GROUP_INDEX,
    FUNCTION_LENGTH_VIOLATION_PATTERN,
    GIT_NAME_STATUS_ADDED_PREFIX,
    GIT_NAME_STATUS_RENAMED_PREFIX,
    ISOLATION_DEFINITION_LINE_GROUP_INDEX,
    ISOLATION_SPAN_GROUP_INDEX,
    ISOLATION_VIOLATION_PATTERN,
    MAX_VIOLATIONS_PER_CHECK,
    PYTHON_FILE_EXTENSION,
    TEST_CONFTEST_FILENAME,
    TEST_FILENAME_PREFIX,
    TESTS_PATH_SEGMENT,
)


ValidateContentCallable = Callable[..., list[str]]


def hunk_header_pattern() -> re.Pattern[str]:
    return re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def violation_line_pattern() -> re.Pattern[str]:
    return re.compile(r"^Line (\d+):")


def resolve_claude_dev_env_root(starting_path: Path) -> Path:
    """Walk up from *starting_path* to the claude-dev-env package root.

    Args:
        starting_path: A path inside the worktree; the function climbs to
            find the ancestor containing ``hooks/blocking/code_rules_enforcer.py``.

    Returns:
        The resolved package root that contains the enforcer file.

    Raises:
        SystemExit: When no ancestor contains the enforcer.
    """
    starting = Path(starting_path).resolve()
    enforcer_relative = Path("hooks") / "blocking" / "code_rules_enforcer.py"
    for each_candidate in [starting, *starting.parents]:
        if (each_candidate / enforcer_relative).is_file():
            return each_candidate
    print(
        f"code_rules_gate: could not locate {enforcer_relative} above {starting}",
        file=sys.stderr,
    )
    raise SystemExit(2)


def _resolve_package_root_absolute(starting_path: Path) -> Path:
    enforcer_relative = Path("hooks") / "blocking" / "code_rules_enforcer.py"
    for each_starting_form in (
        Path(starting_path).absolute(),
        Path(starting_path).resolve(),
    ):
        for each_candidate in [each_starting_form, *each_starting_form.parents]:
            if (each_candidate / enforcer_relative).is_file():
                return each_candidate
    raise SystemExit(2)


def load_validate_content() -> ValidateContentCallable:
    """Load ``code_rules_enforcer.validate_content`` for in-process use.

    Returns:
        The ``validate_content`` callable from the enforcer module.

    Raises:
        SystemExit: When the package root cannot be located or the
            enforcer module cannot be loaded from disk.
    """
    package_root = resolve_claude_dev_env_root(Path(__file__).resolve())
    enforcer_path = package_root / "hooks" / "blocking" / "code_rules_enforcer.py"
    if not enforcer_path.is_file():
        message = f"code_rules_gate: missing enforcer at {enforcer_path}"
        print(message, file=sys.stderr)
        raise SystemExit(2)
    specification = importlib.util.spec_from_file_location(
        "code_rules_enforcer",
        enforcer_path,
    )
    if specification is None or specification.loader is None:
        print("code_rules_gate: could not load code_rules_enforcer.", file=sys.stderr)
        raise SystemExit(2)
    module = importlib.util.module_from_spec(specification)
    package_root_for_imports = _resolve_package_root_absolute(Path(__file__).absolute())
    hooks_root_path = str(package_root_for_imports / "hooks")
    while hooks_root_path in sys.path:
        sys.path.remove(hooks_root_path)
    sys.path.insert(0, hooks_root_path)
    saved_hooks_constants_modules = {
        each_module_name: sys.modules.pop(each_module_name)
        for each_module_name in [
            each_key for each_key in list(sys.modules)
            if each_key == "hooks_constants" or each_key.startswith("hooks_constants.")
        ]
    }
    try:
        specification.loader.exec_module(module)
    finally:
        while hooks_root_path in sys.path:
            sys.path.remove(hooks_root_path)
        for each_module_name in [
            each_key for each_key in list(sys.modules)
            if each_key == "hooks_constants" or each_key.startswith("hooks_constants.")
        ]:
            sys.modules.pop(each_module_name, None)
        sys.modules.update(saved_hooks_constants_modules)
    return module.validate_content


def resolve_merge_base(repository_root: Path, base_reference: str) -> str:
    """Return the merge-base SHA between HEAD and *base_reference*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        base_reference: The git reference to merge-base against.

    Returns:
        The stripped merge-base SHA.

    Raises:
        SystemExit: When ``git merge-base`` returns non-zero.
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
            f"code_rules_gate: git merge-base HEAD {base_reference} failed:\n"
            f"{merge_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return merge_result.stdout.strip()


def filter_paths_under_prefixes(
    all_file_paths: list[Path],
    repository_root: Path,
    all_prefixes: list[str],
) -> list[Path]:
    """Filter *all_file_paths* to entries falling under the supplied prefixes.

    Args:
        all_file_paths: Resolved file paths to filter.
        repository_root: Repository root used to compute relative paths.
        all_prefixes: Repository-relative POSIX prefixes; each path must
            equal one prefix or be nested beneath it to pass through.

    Returns:
        The subset of *all_file_paths* whose relative POSIX path matches one
        of the prefixes. When *all_prefixes* is empty, returns the input
        list unchanged.
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
            relative_posix == each_prefix
            or relative_posix.startswith(each_prefix + "/")
            for each_prefix in normalized_prefixes
        ):
            filtered.append(each_path)
    return filtered


def paths_from_git_staged(repository_root: Path) -> list[Path]:
    """Return absolute paths for every file in the staged index.

    Args:
        repository_root: Repository root used as the ``git -C`` target.

    Returns:
        List of absolute paths for staged files. Names whose bytes cannot
        be decoded as Unicode are logged and skipped.

    Raises:
        SystemExit: When ``git diff --cached --name-only -z`` returns
            non-zero.
    """
    name_result = subprocess.run(
        list(ALL_GIT_DIFF_CACHED_NAME_ONLY_NULL_TERMINATED_COMMAND),
        cwd=str(repository_root),
        capture_output=True,
        check=False,
    )
    if name_result.returncode != 0:
        stderr_text = name_result.stderr.decode("utf-8", errors="replace")
        print(
            f"code_rules_gate: git diff --cached --name-only -z failed:\n{stderr_text}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    raw_paths = name_result.stdout.split(b"\x00")
    resolved_paths = []
    for each_raw_path in raw_paths:
        if not each_raw_path:
            continue
        try:
            relative_path = each_raw_path.decode("utf-8")
        except UnicodeDecodeError:
            print(
                f"code_rules_gate: skipping staged path with non-UTF-8 filename: {each_raw_path!r}",
                file=sys.stderr,
            )
            continue
        resolved_paths.append(repository_root / relative_path)
    return resolved_paths


def staged_file_line_count(
    repository_root: Path,
    relative_path_posix: str,
) -> int:
    """Return the staged-blob line count for *relative_path_posix*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        relative_path_posix: Repository-relative POSIX path of the staged
            file.

    Returns:
        The staged content line count, or zero when the blob is empty.

    Raises:
        SystemExit: When ``git show :<path>`` returns non-zero.
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
            f"code_rules_gate: git show :{relative_path_posix} failed:\n"
            f"{show_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    staged_content = show_result.stdout
    if not staged_content:
        return 0
    return len(staged_content.splitlines())


def is_staged_file_newly_added(
    repository_root: Path,
    relative_path_posix: str,
) -> bool:
    """Check whether *relative_path_posix* is newly added in the staged diff.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        relative_path_posix: Repository-relative POSIX path to inspect.

    Returns:
        True when the first non-empty name-status line begins with the git
        added-prefix; False otherwise.

    Raises:
        SystemExit: When ``git diff --cached --name-status`` returns
            non-zero.
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
            f"code_rules_gate: git diff --cached --name-status failed for "
            f"{relative_path_posix}:\n{status_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    for each_line in status_result.stdout.splitlines():
        stripped_line = each_line.strip()
        if stripped_line:
            return stripped_line.startswith(GIT_NAME_STATUS_ADDED_PREFIX)
    return False


def added_lines_for_staged_file(
    repository_root: Path,
    relative_path_posix: str,
) -> set[int]:
    """Return added line numbers within the staged diff for one file.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        relative_path_posix: Repository-relative POSIX path to inspect.

    Returns:
        Set of line numbers (1-indexed) added in the staged diff. When the
        file is newly added, returns every line in the staged blob.

    Raises:
        SystemExit: When the staged diff command returns non-zero.
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
            f"code_rules_gate: git diff --cached --unified=0 failed for {relative_path_posix}:\n"
            f"{diff_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(2)
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
    """Build a per-file map of staged-added line numbers.

    Args:
        repository_root: Repository root for diff invocations.
        all_file_paths: File paths whose added lines should be collected.

    Returns:
        Mapping from resolved file path to the set of staged-added line
        numbers.
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
    """Return absolute paths for every file changed since *base_reference*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        base_reference: The git reference to merge-base against.

    Returns:
        List of absolute paths changed since the merge-base of HEAD and
        *base_reference*.

    Raises:
        SystemExit: When the ``git diff --name-only`` command returns
            non-zero.
    """
    merge_base = resolve_merge_base(repository_root, base_reference)
    diff_command = list(ALL_GIT_DIFF_NAME_ONLY_NULL_TERMINATED_COMMAND_PREFIX) + [
        f"{merge_base}..HEAD"
    ]
    name_result = subprocess.run(
        diff_command,
        cwd=str(repository_root),
        capture_output=True,
        check=False,
    )
    if name_result.returncode != 0:
        stderr_text = name_result.stderr.decode("utf-8", errors="replace")
        print(
            f"code_rules_gate: git diff --name-only -z failed:\n{stderr_text}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    raw_paths = name_result.stdout.split(b"\x00")
    resolved_paths: list[Path] = []
    for each_raw_path in raw_paths:
        if not each_raw_path:
            continue
        try:
            relative_path = each_raw_path.decode("utf-8")
        except UnicodeDecodeError:
            print(
                f"code_rules_gate: skipping diff path with non-UTF-8 filename: {each_raw_path!r}",
                file=sys.stderr,
            )
            continue
        resolved_paths.append(repository_root / relative_path)
    return resolved_paths


def is_code_path(file_path: Path) -> bool:
    suffix = file_path.suffix.lower()
    return suffix in ALL_CODE_FILE_EXTENSIONS


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
    normalized_posix = file_path.replace("\\", "/")
    filename_only = normalized_posix.rsplit("/", maxsplit=1)[-1]
    if TESTS_PATH_SEGMENT in normalized_posix:
        return True
    if filename_only == TEST_CONFTEST_FILENAME:
        return True
    if filename_only.startswith(TEST_FILENAME_PREFIX) and filename_only.endswith(
        PYTHON_FILE_EXTENSION
    ):
        return True
    if any(
        filename_only.endswith(each_suffix)
        for each_suffix in ALL_TEST_FILENAME_SUFFIXES
    ):
        return True
    if any(
        each_glob_suffix in filename_only
        for each_glob_suffix in ALL_TEST_FILENAME_GLOB_SUFFIXES
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
    """Extract added line numbers from unified-diff text.

    Args:
        unified_diff_text: Output from ``git diff --unified=0``.

    Returns:
        Set of newly-added line numbers (1-indexed) extracted from the
        hunk headers.
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
    """Check whether *relative_path_posix* did not exist at *merge_base*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        merge_base: The merge-base SHA against which to check existence.
        relative_path_posix: Repository-relative POSIX path to inspect.

    Returns:
        True when ``git cat-file -e`` fails to find the blob at the merge
        base (i.e. the file was added on the HEAD side); False otherwise.
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
    """Return added line numbers for *relative_path_posix* since *merge_base*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        merge_base: The merge-base SHA against which to diff.
        relative_path_posix: Repository-relative POSIX path to inspect.

    Returns:
        Set of line numbers (1-indexed) added on the HEAD side of the diff.

    Raises:
        SystemExit: When the diff command returns non-zero.
    """
    diff_result = subprocess.run(
        [
            "git",
            "diff",
            "--unified=0",
            f"{merge_base}..HEAD",
            "--",
            relative_path_posix,
        ],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if diff_result.returncode != 0:
        print(
            f"code_rules_gate: git diff --unified=0 failed for {relative_path_posix}:\n"
            f"{diff_result.stderr}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    if not diff_result.stdout.strip():
        return set()
    return parse_added_line_numbers(diff_result.stdout)


def whole_file_line_set(file_path: Path) -> set[int]:
    """Return the set of line numbers covering an entire file.

    Args:
        file_path: Path to the file whose line span should be summarized.

    Returns:
        Set of line numbers (1-indexed) covering every line in *file_path*,
        or an empty set when the file is unreadable or empty.
    """
    try:
        total_lines = len(file_path.read_text(encoding="utf-8").splitlines())
    except (OSError, UnicodeDecodeError) as read_error:
        print(
            f"code_rules_gate: skipping unreadable file {file_path}: {read_error}",
            file=sys.stderr,
        )
        return set()
    if total_lines <= 0:
        return set()
    return set(range(1, total_lines + 1))


def renamed_file_source_map_since(
    repository_root: Path,
    merge_base: str,
) -> dict[str, str]:
    """Return a mapping from rename-destination path to rename-source path.

    Runs `git diff --name-status -M -z merge_base..HEAD` and collects both
    paths of every rename entry (status code starting with R, e.g. `R100`).
    Keys are destination posix paths; values are source posix paths. The
    -z flag asks git for null-terminated, unquoted output so paths
    containing tab or newline bytes are not misparsed by column or line
    splitting; rename records emit three null-terminated tokens in
    sequence (status, source, destination), other status records emit
    two (status, path).

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        merge_base: The merge-base SHA against which to diff.

    Returns:
        Mapping from rename-destination POSIX path to rename-source POSIX
        path. Empty when no rename records are present.

    Raises:
        SystemExit: When ``git diff --name-status`` returns non-zero.
    """
    name_status_result = subprocess.run(
        ["git", "diff", "--name-status", "-M", "-z", f"{merge_base}..HEAD"],
        cwd=str(repository_root),
        capture_output=True,
        check=False,
    )
    if name_status_result.returncode != 0:
        stderr_text = name_status_result.stderr.decode("utf-8", errors="replace")
        print(
            f"code_rules_gate: git diff --name-status -M -z failed:\n"
            f"{stderr_text}",
            file=sys.stderr,
        )
        raise SystemExit(2)
    null_separated_tokens = [
        each_token.decode("utf-8", errors="replace")
        for each_token in name_status_result.stdout.split(b"\x00")
        if each_token
    ]
    rename_source_by_destination: dict[str, str] = {}
    next_token_index = 0
    while next_token_index < len(null_separated_tokens):
        status_code = null_separated_tokens[next_token_index]
        if status_code.startswith(GIT_NAME_STATUS_RENAMED_PREFIX):
            if next_token_index + EXPECTED_RENAME_COLUMN_COUNT > len(
                null_separated_tokens
            ):
                break
            source_path = null_separated_tokens[next_token_index + 1].replace(
                "\\", "/"
            )
            destination_path = null_separated_tokens[next_token_index + 2].replace(
                "\\", "/"
            )
            rename_source_by_destination[destination_path] = source_path
            next_token_index += EXPECTED_RENAME_COLUMN_COUNT
            continue
        next_token_index += EXPECTED_NON_RENAME_COLUMN_COUNT
    return rename_source_by_destination


def added_lines_for_renamed_file(
    repository_root: Path,
    merge_base: str,
    source_posix: str,
    destination_posix: str,
) -> set[int]:
    """Return added line numbers for a renamed file via blob comparison.

    Compares `merge_base:source_posix` against `HEAD:destination_posix`
    to surface only truly added lines, ignoring lines that already existed
    in the source file before the rename. Falls back to whole-file coverage
    when the source blob is absent at the merge base (i.e. the source was
    itself a new or renamed file that landed earlier in the branch).

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        merge_base: The merge-base SHA against which to compare blobs.
        source_posix: Rename-source POSIX path at the merge base.
        destination_posix: Rename-destination POSIX path at HEAD.

    Returns:
        Set of line numbers (1-indexed) added on the HEAD side of the
        comparison; empty on diff failure.
    """
    diff_result = subprocess.run(
        [
            "git",
            "diff",
            "--unified=0",
            f"{merge_base}:{source_posix}",
            f"HEAD:{destination_posix}",
        ],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if diff_result.returncode != 0:
        print(
            f"code_rules_gate: git diff failed for renamed file {merge_base}:{source_posix} "
            f"vs HEAD:{destination_posix} (returncode={diff_result.returncode}); "
            f"stderr={diff_result.stderr.strip()!r}",
            file=sys.stderr,
        )
        return set()
    if not diff_result.stdout.strip():
        return set()
    return parse_added_line_numbers(diff_result.stdout)


def added_lines_by_file(
    repository_root: Path,
    base_reference: str,
    all_file_paths: list[Path],
) -> dict[Path, set[int]]:
    """Build a per-file map of added line numbers across the branch.

    Args:
        repository_root: Repository root for diff invocations.
        base_reference: The git reference to merge-base against.
        all_file_paths: File paths whose added lines should be collected.

    Returns:
        Mapping from resolved file path to the set of line numbers added
        on the HEAD side, with renames resolved to compare against the
        original source path.
    """
    merge_base = resolve_merge_base(repository_root, base_reference)
    resolved_root = repository_root.resolve()
    rename_source_map = renamed_file_source_map_since(resolved_root, merge_base)
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
        if relative_posix in rename_source_map:
            added_numbers = added_lines_for_renamed_file(
                resolved_root,
                merge_base,
                rename_source_map[relative_posix],
                relative_posix,
            )
        else:
            added_numbers = added_lines_for_file(
                resolved_root, merge_base, relative_posix
            )
            if not added_numbers and resolved.is_file():
                if is_file_new_at_base(resolved_root, merge_base, relative_posix):
                    added_numbers = whole_file_line_set(resolved)
        added_by_path[resolved] = added_numbers
    return added_by_path


def extract_violation_line_number(violation_text: str) -> int | None:
    """Return the line number captured by the gate's violation-line regex.

    Args:
        violation_text: A single violation string of the form ``Line N: ...``.

    Returns:
        The integer line number captured in the prefix, or None when the
        text does not match the violation-line pattern.
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


def duplicate_body_span_range(violation_text: str) -> range | None:
    """Return the copied function's source line range of a duplicate-body issue.

    The duplicate-body message carries the copied function's definition line and
    its full body span: ``Function 'NAME' duplicates location.py::name — ...
    (duplicate body span at line X, spanning Y lines)``. The function occupies
    lines ``X`` through ``X + Y - 1`` inclusive, so a duplicate of a sibling helper
    is blocking only when the diff touches the copied function and advisory when an
    unrelated edit leaves a pre-existing copy untouched — matching the span-scoped
    PreToolUse Write/Edit behavior rather than blocking every duplicate-body
    message unconditionally.

    Args:
        violation_text: A single violation string emitted by the enforcer.

    Returns:
        A ``range`` covering the copied function's declared line span, or None
        when the text is not a duplicate-body violation.
    """
    span_match = DUPLICATE_BODY_VIOLATION_PATTERN.search(violation_text)
    if span_match is None:
        return None
    definition_line = int(span_match.group(DUPLICATE_BODY_DEFINITION_LINE_GROUP_INDEX))
    line_span = int(span_match.group(DUPLICATE_BODY_SPAN_GROUP_INDEX))
    return range(definition_line, definition_line + line_span)


def _all_span_range_extractors() -> tuple[Callable[[str], range | None], ...]:
    return (
        function_length_span_range,
        isolation_span_range,
        banned_noun_span_range,
        duplicate_body_span_range,
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
        None, every issue is blocking. Every diff-scoped violation
        (function-length, HOME/TMP isolation, banned-noun, duplicate-body)
        carries an enclosing-unit span fragment that ``enclosing_span_range``
        reconstructs through one shared extractor registry; such a violation is
        blocking
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
    """Print a labeled block of violations grouped by relative path.

    Args:
        header_message: Section header to write to stderr.
        violations_by_file: Mapping from absolute file path to the list of
            violation strings to render under that path.
        repository_root: Repository root used to compute relative paths.
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
        repository_root: Repository root used as the ``git -C`` target.
        relative_path_posix: Repository-relative POSIX path to read.

    Returns:
        The committed file content at HEAD, or an empty string when the
        path is not tracked or ``git show`` returns non-zero.
    """
    show_result = subprocess.run(
        ["git", "show", f"HEAD:{relative_path_posix}"],
        cwd=str(repository_root),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if show_result.returncode != 0:
        return ""
    return show_result.stdout


def read_staged_content(
    repository_root: Path, relative_path_posix: str
) -> str | None:
    """Return the staged-blob content for *relative_path_posix*.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        relative_path_posix: Repository-relative POSIX path to read.

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
        repository_root: Repository root used as the ``git -C`` target.
        relative_path_posix: Repository-relative POSIX path to probe.

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


def _path_is_eligible_for_validation(
    resolved_path: Path,
    repository_root: Path,
    read_staged_content_flag: bool,
) -> bool:
    """Decide whether *resolved_path* should be validated by the gate.

    Args:
        resolved_path: A resolved candidate path already confirmed to live
            under *repository_root*.
        repository_root: Repository root used to compute the relative path.
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


def _scoped_violations_for_file(
    validate_content: ValidateContentCallable,
    resolved_path: Path,
    repository_root: Path,
    all_added_lines_for_file: set[int] | None,
    read_staged_content_flag: bool = False,
) -> tuple[list[str], list[str]] | None:
    """Validate one resolved file and partition its violations by diff scope.

    Args:
        validate_content: The enforcer ``validate_content`` callable.
        resolved_path: The resolved code file to validate.
        repository_root: Repository root used to resolve the relative path.
        all_added_lines_for_file: Lines added in the current diff for this file,
            or None to treat every violation as blocking.
        read_staged_content_flag: When True, source the content from the staged
            blob so it matches the staged diff that scoped the added lines.

    Returns:
        ``(blocking, advisory)`` for the file, or None when the file is
        unreadable (the caller logs and skips it).
    """
    relative_posix = str(
        resolved_path.relative_to(repository_root.resolve())
    ).replace("\\", "/")
    if read_staged_content_flag:
        staged_content = read_staged_content(repository_root.resolve(), relative_posix)
        if staged_content is None:
            print(f"code_rules_gate: skip unreadable {resolved_path}", file=sys.stderr)
            return None
        content = staged_content
    else:
        try:
            content = resolved_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            print(f"code_rules_gate: skip unreadable {resolved_path}", file=sys.stderr)
            return None
    prior_content = read_prior_committed_content(
        repository_root.resolve(), relative_posix
    )
    issues = validate_content(
        content,
        relative_posix,
        prior_content,
        defer_scope_to_caller=True,
        sibling_directory=resolved_path.parent,
    )
    issues.extend(check_wrapper_plumb_through(content, relative_posix))
    if not issues:
        return [], []
    return split_violations_by_scope(issues, all_added_lines_for_file)


def run_gate(
    validate_content: ValidateContentCallable,
    all_file_paths: list[Path],
    repository_root: Path,
    all_added_lines_by_path: dict[Path, set[int]] | None = None,
    read_staged_content_flag: bool = False,
) -> int:
    """Run the gate over *all_file_paths* and emit a partitioned report.

    Args:
        validate_content: The enforcer ``validate_content`` callable.
        all_file_paths: File paths to inspect.
        repository_root: Repository root used to resolve relative paths.
        all_added_lines_by_path: Optional per-file added-line maps used to
            partition issues into blocking vs advisory.
        read_staged_content_flag: When True, validate each file's staged blob
            so the content source matches the staged diff.

    Returns:
        Zero when every targeted file was validated and no blocking violation
        was found. Non-zero when any blocking violation was reported OR when
        one or more files could not be read (a skipped file means the gate
        could not vouch for it).
    """
    blocking_by_file, advisory_by_file, skipped_unreadable_count = (
        _collect_partitioned_violations(
            validate_content,
            all_file_paths,
            repository_root,
            all_added_lines_by_path,
            read_staged_content_flag,
        )
    )
    return _report_partitioned_violations(
        blocking_by_file,
        advisory_by_file,
        repository_root,
        all_added_lines_by_path is None,
        skipped_unreadable_count,
    )


def _collect_partitioned_violations(
    validate_content: ValidateContentCallable,
    all_file_paths: list[Path],
    repository_root: Path,
    all_added_lines_by_path: dict[Path, set[int]] | None,
    read_staged_content_flag: bool = False,
) -> tuple[dict[Path, list[str]], dict[Path, list[str]], int]:
    """Validate every targeted file and partition results by diff scope.

    Args:
        validate_content: The enforcer ``validate_content`` callable.
        all_file_paths: File paths to inspect.
        repository_root: Repository root used to resolve relative paths.
        all_added_lines_by_path: Optional per-file added-line maps used to
            partition issues into blocking vs advisory.
        read_staged_content_flag: When True, validate each file's staged blob
            so the content source matches the staged diff.

    Returns:
        ``(blocking_by_file, advisory_by_file, skipped_unreadable_count)`` where
        the skipped count increments for every changed file that could not be
        read, so the caller can fail closed on unvalidated files.
    """
    blocking_by_file: dict[Path, list[str]] = {}
    advisory_by_file: dict[Path, list[str]] = {}
    skipped_unreadable_count = 0
    for each_path in sorted(set(all_file_paths)):
        try:
            resolved = each_path.resolve()
        except OSError:
            continue
        try:
            resolved.relative_to(repository_root.resolve())
        except ValueError:
            continue
        if not _path_is_eligible_for_validation(
            resolved, repository_root, read_staged_content_flag
        ):
            continue
        all_added_lines_for_file = (
            None
            if all_added_lines_by_path is None
            else all_added_lines_by_path.get(resolved)
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
    return blocking_by_file, advisory_by_file, skipped_unreadable_count


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
        skipped_unreadable_count: Count of changed files that could not be read;
            a non-zero count forces a non-zero exit because the gate cannot
            vouch for those files.

    Returns:
        Zero when no blocking violation was found and no file was skipped;
        non-zero otherwise.
    """
    blocking_count = sum(len(each_list) for each_list in blocking_by_file.values())
    advisory_count = sum(len(each_list) for each_list in advisory_by_file.values())
    if blocking_count:
        if is_whole_file_scope:
            header = f"code_rules_gate: {blocking_count} violation(s) reported."
        else:
            header = (
                f"code_rules_gate: {blocking_count} violation(s) "
                "introduced on changed lines:"
            )
        print_violation_section(header, blocking_by_file, repository_root)
    if advisory_count:
        if blocking_count:
            print("", file=sys.stderr)
        print_violation_section(
            (
                f"code_rules_gate: {advisory_count} pre-existing violation(s) "
                "in touched files (advisory, not blocking):"
            ),
            advisory_by_file,
            repository_root,
        )
    if skipped_unreadable_count:
        print(
            f"code_rules_gate: {skipped_unreadable_count} file(s) "
            "skipped due to read errors; gate cannot vouch for those files.",
            file=sys.stderr,
        )
    if blocking_count or skipped_unreadable_count:
        return 1
    return 0


def parse_arguments(all_arguments: list[str]) -> argparse.Namespace:
    """Parse the command-line arguments for the code-rules gate.

    Args:
        all_arguments: Command-line argument list forwarded to argparse.

    Returns:
        The parsed argparse namespace with ``repo_root``, ``base``,
        ``staged``, ``only_under``, and ``paths`` attributes.
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
    return parser.parse_args(all_arguments)


def main(all_arguments: list[str]) -> int:
    """Run the gate using the parsed CLI arguments.

    Args:
        all_arguments: Command-line argument list forwarded to argparse.

    Returns:
        The exit code from ``run_gate`` (``0`` clean, ``1`` blocking
        violations).
    """
    arguments = parse_arguments(all_arguments)
    repository_root = (
        arguments.repo_root.resolve()
        if arguments.repo_root is not None
        else Path.cwd().resolve()
    )
    validate_content = load_validate_content()
    if arguments.paths:
        file_paths = [repository_root / each_path for each_path in arguments.paths]
        return run_gate(
            validate_content, file_paths, repository_root, all_added_lines_by_path=None
        )
    if arguments.staged:
        staged_file_paths = paths_from_git_staged(repository_root)
        staged_file_paths = filter_paths_under_prefixes(
            staged_file_paths,
            repository_root,
            arguments.only_under,
        )
        if not staged_file_paths:
            return 0
        staged_added_lines = added_lines_by_file_staged(
            repository_root, staged_file_paths
        )
        return run_gate(
            validate_content,
            staged_file_paths,
            repository_root,
            all_added_lines_by_path=staged_added_lines,
            read_staged_content_flag=True,
        )
    file_paths = paths_from_git_diff(repository_root, arguments.base)
    file_paths = filter_paths_under_prefixes(
        file_paths,
        repository_root,
        arguments.only_under,
    )
    if not file_paths:
        return 0
    scoped_added_lines = added_lines_by_file(
        repository_root, arguments.base, file_paths
    )
    return run_gate(
        validate_content,
        file_paths,
        repository_root,
        all_added_lines_by_path=scoped_added_lines,
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
