"""Imports-at-top, logging f-string, win32gui None, E2E spec naming, file-length advisory, and library-print checks."""

import ast
import re
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
    ALL_FORMAT_LOGGER_FUNCTION_NAMES,
    MAX_E2E_TEST_NAMING_ISSUES,
    MAX_LOGGING_FSTRING_ISSUES,
    MAX_LOGGING_PRINTF_TOKEN_ISSUES,
    MAX_WINDOWS_API_NONE_ISSUES,
)
from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ADVISORY_LINE_THRESHOLD_HARD,
    ADVISORY_LINE_THRESHOLD_SOFT,
    ALL_CLI_FILE_PATH_MARKERS,
    ALL_IMPORT_STATEMENT_PREFIXES,
    ALL_PYTHON_EXTENSIONS,
    LOGGING_FSTRING_PATTERN,
    LOGGING_PRINTF_TOKEN_PATTERN,
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


def _format_logger_names_imported(tree: ast.Module) -> set[str]:
    """Return the local names bound to automation_logging log helpers.

    Scans every ``from ... import ...`` statement for an import whose module
    path contains ``automation_logging`` and collects the local binding of each
    imported ``log_*`` helper (the alias when ``as`` is present, otherwise the
    imported name). Only these names identify a str.format-logger call; a
    ``log_*`` helper from any other module is not collected, because a
    ``%``-style logger formats its tokens correctly.

    Args:
        tree: The parsed module to scan for logger imports.

    Returns:
        The set of local names bound to automation_logging log helpers.
    """
    bound_names: set[str] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.ImportFrom):
            continue
        if each_node.module is None or "automation_logging" not in each_node.module:
            continue
        for each_alias in each_node.names:
            if each_alias.name in ALL_FORMAT_LOGGER_FUNCTION_NAMES:
                bound_names.add(each_alias.asname or each_alias.name)
    return bound_names


def _printf_token_log_call_line(
    node: ast.AST, all_format_logger_names: set[str]
) -> int | None:
    """Return the line of a format-logger call carrying a printf token, else None.

    Args:
        node: The AST node to inspect.
        all_format_logger_names: Local names bound to automation_logging log
            helpers.

    Returns:
        The 1-based line number when ``node`` is a bare-name call to a format
        logger whose first string-literal argument carries a printf token;
        otherwise None.
    """
    if not isinstance(node, ast.Call):
        return None
    function_reference = node.func
    if (
        not isinstance(function_reference, ast.Name)
        or function_reference.id not in all_format_logger_names
    ):
        return None
    if not node.args:
        return None
    message_argument = node.args[0]
    if not isinstance(message_argument, ast.Constant) or not isinstance(
        message_argument.value, str
    ):
        return None
    if not LOGGING_PRINTF_TOKEN_PATTERN.search(message_argument.value):
        return None
    return node.lineno


def check_logging_printf_tokens(content: str, file_path: str) -> list[str]:
    """Flag printf tokens in a str.format-logger (automation_logging) message.

    The ``shared_utils.automation_logging`` helpers (``log_info``, ``log_error``,
    ...) format with ``str.format`` (``{}`` placeholders), so a printf-style
    token such as ``%s`` in the message literal is never substituted: the
    arguments are dropped and the literal token prints. The check fires only in a
    file that imports one of those helpers from an ``automation_logging`` module,
    and only for a bare-name call to such a helper whose first argument is a
    string literal carrying a token. An attribute call (``logger.info``) or a
    ``log_*`` helper from any other module formats ``%``-tokens correctly and is
    left alone. Test files are exempt so a test may exercise the malformed shape.

    Args:
        content: The Python source under validation.
        file_path: The destination path, used to skip test files and non-Python.

    Returns:
        One issue line per offending call, capped at the configured maximum.
    """
    if is_test_file(file_path):
        return []
    if get_file_extension(file_path) not in ALL_PYTHON_EXTENSIONS:
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    all_format_logger_names = _format_logger_names_imported(tree)
    if not all_format_logger_names:
        return []
    issues: list[str] = []
    for each_node in ast.walk(tree):
        offending_line = _printf_token_log_call_line(each_node, all_format_logger_names)
        if offending_line is None:
            continue
        issues.append(
            f"Line {offending_line}: printf token in a str.format logger "
            "message - the automation_logging helpers format with str.format; "
            "use {} placeholders (the %-arguments are silently dropped)"
        )
        if len(issues) >= MAX_LOGGING_PRINTF_TOKEN_ISSUES:
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
