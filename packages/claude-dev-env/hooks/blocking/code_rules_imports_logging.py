"""Imports-at-top, import-block-sorted, logging f-string, win32gui None, E2E spec naming, file-length advisory, and library-print checks."""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_path_utils import (  # noqa: E402
    is_config_file,
)
from code_rules_shared import (  # noqa: E402
    get_file_extension,
    is_hook_infrastructure,
    is_spec_file,
    is_test_file,
)

from hooks_constants.blocking_check_limits import (  # noqa: E402
    ALL_IMPORT_BLOCK_SORT_RUFF_COMMAND_PREFIX,
    ALL_RUFF_STANDALONE_CONFIG_FILENAMES,
    IMPORT_BLOCK_SORT_RUFF_TIMEOUT_SECONDS,
    IMPORT_BLOCK_SORT_RULE_CODE,
    MAX_E2E_TEST_NAMING_ISSUES,
    MAX_IMPORT_BLOCK_SORT_ISSUES,
    MAX_LOGGING_FSTRING_ISSUES,
    MAX_WINDOWS_API_NONE_ISSUES,
    RUFF_PYPROJECT_CONFIG_FILENAME,
    RUFF_PYPROJECT_TOOL_TABLE_MARKER,
    RUFF_STDIN_ENCODING,
)
from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ADVISORY_LINE_THRESHOLD_HARD,
    ADVISORY_LINE_THRESHOLD_SOFT,
    ALL_CLI_FILE_PATH_MARKERS,
    ALL_IMPORT_STATEMENT_PREFIXES,
    ALL_PYTHON_EXTENSIONS,
    LOGGING_FSTRING_PATTERN,
    NOT_INSIDE_TYPE_CHECKING_BLOCK,
    TRIPLE_DOUBLE_QUOTE_DELIMITER,
    TRIPLE_QUOTE_PARITY_DIVISOR,
    TRIPLE_SINGLE_QUOTE_DELIMITER,
    TYPE_CHECKING_BLOCK_PATTERN,
)


def check_imports_at_top(content: str) -> list[str]:
    """Check for imports inside functions (Python only).

    An import lexically inside an ``if TYPE_CHECKING:`` block is exempt.
    An import inside a function body is flagged even if the file uses TYPE_CHECKING
    elsewhere at module scope.

    Only the innermost ``if TYPE_CHECKING:`` block is tracked: a second, nested
    ``if TYPE_CHECKING:`` header overwrites the outer block's indent so that when
    control dedents back to the outer block's body, the tracker resets.

    Known limitation: nested ``if TYPE_CHECKING:`` blocks are NOT supported. After
    a nested inner block ends, subsequent lines at the OUTER block's body indent
    are treated as outside any TYPE_CHECKING scope, so function-body imports there
    WILL be flagged as violations even though they are lexically guarded by the
    outer block. Rewrite to a single top-level ``if TYPE_CHECKING:`` block to avoid
    this false positive. Nested TYPE_CHECKING blocks are rare in practice, so this
    simpler single-level tracking is preferred over maintaining a stack of indent
    levels. The pinned behavior is covered by
    ``test_should_track_only_innermost_type_checking_block``.

    Triple-quoted-string interior lines are skipped. Once a line opens a
    multi-line triple-double-quote or triple-single-quote string (odd count
    of the delimiter), every subsequent line is treated as docstring content
    and exempt from the import-prefix scan until the matching delimiter
    closes the string. Without this tracking, docstring sentences that
    happen to start with ``from `` or ``import `` after stripping (a common
    pattern in narrative docstrings) would fire a false positive.
    """
    issues: list[str] = []
    lines = content.split("\n")
    is_inside_function = False
    function_indent = 0
    type_checking_block_indent = NOT_INSIDE_TYPE_CHECKING_BLOCK
    active_triple_quote_delimiter: str | None = None

    for each_line_number, each_line in enumerate(lines, 1):
        if active_triple_quote_delimiter is not None:
            active_triple_quote_delimiter = _update_triple_quote_state_for_line(
                each_line, active_triple_quote_delimiter
            )
            continue

        stripped = each_line.strip()

        if not stripped:
            continue

        current_indent = len(each_line) - len(each_line.lstrip())

        if type_checking_block_indent != NOT_INSIDE_TYPE_CHECKING_BLOCK:
            if current_indent <= type_checking_block_indent:
                type_checking_block_indent = NOT_INSIDE_TYPE_CHECKING_BLOCK

        type_checking_match = TYPE_CHECKING_BLOCK_PATTERN.match(each_line)
        if type_checking_match:
            type_checking_block_indent = len(type_checking_match.group("indent"))
            active_triple_quote_delimiter = _update_triple_quote_state_for_line(
                each_line, active_triple_quote_delimiter
            )
            continue

        function_match = re.match(r"^(\s*)(async\s+)?def\s+\w+", each_line)
        if function_match:
            is_inside_function = True
            function_indent = len(function_match.group(1)) if function_match.group(1) else 0
            active_triple_quote_delimiter = _update_triple_quote_state_for_line(
                each_line, active_triple_quote_delimiter
            )
            continue

        if is_inside_function:
            if current_indent <= function_indent and stripped and not stripped.startswith(("#", "@", ")")):
                is_inside_function = False

        is_inside_type_checking_block = type_checking_block_indent != NOT_INSIDE_TYPE_CHECKING_BLOCK
        if is_inside_function and not is_inside_type_checking_block:
            if stripped.startswith(ALL_IMPORT_STATEMENT_PREFIXES):
                issues.append(f"Line {each_line_number}: Import inside function - move to top of file")

        active_triple_quote_delimiter = _update_triple_quote_state_for_line(
            each_line, active_triple_quote_delimiter
        )

    return issues


def check_import_block_sorted(content: str, file_path: str) -> list[str]:
    """Flag a Python import block left un-sorted per isort rules (ruff I001).

    ruff/isort treats a contiguous run of ``import`` and ``from`` statements as
    one sortable unit. An edit that re-touches such a block pulls the whole block
    into the gate's scope, so a pre-existing mis-ordering in an untouched line of
    that block becomes a quality-gate failure (``check.ps1`` runs ruff over
    ``hooks/blocking``). This catches that drift at Write/Edit time by delegating
    to ruff itself, the same sorter the quality gate uses, so the two surfaces
    never disagree.

    The check resolves *file_path* to an absolute path and runs ruff against
    *content* on stdin under that path, so ruff walks parents to find the repo's
    ``[tool.ruff]`` config. Without a discoverable config ruff falls back to
    default isort first-party grouping, which orders sibling imports differently
    and produces false positives, so the check fails open when no ruff config is
    found above the file. Non-Python files and test files are exempt. When ruff
    is not installed, times out, or returns output the parser cannot read, the
    check also fails open and reports nothing — a missing or slow tool never
    blocks a write.

    Args:
        content: The full file content the Write or Edit would leave on disk.
        file_path: The destination path, used both to gate by extension and to
            give ruff the filename it needs for config discovery.

    Returns:
        One issue string per detected I001 finding, capped at
        ``MAX_IMPORT_BLOCK_SORT_ISSUES``; an empty list when the block sorts
        cleanly or the check fails open.
    """
    if get_file_extension(file_path) not in ALL_PYTHON_EXTENSIONS:
        return []
    if is_test_file(file_path):
        return []

    absolute_file_path = Path(file_path).resolve()
    if not _ruff_config_discoverable(absolute_file_path):
        return []

    ruff_findings = _run_ruff_import_sort_check(content, str(absolute_file_path))
    if ruff_findings is None:
        return []

    issues: list[str] = []
    for each_finding in ruff_findings:
        if each_finding.get("code") != IMPORT_BLOCK_SORT_RULE_CODE:
            continue
        line_number = _finding_line_number(each_finding.get("location"))
        issues.append(
            f"Line {line_number}: Import block is un-sorted (ruff I001) - "
            f"run 'ruff check --fix' to sort the block before writing"
        )
        if len(issues) >= MAX_IMPORT_BLOCK_SORT_ISSUES:
            break

    return issues


def _run_ruff_import_sort_check(content: str, file_path: str) -> list[dict[str, object]] | None:
    """Run ruff's I001 check over *content* and return its parsed JSON findings.

    Args:
        content: The file content fed to ruff on stdin.
        file_path: The filename ruff is told the stdin content belongs to, so it
            discovers the surrounding ``[tool.ruff]`` config.

    Returns:
        The list of ruff finding dictionaries, or ``None`` when ruff is absent,
        times out, or emits output that is not the expected JSON list.
    """
    ruff_command = [
        *ALL_IMPORT_BLOCK_SORT_RUFF_COMMAND_PREFIX,
        "--stdin-filename",
        file_path,
        "-",
    ]
    try:
        completed_process = subprocess.run(
            ruff_command,
            input=content.encode(RUFF_STDIN_ENCODING),
            capture_output=True,
            timeout=IMPORT_BLOCK_SORT_RUFF_TIMEOUT_SECONDS,
            check=False,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None

    try:
        ruff_stdout = completed_process.stdout.decode(RUFF_STDIN_ENCODING)
    except UnicodeDecodeError:
        return None

    try:
        parsed_findings = json.loads(ruff_stdout)
    except json.JSONDecodeError:
        return None

    if not isinstance(parsed_findings, list):
        return None
    return [each_finding for each_finding in parsed_findings if isinstance(each_finding, dict)]


def _ruff_config_discoverable(absolute_file_path: Path) -> bool:
    """Return whether a ruff config sits above *absolute_file_path*.

    Walks the file's parent directories looking for a standalone ``ruff.toml`` /
    ``.ruff.toml`` or a ``pyproject.toml`` that declares a ``[tool.ruff`` table.
    ruff uses this same nearest-ancestor walk to resolve its settings; mirroring
    it lets the check confirm ruff will see the project's isort configuration
    rather than its built-in defaults before trusting an I001 finding.

    Args:
        absolute_file_path: The resolved path of the file under validation.

    Returns:
        True when a ruff config is found in the file's directory or any ancestor;
        False when the walk reaches the filesystem root without one.
    """
    for each_directory in absolute_file_path.parents:
        for each_standalone_name in ALL_RUFF_STANDALONE_CONFIG_FILENAMES:
            if (each_directory / each_standalone_name).is_file():
                return True
        pyproject_path = each_directory / RUFF_PYPROJECT_CONFIG_FILENAME
        if _pyproject_declares_ruff_table(pyproject_path):
            return True
    return False


def _pyproject_declares_ruff_table(pyproject_path: Path) -> bool:
    """Return whether *pyproject_path* exists and declares a ``[tool.ruff`` table.

    Args:
        pyproject_path: The candidate ``pyproject.toml`` path to inspect.

    Returns:
        True when the file exists and its text contains the ``[tool.ruff`` table
        marker; False when the file is absent or unreadable.
    """
    if not pyproject_path.is_file():
        return False
    try:
        pyproject_text = pyproject_path.read_text(encoding=RUFF_STDIN_ENCODING)
    except OSError:
        return False
    return RUFF_PYPROJECT_TOOL_TABLE_MARKER in pyproject_text


def _finding_line_number(location: object) -> int:
    """Return the source line a ruff finding's location anchors to.

    Args:
        location: The ``location`` value from one ruff JSON finding, expected to
            be a mapping carrying an integer ``row``; any other shape yields a
            zero line number.

    Returns:
        The ``row`` value as an integer, or a zero line number when the location
        is absent or carries no readable row.
    """
    if not isinstance(location, dict):
        return 0
    row = location.get("row")
    if not isinstance(row, int):
        return 0
    return row


def _update_triple_quote_state_for_line(
    line_text: str, current_delimiter: str | None
) -> str | None:
    """Return the triple-quote delimiter that remains active after the line.

    Naively counts triple-double-quote and triple-single-quote occurrences.
    An odd count of either delimiter toggles the active state: ``None``
    becomes that delimiter, the same delimiter becomes ``None``. Even counts
    mean the line opens and closes the same delimiter in place (single-line
    docstring or balanced pair) and the active state is unchanged.

    Known limitation: the counter does not distinguish triple quotes that
    appear inside other string contexts (for example, a raw f-string
    containing the literal substring of triple quotes). Such constructs are
    rare in docstring-bearing code; the false-negative risk is acceptable
    to keep the line-walker simple and dependency-free.

    Args:
        line_text: The raw source line whose triple-quote balance is being
            integrated into the running state.
        current_delimiter: The active delimiter at the start of this line,
            or ``None`` when no multi-line string is open.

    Returns:
        The delimiter that remains active after this line, or ``None`` when
        no string is open.
    """
    if current_delimiter is not None:
        if line_text.count(current_delimiter) % TRIPLE_QUOTE_PARITY_DIVISOR == 1:
            return None
        return current_delimiter
    if line_text.count(TRIPLE_DOUBLE_QUOTE_DELIMITER) % TRIPLE_QUOTE_PARITY_DIVISOR == 1:
        return TRIPLE_DOUBLE_QUOTE_DELIMITER
    if line_text.count(TRIPLE_SINGLE_QUOTE_DELIMITER) % TRIPLE_QUOTE_PARITY_DIVISOR == 1:
        return TRIPLE_SINGLE_QUOTE_DELIMITER
    return None


def check_logging_fstrings(content: str) -> list[str]:
    """Check for f-strings in logging calls."""
    issues = []
    pattern = LOGGING_FSTRING_PATTERN

    maximum_issues = MAX_LOGGING_FSTRING_ISSUES
    for each_line_number, each_line in enumerate(content.split("\n"), 1):
        if pattern.search(each_line):
            issues.append(f"Line {each_line_number}: f-string in log call - use format args instead")

        if len(issues) >= maximum_issues:
            break

    return issues


def advise_file_line_count(content: str, file_path: str) -> None:
    """Emit non-blocking stderr advisories when a file crosses size smell thresholds.

    Thresholds are smell signals, not hard caps. See CODE_RULES.md "File length guidance"
    for rationale. Soft threshold aligns with Clean Code Chapter Five / Fowler "Large Class".
    Hard threshold matches pylint default max-module-lines and SonarQube S104 default.
    """
    line_count = len(content.splitlines())
    if line_count >= ADVISORY_LINE_THRESHOLD_HARD:
        print(
            f"[CODE_RULES advisory] {file_path}: {line_count} lines - "
            f"exceeds pylint/SonarQube default ({ADVISORY_LINE_THRESHOLD_HARD}); "
            f"strongly consider splitting by responsibility (SRP / cohesion)",
            file=sys.stderr,
        )
    elif line_count >= ADVISORY_LINE_THRESHOLD_SOFT:
        print(
            f"[CODE_RULES advisory] {file_path}: {line_count} lines - "
            f"consider splitting (Clean Code Ch. 5; Fowler 'Large Class' smell)",
            file=sys.stderr,
        )


def check_windows_api_none(content: str) -> list[str]:
    """Check for win32gui calls with None parameter."""
    issues = []
    pattern = re.compile(r"win32gui\.\w+\s*\([^)]*,\s*None\s*\)")

    maximum_issues = MAX_WINDOWS_API_NONE_ISSUES
    for each_line_number, each_line in enumerate(content.split("\n"), 1):
        if pattern.search(each_line):
            issues.append(f"Line {each_line_number}: win32gui call with None - use 0 for unused int params")

        if len(issues) >= maximum_issues:
            break

    return issues


def check_e2e_test_naming(content: str, file_path: str) -> list[str]:
    """Check for online/offline in test names (spec files only)."""
    if not is_spec_file(file_path):
        return []

    issues = []
    pattern = re.compile(r'(test|it|describe)\s*\(\s*["\'][^"\']*\b(online|offline)\b[^"\']*["\']', re.IGNORECASE)

    maximum_issues = MAX_E2E_TEST_NAMING_ISSUES
    for each_line_number, each_line in enumerate(content.split("\n"), 1):
        if pattern.search(each_line):
            issues.append(f"Line {each_line_number}: Test name contains online/offline - file scope defines this")

        if len(issues) >= maximum_issues:
            break

    return issues


def _is_cli_entry_point(file_path: str) -> bool:
    path_lower = file_path.lower().replace("\\", "/")
    return any(marker.replace("\\", "/") in path_lower for marker in ALL_CLI_FILE_PATH_MARKERS)


def check_library_print(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path) or is_config_file(file_path) or is_hook_infrastructure(file_path):
        return []
    if _is_cli_entry_point(file_path):
        return []
    if get_file_extension(file_path) not in ALL_PYTHON_EXTENSIONS:
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Call):
            continue
        function_reference = each_node.func
        if isinstance(function_reference, ast.Name) and function_reference.id == "print":
            issues.append(
                f"Line {each_node.lineno}: Library print() - route through logger or accept an explicit stream parameter"
            )
        elif isinstance(function_reference, ast.Attribute) and function_reference.attr == "write":
            value_node = function_reference.value
            if isinstance(value_node, ast.Attribute) and isinstance(value_node.value, ast.Name):
                if value_node.value.id == "sys" and value_node.attr in {"stdout", "stderr"}:
                    issues.append(
                        f"Line {each_node.lineno}: sys.{value_node.attr}.write - route through logger"
                    )
    return issues
