import argparse
import ast
import importlib.util
import re
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

sys.modules.pop("config", None)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.code_rules_gate_constants import (
    ALL_CODE_FILE_EXTENSIONS,
    ALL_GIT_DIFF_CACHED_NAME_ONLY_NULL_TERMINATED_COMMAND,
    ALL_GIT_DIFF_NAME_ONLY_NULL_TERMINATED_COMMAND_PREFIX,
    ALL_LITERAL_KEYWORD_EXEMPTIONS,
    ALL_TEST_FILENAME_GLOB_SUFFIXES,
    ALL_TEST_FILENAME_SUFFIXES,
    COLUMN_KEY_PATTERN_TEMPLATE,
    CONFIG_PATH_SEGMENT,
    EXPECTED_NON_RENAME_COLUMN_COUNT,
    EXPECTED_RENAME_COLUMN_COUNT,
    EXPECTED_TUPLE_PAIR_LENGTH,
    GIT_NAME_STATUS_ADDED_PREFIX,
    GIT_NAME_STATUS_RENAMED_PREFIX,
    MAX_VIOLATIONS_PER_CHECK,
    MINIMUM_COLUMN_NAME_LENGTH_AFTER_FIRST_CHAR,
    PYTHON_FILE_EXTENSION,
    TEST_CONFTEST_FILENAME,
    TEST_FILENAME_PREFIX,
    TESTS_PATH_SEGMENT,
)


ValidateContentCallable = Callable[[str, str, str], list[str]]


def hunk_header_pattern() -> re.Pattern[str]:
    return re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@")


def violation_line_pattern() -> re.Pattern[str]:
    return re.compile(r"^Line (\d+):")


def resolve_claude_dev_env_root(starting_path: Path) -> Path:
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


def load_validate_content() -> ValidateContentCallable:
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
    specification.loader.exec_module(module)
    return module.validate_content


def resolve_merge_base(repository_root: Path, base_reference: str) -> str:
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


def check_database_column_string_magic(content: str, file_path: str) -> list[str]:
    """Flag string literals that look like database/HTTP column or key names inside function bodies.

    Triggers when a snake_case string literal appears as the first element of a
    two-element tuple inside a function body (the characteristic column-name/value
    pair pattern). Files under ``config/`` and test files are exempt.
    """
    normalized_path = file_path.replace("\\", "/")
    if CONFIG_PATH_SEGMENT in normalized_path:
        return []
    if is_test_path(normalized_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    column_key_pattern = re.compile(
        COLUMN_KEY_PATTERN_TEMPLATE.format(
            minimum_length=MINIMUM_COLUMN_NAME_LENGTH_AFTER_FIRST_CHAR
        )
    )
    seen_tuple_node_ids: set[int] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_child in ast.walk(each_node):
            if not isinstance(each_child, ast.Tuple):
                continue
            if id(each_child) in seen_tuple_node_ids:
                continue
            seen_tuple_node_ids.add(id(each_child))
            if len(each_child.elts) != EXPECTED_TUPLE_PAIR_LENGTH:
                continue
            first_element = each_child.elts[0]
            if not isinstance(first_element, ast.Constant):
                continue
            if not isinstance(first_element.value, str):
                continue
            literal_text = first_element.value
            if not column_key_pattern.match(literal_text):
                continue
            if literal_text in ALL_LITERAL_KEYWORD_EXEMPTIONS:
                continue
            issues.append(
                f"Line {first_element.lineno}: Column-name string magic {literal_text!r} - extract to config"
            )
            if len(issues) >= MAX_VIOLATIONS_PER_CHECK:
                return issues
    return issues


def _iter_calls_excluding_nested_functions(node: ast.AST) -> Iterator[ast.Call]:
    for each_child in ast.iter_child_nodes(node):
        if isinstance(each_child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(each_child, ast.Call):
            yield each_child
            continue
        yield from _iter_calls_excluding_nested_functions(each_child)


def check_wrapper_plumb_through(content: str, file_path: str) -> list[str]:
    """Flag calls inside public functions that drop a same-file delegate's optional kwargs.

    Walks the AST. For every public function (name does not start with '_'),
    inspects every ast.Call inside its body and emits one finding per call
    whose target name matches a same-file function that exposes optional
    kwargs the enclosing public function does not also accept. Emission is
    capped at MAX_VIOLATIONS_PER_CHECK findings per call to run_gate.

    Limitations:
    - Only module-level FunctionDef nodes contribute signatures. Methods
      defined inside ClassDef bodies are ignored so cross-class same-name
      methods cannot overwrite a module-level delegate's signature index.
    - Methods defined inside ClassDef bodies are also skipped as wrapper
      candidates. A class method that calls a module-level delegate has a
      signature unrelated to that delegate's keyword-argument surface, so
      treating it as a wrapper produces false positives that flag every
      class method calling a free-function delegate with optional kwargs.
    - ast.Attribute calls match by attribute name only; the receiver type is
      not checked, so `self.fetch(...)` and `other.fetch(...)` both match a
      module-level `fetch` definition.
    - Nested call expressions inside another call's arguments are not treated as
      separate call sites; only the enclosing Call is inspected. This avoids
      false positives where a callee nested as an argument is confused with a
      top-level delegate invocation (for example `delegate(helper(x))`).
    """
    non_python_code_extensions = ALL_CODE_FILE_EXTENSIONS - {PYTHON_FILE_EXTENSION}
    lowercase_file_path = file_path.lower()
    if any(
        lowercase_file_path.endswith(each_extension)
        for each_extension in non_python_code_extensions
    ):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
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
    class_method_node_ids: set[int] = set()
    for each_class_def in ast.walk(tree):
        if not isinstance(each_class_def, ast.ClassDef):
            continue
        for each_class_body_node in each_class_def.body:
            if isinstance(
                each_class_body_node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                class_method_node_ids.add(id(each_class_body_node))
    issues: list[str] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if id(each_node) in class_method_node_ids:
            continue
        if each_node.name.startswith("_"):
            continue
        wrapper_kwargs = function_signatures.get(each_node.name, set())
        for each_call in _iter_calls_excluding_nested_functions(each_node):
            if isinstance(each_call.func, ast.Name):
                delegate_name = each_call.func.id
            elif isinstance(each_call.func, ast.Attribute):
                delegate_name = each_call.func.attr
            else:
                continue
            delegate_kwargs = function_signatures.get(delegate_name)
            if delegate_kwargs is None:
                continue
            missing = delegate_kwargs - wrapper_kwargs
            if missing:
                issues.append(
                    f"Line {each_node.lineno}: Wrapper {each_node.name!r} drops optional kwargs {sorted(missing)!r} of delegate {delegate_name!r}"
                )
                if len(issues) >= MAX_VIOLATIONS_PER_CHECK:
                    return issues
    return issues


def parse_added_line_numbers(unified_diff_text: str) -> set[int]:
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
    match_result = violation_line_pattern().match(violation_text)
    if match_result is None:
        return None
    return int(match_result.group(1))


def split_violations_by_scope(
    all_issues: list[str],
    all_added_line_numbers: set[int] | None,
) -> tuple[list[str], list[str]]:
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


def run_gate(
    validate_content: ValidateContentCallable,
    all_file_paths: list[Path],
    repository_root: Path,
    all_added_lines_by_path: dict[Path, set[int]] | None = None,
) -> int:
    blocking_by_file: dict[Path, list[str]] = {}
    advisory_by_file: dict[Path, list[str]] = {}
    for each_path in sorted(set(all_file_paths)):
        try:
            resolved = each_path.resolve()
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
        except (OSError, UnicodeDecodeError):
            print(f"code_rules_gate: skip unreadable {resolved}", file=sys.stderr)
            continue
        relative = resolved.relative_to(repository_root.resolve())
        relative_posix = str(relative).replace("\\", "/")
        prior_content = read_prior_committed_content(
            repository_root.resolve(), relative_posix
        )
        issues = validate_content(content, relative_posix, prior_content)
        issues.extend(
            check_database_column_string_magic(content, relative_posix)
        )
        issues.extend(check_wrapper_plumb_through(content, relative_posix))
        if not issues:
            continue
        added_for_file = (
            None
            if all_added_lines_by_path is None
            else all_added_lines_by_path.get(resolved)
        )
        blocking, advisory = split_violations_by_scope(issues, added_for_file)
        if blocking:
            blocking_by_file[resolved] = blocking
        if advisory:
            advisory_by_file[resolved] = advisory
    blocking_count = sum(len(each_list) for each_list in blocking_by_file.values())
    advisory_count = sum(len(each_list) for each_list in advisory_by_file.values())
    if blocking_count:
        if all_added_lines_by_path is None:
            header = f"code_rules_gate: {blocking_count} violation(s) reported."
        else:
            header = (
                f"code_rules_gate: {blocking_count} violation(s) "
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
                f"code_rules_gate: {advisory_count} pre-existing violation(s) "
                "in touched files (advisory, not blocking):"
            ),
            advisory_by_file,
            repository_root,
        )
    if blocking_count:
        return 1
    return 0


def parse_arguments(all_arguments: list[str]) -> argparse.Namespace:
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
