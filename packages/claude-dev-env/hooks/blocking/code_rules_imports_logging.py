"""Imports-at-top, import-block-sorted, logging f-string, win32gui None, naive datetime construction, E2E spec naming, JS resume-task enumeration coverage, JS returns-object schema-less branch, JS sibling return-object key drift, file-length advisory, and library-print checks."""

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
    _scope_violations_to_changed_lines,
    get_file_extension,
    is_hook_infrastructure,
    is_spec_file,
    is_test_file,
)

from hooks_constants.blocking_check_limits import (  # noqa: E402
    ALL_ALWAYS_NAIVE_DATETIME_CONSTRUCTORS,
    ALL_FORMAT_LOGGER_FUNCTION_NAMES,
    ALL_IMPORT_BLOCK_SORT_RUFF_COMMAND_PREFIX,
    ALL_RUFF_STANDALONE_CONFIG_FILENAMES,
    DATETIME_CLASS_ATTRIBUTE_NAME,
    FROMTIMESTAMP_POSITIONAL_TIMEZONE_ARGUMENT_COUNT,
    IMPORT_BLOCK_SORT_RUFF_TIMEOUT_SECONDS,
    IMPORT_BLOCK_SORT_RULE_CODE,
    MAX_E2E_TEST_NAMING_ISSUES,
    MAX_IMPORT_BLOCK_SORT_ISSUES,
    MAX_JS_RESUME_TASK_ENUMERATION_ISSUES,
    MAX_JS_RETURNS_OBJECT_SCHEMALESS_ISSUES,
    MAX_JS_SIBLING_RETURN_OBJECT_KEY_DRIFT_ISSUES,
    MAX_LOGGING_FSTRING_ISSUES,
    MAX_LOGGING_PRINTF_TOKEN_ISSUES,
    MAX_NAIVE_DATETIME_ISSUES,
    MAX_WINDOWS_API_NONE_ISSUES,
    MINIMUM_RESUME_TASK_ENUMERATION_ITEMS,
    MINIMUM_SIBLING_RETURN_OBJECT_KEYS,
    NAIVE_DATETIME_FROMTIMESTAMP_CONSTRUCTOR,
    NAIVE_DATETIME_TIMEZONE_KEYWORD,
    NAIVE_DATETIME_UTCFROMTIMESTAMP_CONSTRUCTOR,
    NAIVE_DATETIME_UTCNOW_CONSTRUCTOR,
    RUFF_PYPROJECT_CONFIG_FILENAME,
    RUFF_PYPROJECT_TOOL_TABLE_MARKER,
    RUFF_STDIN_ENCODING,
    SIBLING_RETURN_OBJECT_EXACT_MISSING_KEY_COUNT,
)
from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ADVISORY_LINE_THRESHOLD_HARD,
    ADVISORY_LINE_THRESHOLD_SOFT,
    ALL_CLI_FILE_PATH_MARKERS,
    ALL_IMPORT_STATEMENT_PREFIXES,
    ALL_JAVASCRIPT_BARE_RETURN_TYPE_EXTRA_CHARACTERS,
    ALL_JAVASCRIPT_BRACKET_CLOSERS,
    ALL_JAVASCRIPT_BRACKET_OPENERS,
    ALL_JAVASCRIPT_CONTROL_FLOW_BLOCK_KEYWORDS,
    ALL_JAVASCRIPT_EXTENSIONS,
    ALL_JAVASCRIPT_IDENTIFIER_EXTRA_CHARACTERS,
    ALL_JAVASCRIPT_PARENTHESIS_FREE_BLOCK_KEYWORDS,
    ALL_JAVASCRIPT_REGEX_PRECEDING_CHARACTERS,
    ALL_JAVASCRIPT_REGEX_PRECEDING_KEYWORDS,
    ALL_JAVASCRIPT_RETURN_TYPE_TERMINATORS,
    ALL_JAVASCRIPT_STRING_DELIMITERS,
    ALL_PYTHON_EXTENSIONS,
    ARROW_CONCISE_BODY_OBJECT_LITERAL_OPENING_PATTERN,
    ENUMERATION_LEADING_CONJUNCTION_PATTERN,
    ENUMERATION_LIST_ITEM_SEPARATOR_PATTERN,
    ENUMERATION_TASK_ITEM_PATTERN,
    FUNCTION_WITH_JSDOC_PATTERN,
    HYPHENATED_TASK_ITEM_PATTERN,
    JAVASCRIPT_ARROW_TOKEN_LENGTH,
    JAVASCRIPT_BLOCK_COMMENT_CLOSER,
    JAVASCRIPT_BLOCK_COMMENT_OPENER,
    JAVASCRIPT_LINE_COMMENT_OPENER,
    JAVASCRIPT_MODULE_SCOPE_SENTINEL,
    JAVASCRIPT_OBJECT_SPREAD_PREFIX,
    JAVASCRIPT_REGEX_DELIMITER,
    JAVASCRIPT_STRING_ESCAPE_CHARACTER,
    JS_OBJECT_KEY_IDENTIFIER_PATTERN,
    JS_OBJECT_METHOD_SHORTHAND_KEY_PATTERN,
    JSDOC_RETURNS_STRUCTURED_OBJECT_PROMISE_PATTERN,
    LOGGING_FSTRING_PATTERN,
    LOGGING_PRINTF_TOKEN_PATTERN,
    MINIMUM_FORMAT_LOGGER_ARGUMENT_COUNT,
    NOT_INSIDE_TYPE_CHECKING_BLOCK,
    RESUME_TASK_ENUMERATION_PATTERN,
    RETURN_CALL_OPENING_PARENTHESIS_PATTERN,
    RETURN_OBJECT_LITERAL_OPENING_PATTERN,
    SCHEMA_OPTIONS_PROPERTY_KEY_PATTERN,
    SPAWN_AGENT_WITH_JSDOC_PATTERN,
    TASK_DISPATCH_NAME_PATTERN,
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


def check_import_block_sorted(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
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

    An I001 finding covers the whole sortable block, so each finding carries a
    span from the block's anchor line (``location.row``) through its last line
    (``end_location.row``) scoped through the shared
    ``_scope_violations_to_changed_lines`` helper. On a terminal diff-scoped Edit
    a finding is returned when any line in that block span is among
    ``all_changed_lines``, so an edit touching any line of an unsorted block
    blocks while an edit far from the block does not. On a new-file or full-file
    write (``all_changed_lines`` None) every finding is in scope;
    ``defer_scope_to_caller`` returns every finding so the commit/push gate
    scopes by added line through its own ``Line N:`` partitioning.

    Args:
        content: The full file content the Write or Edit would leave on disk.
        file_path: The destination path, used both to gate by extension and to
            give ruff the filename it needs for config discovery.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a finding
            blocks only when its block-anchor line is among the changed lines.
        defer_scope_to_caller: When True, return every finding so the commit/push
            gate's ``Line N:`` partitioning scopes by added line.

    Returns:
        One issue string per detected I001 finding, capped at
        ``MAX_IMPORT_BLOCK_SORT_ISSUES``; an empty list when the block sorts
        cleanly, every finding falls outside the changed lines, or the check
        fails open.
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

    span_end_line_offset = 1
    all_violations_in_finding_order: list[tuple[range, str]] = []
    for each_finding in ruff_findings:
        if each_finding.get("code") != IMPORT_BLOCK_SORT_RULE_CODE:
            continue
        line_number = _finding_line_number(each_finding.get("location"))
        block_end_line_number = _finding_block_end_line_number(
            each_finding.get("end_location"), line_number
        )
        span_range = range(line_number, block_end_line_number + span_end_line_offset)
        message = (
            f"Line {line_number}: Import block is un-sorted (ruff I001) - "
            f"run 'ruff check --fix' to sort the block before writing"
        )
        all_violations_in_finding_order.append((span_range, message))
        if len(all_violations_in_finding_order) >= MAX_IMPORT_BLOCK_SORT_ISSUES:
            break

    return _scope_violations_to_changed_lines(
        all_violations_in_finding_order,
        all_changed_lines,
        defer_scope_to_caller,
    )


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


def _finding_block_end_line_number(end_location: object, anchor_line_number: int) -> int:
    """Return the last source line a ruff finding's block spans.

    ruff anchors an I001 finding at its block's first line and records the
    block's last line in ``end_location.row``, so the two together bound the
    whole sortable run. The end row falls back to the anchor line when the
    ``end_location`` is absent or carries no readable row, or when it would land
    above the anchor — keeping the span to at least the anchor line itself.

    Args:
        end_location: The ``end_location`` value from one ruff JSON finding,
            expected to be a mapping carrying an integer ``row``.
        anchor_line_number: The finding's block-anchor line, used as the floor
            for the returned end line.

    Returns:
        The block's last line as an integer, never below *anchor_line_number*.
    """
    if not isinstance(end_location, dict):
        return anchor_line_number
    row = end_location.get("row")
    if not isinstance(row, int) or row < anchor_line_number:
        return anchor_line_number
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
        logger that has at least one format argument after the message and
        whose first string-literal argument carries a printf token; otherwise
        None. A call with only the message and no format arguments never runs
        ``.format(*args)``, so its token prints intact and is not flagged.
    """
    if not isinstance(node, ast.Call):
        return None
    function_reference = node.func
    if (
        not isinstance(function_reference, ast.Name)
        or function_reference.id not in all_format_logger_names
    ):
        return None
    if len(node.args) < MINIMUM_FORMAT_LOGGER_ARGUMENT_COUNT:
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
    ...) format with ``str.format`` (``{}`` placeholders) only when format
    arguments follow the message (``message.format(*args) if args else
    message``), so a printf-style token such as ``%s`` in the message literal is
    never substituted: the format arguments are dropped and the literal token
    prints. The check fires only in a file that imports one of those helpers
    from an ``automation_logging`` module, and only for a bare-name call to such
    a helper that passes at least one format argument after the message and
    whose first argument is a string literal carrying a token. A call with only
    the message and no format arguments never runs ``.format``, so its token
    prints intact and is left alone. An attribute call (``logger.info``) or a
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


def _attribute_base_is_datetime(attribute_node: ast.Attribute) -> bool:
    """Report whether an attribute access hangs off the ``datetime`` class.

    Covers both import forms: ``datetime.fromtimestamp`` (from
    ``from datetime import datetime``) where the base is a plain name, and
    ``datetime.datetime.fromtimestamp`` (from ``import datetime``) where the base
    is itself a ``.datetime`` attribute access.

    Args:
        attribute_node: The attribute access whose base is examined.

    Returns:
        True when the base resolves to the ``datetime`` class, else False.
    """
    base_node = attribute_node.value
    if isinstance(base_node, ast.Name):
        return base_node.id == DATETIME_CLASS_ATTRIBUTE_NAME
    if isinstance(base_node, ast.Attribute):
        inner_base = base_node.value
        return (
            base_node.attr == DATETIME_CLASS_ATTRIBUTE_NAME
            and isinstance(inner_base, ast.Name)
            and inner_base.id == DATETIME_CLASS_ATTRIBUTE_NAME
        )
    return False


def _is_literal_none(node: ast.expr) -> bool:
    """Report whether an expression is the literal ``None``.

    A ``None`` timezone argument leaves a datetime naive, so it does not count as
    a supplied zone.

    Args:
        node: The argument expression to inspect.

    Returns:
        True when the node is a literal ``None``, else False.
    """
    return isinstance(node, ast.Constant) and node.value is None


def _fromtimestamp_supplies_concrete_timezone(call_node: ast.Call) -> bool:
    """Report whether a ``fromtimestamp`` call pins a real timezone.

    The zone arrives either as a ``tz=`` keyword or as the second positional
    argument, matching the ``datetime.fromtimestamp(timestamp, tz=None)``
    signature. A literal ``None`` in either slot leaves the value naive and does
    not count.

    Args:
        call_node: The ``fromtimestamp`` call to inspect.

    Returns:
        True when a concrete (non-None) timezone is supplied, else False.
    """
    for each_keyword in call_node.keywords:
        if each_keyword.arg == NAIVE_DATETIME_TIMEZONE_KEYWORD:
            return not _is_literal_none(each_keyword.value)
    if len(call_node.args) >= FROMTIMESTAMP_POSITIONAL_TIMEZONE_ARGUMENT_COUNT:
        return not _is_literal_none(call_node.args[1])
    return False


def _naive_datetime_constructor_name(call_node: ast.Call) -> str | None:
    """Return the naive datetime constructor a call uses, or None when it is safe.

    ``utcnow`` and ``utcfromtimestamp`` always build a naive datetime — neither
    accepts a ``tz`` argument, so any such call is flagged. ``fromtimestamp``
    builds a naive datetime only when no timezone pins the zone; a concrete
    timezone counts when supplied as a ``tz=`` keyword or as a second positional
    argument (``datetime.fromtimestamp(stamp, timezone.utc)``), while a literal
    ``None`` in either slot still yields a naive value. Any other call is safe and
    returns None.

    Args:
        call_node: The call expression to classify.

    Returns:
        The constructor name when the call builds a naive datetime, else None.
    """
    call_function = call_node.func
    if not isinstance(call_function, ast.Attribute):
        return None
    if not _attribute_base_is_datetime(call_function):
        return None
    constructor_name = call_function.attr
    if constructor_name in ALL_ALWAYS_NAIVE_DATETIME_CONSTRUCTORS:
        return constructor_name
    if constructor_name != NAIVE_DATETIME_FROMTIMESTAMP_CONSTRUCTOR:
        return None
    if _fromtimestamp_supplies_concrete_timezone(call_node):
        return None
    return constructor_name


def _naive_datetime_remediation(constructor_name: str) -> str:
    """Return the fix guidance for a specific naive datetime constructor.

    ``utcnow`` and ``utcfromtimestamp`` accept no ``tz`` argument, so each points
    at its aware replacement (``datetime.now(tz=...)`` and
    ``datetime.fromtimestamp(..., tz=...)``); ``fromtimestamp`` keeps its shape and
    only needs a ``tz=`` argument.

    Args:
        constructor_name: The naive constructor the call used.

    Returns:
        The remediation clause to embed in the emitted issue.
    """
    if constructor_name == NAIVE_DATETIME_UTCNOW_CONSTRUCTOR:
        return "use datetime.now(tz=timezone.utc)"
    if constructor_name == NAIVE_DATETIME_UTCFROMTIMESTAMP_CONSTRUCTOR:
        return "use datetime.fromtimestamp(..., tz=timezone.utc)"
    return "pass tz= (e.g. tz=timezone.utc)"


def check_naive_datetime_construction(content: str, file_path: str) -> list[str]:
    """Flag naive datetime constructors that invite DST-fold ambiguity.

    ``datetime.fromtimestamp(epoch)`` and ``datetime.utcfromtimestamp(epoch)``
    build a datetime with no timezone, and ``datetime.utcnow()`` does the same for
    the current moment. A later ``.astimezone()`` on that naive value guesses the
    local offset, so a timestamp landing in a daylight-saving fold reads back an
    hour off. The aware replacements differ by constructor: ``fromtimestamp`` takes
    a ``tz=`` keyword or a second positional timezone (``datetime.fromtimestamp(
    stamp, timezone.utc)``); ``utcnow`` becomes ``datetime.now(tz=timezone.utc)``;
    and ``utcfromtimestamp`` becomes ``datetime.fromtimestamp(stamp,
    tz=timezone.utc)`` — neither ``utc`` constructor accepts a ``tz`` argument. A
    plain ``datetime.now()`` is left alone, since it does not derive an instant from
    an epoch value.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per naive datetime constructor, capped at the module limit.
    """
    if is_test_file(file_path):
        return []
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in ast.walk(parsed_tree):
        if not isinstance(each_node, ast.Call):
            continue
        naive_constructor_name = _naive_datetime_constructor_name(each_node)
        if naive_constructor_name is None:
            continue
        remediation = _naive_datetime_remediation(naive_constructor_name)
        issues.append(
            f"Line {each_node.lineno}: naive datetime.{naive_constructor_name}() - "
            f"{remediation} so the instant is unambiguous; call .astimezone() only "
            "when local display is needed (avoids DST-fold ambiguity)"
        )
        if len(issues) >= MAX_NAIVE_DATETIME_ISSUES:
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


class _JavaScriptRegionScanner:
    """Walks JavaScript source one character at a time, tracking string,
    comment, and regex regions so a caller can tell code from non-code.

    The scanner holds the region the current character sits in. ``consume``
    advances the state for one character and returns whether that character is
    structural code (``True``) or part of a string, comment, or regex literal
    (``False``).
    """

    def __init__(self) -> None:
        self._active_string_delimiter: str | None = None
        self._is_inside_line_comment = False
        self._is_inside_block_comment = False
        self._is_inside_regex_literal = False
        self._previous_code_character = "\n"
        self._previous_code_word = ""
        self._is_building_code_word = False

    def consume(self, character: str, source: str, index: int) -> bool:
        if self._active_string_delimiter is not None:
            return self._consume_inside_string(character, source, index)
        if self._is_inside_line_comment:
            return self._consume_inside_line_comment(character)
        if self._is_inside_block_comment:
            return self._consume_inside_block_comment(source, index)
        if self._is_inside_regex_literal:
            return self._consume_inside_regex(character, source, index)
        return self._consume_inside_code(character, source, index)

    def _consume_inside_string(self, character: str, source: str, index: int) -> bool:
        if character == self._active_string_delimiter and not _is_escaped(source, index):
            self._active_string_delimiter = None
        return False

    def _consume_inside_line_comment(self, character: str) -> bool:
        if character == "\n":
            self._is_inside_line_comment = False
        return False

    def _consume_inside_block_comment(self, source: str, index: int) -> bool:
        if source[index - 1 : index + 1] == JAVASCRIPT_BLOCK_COMMENT_CLOSER:
            self._is_inside_block_comment = False
        return False

    def _consume_inside_regex(self, character: str, source: str, index: int) -> bool:
        if character == JAVASCRIPT_REGEX_DELIMITER and not _is_escaped(source, index):
            self._is_inside_regex_literal = False
        return False

    def _consume_inside_code(self, character: str, source: str, index: int) -> bool:
        if character in ALL_JAVASCRIPT_STRING_DELIMITERS:
            self._active_string_delimiter = character
            return False
        if source.startswith(JAVASCRIPT_LINE_COMMENT_OPENER, index):
            self._is_inside_line_comment = True
            return False
        if source.startswith(JAVASCRIPT_BLOCK_COMMENT_OPENER, index):
            self._is_inside_block_comment = True
            return False
        if character == JAVASCRIPT_REGEX_DELIMITER and self._is_regex_start():
            self._is_inside_regex_literal = True
            return False
        self._track_preceding_word(character)
        if not character.isspace():
            self._previous_code_character = character
        return True

    def _track_preceding_word(self, character: str) -> None:
        if character.isalnum() or character == "_":
            if not self._is_building_code_word:
                self._previous_code_word = ""
                self._is_building_code_word = True
            self._previous_code_word += character
            return
        if not character.isspace():
            self._previous_code_word = ""
        self._is_building_code_word = False

    def _is_regex_start(self) -> bool:
        if self._previous_code_character in ALL_JAVASCRIPT_REGEX_PRECEDING_CHARACTERS:
            return True
        return self._previous_code_word in ALL_JAVASCRIPT_REGEX_PRECEDING_KEYWORDS


def _is_escaped(source: str, index: int) -> bool:
    backslash_run_length = 0
    scan_index = index - 1
    while scan_index >= 0 and source[scan_index] == JAVASCRIPT_STRING_ESCAPE_CHARACTER:
        backslash_run_length += 1
        scan_index -= 1
    return backslash_run_length % 2 == 1


def _code_position_flags(source: str) -> list[bool]:
    """Return one flag per character: ``True`` for structural code, ``False`` for
    a character inside a string literal, comment, or regex literal.

    A backslash escapes the next character inside a string literal, so a delimiter
    preceded by an odd run of backslashes stays inside the literal and a delimiter
    preceded by an even run (including zero) closes it. A ``/`` opens a regex
    literal only when it sits at an expression position: either the previous
    structural character is a punctuation/operator that precedes an expression, or
    the preceding identifier token is an expression-introducing keyword (``return``,
    ``typeof``, ``case``, ``in``, ``of``, ``do``, ``else``, ``void``, ``delete``,
    ``instanceof``, ``new``, ``yield``, ``await``, ``throw``). After a value it is
    the division operator and is left intact.
    """
    region = _JavaScriptRegionScanner()
    return [
        region.consume(each_character, source, each_index)
        for each_index, each_character in enumerate(source)
    ]


def _blank_non_code_regions(body_text: str) -> str:
    """Replace every non-code region in JavaScript source with spaces.

    A non-code region is a string literal (single-, double-, or backtick-quoted),
    a ``//`` line comment, a ``/* */`` block comment, or a ``/.../`` regex
    literal. Each is blanked to spaces, newlines preserved, so the returned text
    has the same length and line structure as the input while carrying only
    structural code characters.

    Blanking comments and regex literals keeps a stray brace inside either from
    skewing the brace-depth scan that bounds the resume body, and blanking string
    literals keeps a brace inside a prompt string from skewing it the same way.
    """
    code_flags = _code_position_flags(body_text)
    rendered_characters = [
        each_character if (code_flags[each_index] or each_character == "\n") else " "
        for each_index, each_character in enumerate(body_text)
    ]
    return "".join(rendered_characters)


def _dispatched_task_names(resume_body: str) -> set[str]:
    """Return the task names the resume body dispatches on in code position.

    A real dispatch branch (``task === 'fix-verify'``) has its ``task`` keyword in
    structural code; a ``task === '<name>'`` mention inside an agent-prompt string,
    a comment, or a regex literal is prose and its keyword sits in a non-code
    region. Only a match whose ``task`` keyword is at a code position counts, so a
    prose mention is never read as a dispatch branch.
    """
    code_flags = _code_position_flags(resume_body)
    dispatched_tasks: set[str] = set()
    for each_match in TASK_DISPATCH_NAME_PATTERN.finditer(resume_body):
        if code_flags[each_match.start()]:
            dispatched_tasks.add(each_match.group("task"))
    return dispatched_tasks


def _balanced_brace_body(content: str, from_index: int) -> str | None:
    """Return the brace-balanced span of ``content`` starting at the first ``{``.

    Braces inside string literals, comments, and regex literals do not count
    toward the depth: the scan walks a blanked copy where those regions are
    spaces, so only structural braces move the depth. The returned span is a slice
    of the original ``content`` so the caller reads real source for the dispatch
    scan.
    """
    blanked_content = _blank_non_code_regions(content)
    opening_index = blanked_content.find("{", from_index)
    if opening_index == -1:
        return None
    depth = 0
    for each_position in range(opening_index, len(blanked_content)):
        character = blanked_content[each_position]
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
            if depth == 0:
                return content[opening_index : each_position + 1]
    return content[opening_index:]


def _resume_function_body(content: str, role: str) -> str | None:
    header_pattern = re.compile(
        r"(?:async\s+)?function\s+resume" + re.escape(role) + r"Agent\s*\("
    )
    header_match = header_pattern.search(_blank_non_code_regions(content))
    if header_match is None:
        return None
    bounded_content = content[: _next_top_level_function_index(content, header_match.end())]
    return _balanced_brace_body(bounded_content, header_match.end())


def _next_top_level_function_index(content: str, from_index: int) -> int:
    blanked_content = _blank_non_code_regions(content)
    next_function_match = re.compile(
        r"^(?:async\s+)?function\s+\w+", re.MULTILINE
    ).search(blanked_content, from_index)
    if next_function_match is None:
        return len(content)
    return next_function_match.start()


def _task_list_from_enumeration_text(
    enumeration_text: str, all_dispatched_tasks: frozenset[str]
) -> set[str] | None:
    enumerated_items = ENUMERATION_LIST_ITEM_SEPARATOR_PATTERN.split(enumeration_text)
    task_items = {_strip_leading_conjunction(each_item) for each_item in enumerated_items}
    if not all(ENUMERATION_TASK_ITEM_PATTERN.match(each_item) for each_item in task_items):
        return None
    if not any(HYPHENATED_TASK_ITEM_PATTERN.match(each_item) for each_item in task_items):
        return None
    if len(task_items) < MINIMUM_RESUME_TASK_ENUMERATION_ITEMS and not (task_items & all_dispatched_tasks):
        return None
    return task_items


def _strip_leading_conjunction(enumeration_item: str) -> str:
    stripped_item = enumeration_item.strip()
    return ENUMERATION_LEADING_CONJUNCTION_PATTERN.sub("", stripped_item).strip()


def _enumeration_task_names(
    jsdoc_text: str, all_dispatched_tasks: frozenset[str]
) -> set[str] | None:
    for each_enumeration_match in RESUME_TASK_ENUMERATION_PATTERN.finditer(jsdoc_text):
        enumeration_text = each_enumeration_match.group("enumeration").replace("*", " ")
        task_items = _task_list_from_enumeration_text(enumeration_text, all_dispatched_tasks)
        if task_items is not None:
            return task_items
    return None


def check_js_resume_task_enumeration_coverage(
    content: str, file_path: str
) -> list[str]:
    """Flag a spawn JSDoc whose resume enumeration omits a dispatched task.

    The drift this catches: a ``spawn<Role>Agent`` function carries a JSDoc that
    enumerates the resume tasks of its sibling ``resume<Role>Agent`` in a
    parenthetical ``resume (repair-verify, hardening-verify)`` list, while the
    ``resume<Role>Agent`` body dispatches on a ``task === '<name>'`` branch the
    enumeration never names. A reader who trusts the spawn JSDoc to list every
    step that runs on the session misses the omitted task. This is the JS/.mjs
    slice of Category O6 docstring-prose-vs-implementation drift; the Python
    enforcer's AST docstring checks never inspect JavaScript source.

    A spawn JSDoc binds to its sibling resume function by the shared ``<Role>``
    token (``spawnVerifierAgent`` pairs with ``resumeVerifierAgent``). The check
    reads the sibling resume body's dispatched task set first, then scans each
    standalone-word ``resume (...)`` parenthetical in the JSDoc (a longer word
    ending in ``resume``, such as ``presume (...)``, does not introduce an
    enumeration) and binds to the first that reads as a task list: every comma- or
    ``and``-delimited item (including the Oxford-comma ``a, b, and c`` form, where
    the trailing ``and`` is stripped from the final item) is a single
    dispatch-shaped task token (no embedded spaces, so a descriptive phrase such as
    ``re-establishing the session`` is not a task list, and a later real task list
    still binds when an earlier descriptive parenthetical precedes it) and at least
    one item is hyphenated, proving the prose is a resume-task enumeration
    describing the sibling rather than incidental prose. A multi-item parenthetical
    that clears those gates is a task list. A single-item parenthetical clears them
    only when its lone token is itself one of the sibling's dispatched tasks, so a
    descriptive single hyphenated word such as ``re-entry`` or ``fast-forward`` —
    which names no dispatched task — stays descriptive prose rather than a
    one-item task list. This keeps the enumerated token set a superset of the
    sibling's dispatched task set. The resume body is read up to the next
    top-level ``function`` declaration, and only a ``task === '<name>'`` whose
    ``task`` keyword sits in structural code counts as a dispatch branch: a
    ``task === '<name>'`` mention inside a string literal (any quote flavor), a
    comment, or a regex literal is prose and is skipped. Each
    ``task === '<name>'`` branch name the resume body dispatches on that the
    enumeration omits is flagged.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per dispatched task name the spawn enumeration omits, capped at
        the module limit.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []
    if get_file_extension(file_path) not in ALL_JAVASCRIPT_EXTENSIONS:
        return []
    issues: list[str] = []
    for each_spawn_match in SPAWN_AGENT_WITH_JSDOC_PATTERN.finditer(content):
        role = each_spawn_match.group("role")
        resume_body = _resume_function_body(content, role)
        if resume_body is None:
            continue
        dispatched_tasks = _dispatched_task_names(resume_body)
        enumerated_tasks = _enumeration_task_names(
            each_spawn_match.group("jsdoc"), frozenset(dispatched_tasks)
        )
        if not enumerated_tasks:
            continue
        for each_task in sorted(dispatched_tasks - enumerated_tasks):
            issues.append(
                f"spawn{role}Agent() JSDoc resume enumeration omits the "
                f"'{each_task}' task that resume{role}Agent dispatches on — add it "
                "to the parenthetical (Category O6 docstring-vs-implementation drift)"
            )
            if len(issues) >= MAX_JS_RESUME_TASK_ENUMERATION_ISSUES:
                return issues[:MAX_JS_RESUME_TASK_ENUMERATION_ISSUES]
    return issues[:MAX_JS_RESUME_TASK_ENUMERATION_ISSUES]


def _parameter_list_end_index(blanked_content: str, after_open_parenthesis_index: int) -> int:
    """Return the index just past the ``)`` that closes an opened parameter list.

    ``after_open_parenthesis_index`` sits just past the opening ``(``, so the scan
    starts one level deep and walks paren-balanced. A nested ``(`` inside the list
    — a default-value call, a destructure default — does not close the list early.
    """
    depth = 1
    for each_position in range(after_open_parenthesis_index, len(blanked_content)):
        character = blanked_content[each_position]
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return each_position + 1
    return len(blanked_content)


def _javascript_function_body(content: str, header_end_index: int) -> str | None:
    """Return the brace-balanced body of the function whose header ends at the index.

    ``header_end_index`` sits just past the opening ``(`` of the parameter list, so
    the scan advances past the paren-balanced parameter list before finding the body
    brace. A destructured parameter (``function f({ ... }) { ... }``) opens a brace
    inside that list; the body brace is the first ``{`` after the list closes, not
    the destructure brace.
    """
    body_search_index = _parameter_list_end_index(
        _blank_non_code_regions(content), header_end_index
    )
    bounded_content = content[: _next_top_level_function_index(content, body_search_index)]
    return _balanced_brace_body(bounded_content, body_search_index)


def _balanced_parenthesis_span(blanked_content: str, opening_index: int) -> str:
    """Return the paren-balanced slice of blanked source starting at an opening ``(``."""
    depth = 0
    for each_position in range(opening_index, len(blanked_content)):
        character = blanked_content[each_position]
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
            if depth == 0:
                return blanked_content[opening_index : each_position + 1]
    return blanked_content[opening_index:]


def _mixed_schema_return_callees(function_body: str) -> set[str]:
    """Return callees a function returns both with and without a schema options object.

    The body is blanked so a brace or keyword inside a prompt string never counts.
    Each ``return <callee>(...)`` whose argument list carries an object literal is
    grouped by whether that argument list also carries a ``schema`` key. A callee
    that appears on both sides marks a function that returns a schema object in one
    branch and a schema-less transcript in another.
    """
    blanked_body = _blank_non_code_regions(function_body)
    schema_bearing_callees: set[str] = set()
    schema_less_callees: set[str] = set()
    for each_return_match in RETURN_CALL_OPENING_PARENTHESIS_PATTERN.finditer(blanked_body):
        argument_span = _balanced_parenthesis_span(blanked_body, each_return_match.end() - 1)
        if "{" not in argument_span:
            continue
        callee_name = each_return_match.group("callee")
        if SCHEMA_OPTIONS_PROPERTY_KEY_PATTERN.search(argument_span) is not None:
            schema_bearing_callees.add(callee_name)
        else:
            schema_less_callees.add(callee_name)
    return schema_bearing_callees & schema_less_callees


def check_js_returns_object_schemaless_branch(content: str, file_path: str) -> list[str]:
    """Flag a JSDoc @returns Promise<object> whose branch returns a transcript string.

    Picture a dispatcher that spawns an agent and returns whatever the agent
    resolves to. Most branches pass a ``schema`` in the agent options, so the agent
    resolves to a structured object — and the JSDoc reads
    ``@returns {Promise<object>}``. But one branch spawns the same agent with no
    schema, so that branch resolves to a plain transcript string. A caller who
    trusts the object contract and reads a field off the result gets undefined on
    that branch.

    The check reads each ``function`` declaration that carries a JSDoc block. When
    the JSDoc promises a ``Promise<object>`` and the body returns one agent helper
    both with a ``schema`` options object and without one, the schema-less branch
    contradicts the object claim and the function is flagged. A function whose every
    return passes a schema, one that returns plain object literals, and one whose
    ``@returns`` already admits a string are all left alone. This is the JS/.mjs
    slice of Category O6 docstring-prose-vs-implementation drift; the Python
    enforcer's AST docstring checks never inspect JavaScript source.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per function whose object return-type claim a schema-less branch
        contradicts, capped at the module limit.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []
    if get_file_extension(file_path) not in ALL_JAVASCRIPT_EXTENSIONS:
        return []
    issues: list[str] = []
    for each_match in FUNCTION_WITH_JSDOC_PATTERN.finditer(content):
        if JSDOC_RETURNS_STRUCTURED_OBJECT_PROMISE_PATTERN.search(each_match.group("jsdoc")) is None:
            continue
        function_body = _javascript_function_body(content, each_match.end())
        if function_body is None:
            continue
        mixed_callees = _mixed_schema_return_callees(function_body)
        if not mixed_callees:
            continue
        function_name = each_match.group("name")
        line_number = content.count("\n", 0, each_match.start("name")) + 1
        joined_callees = ", ".join(sorted(mixed_callees))
        issues.append(
            f"Line {line_number}: {function_name}() JSDoc @returns a Promise<object> but a "
            f"branch returns {joined_callees}(...) with a schema-less options object — that "
            "branch resolves to a transcript string, not the structured object the @returns "
            "claims; widen the @returns type to admit the string transcript, or pass a schema "
            "(Category O6 docstring-vs-implementation drift)"
        )
        if len(issues) >= MAX_JS_RETURNS_OBJECT_SCHEMALESS_ISSUES:
            break
    return issues[:MAX_JS_RETURNS_OBJECT_SCHEMALESS_ISSUES]


def _matching_open_parenthesis_index(blanked_content: str, closing_index: int) -> int | None:
    """Return the index of the ``(`` that matches the ``)`` at ``closing_index``."""
    depth = 0
    for each_position in range(closing_index, -1, -1):
        character = blanked_content[each_position]
        if character == ")":
            depth += 1
        elif character == "(":
            depth -= 1
            if depth == 0:
                return each_position
    return None


def _return_type_annotation_colon_index(blanked_content: str, terminator_index: int) -> int | None:
    """Return the index of the ``:`` that opens the return-type annotation.

    Scanning backward from the annotation's terminating bracket at
    ``terminator_index``, nested ``{}``, ``[]``, ``<>``, and ``()`` are balanced so a
    ``:`` inside the type never counts. An arrow ``=>`` inside a function-type
    annotation (``(x: number) => void``) is depth-neutral: both characters are
    skipped so the arrow's ``>`` never counts as a generic closer. The first ``:``
    reached at annotation depth zero is the return-type colon. The result is None
    when a statement boundary (``;`` at depth zero, or an opener that drops the
    depth below zero) or the source start is reached first, so a plain block brace
    is not read as a function body.
    """
    depth = 0
    each_index = terminator_index
    while each_index >= 0:
        character = blanked_content[each_index]
        if character == ">" and each_index > 0 and blanked_content[each_index - 1] == "=":
            each_index -= JAVASCRIPT_ARROW_TOKEN_LENGTH
            continue
        if character in ALL_JAVASCRIPT_BRACKET_CLOSERS or character == ">":
            depth += 1
        elif character in ALL_JAVASCRIPT_BRACKET_OPENERS or character == "<":
            depth -= 1
            if depth < 0:
                return None
        elif depth == 0:
            if character == ":":
                return each_index
            if character == ";":
                return None
        each_index -= 1
    return None


def _is_bare_return_type_character(character: str) -> bool:
    """Report whether ``character`` can appear in a bracket-free return-type annotation.

    A bare return type — a named type (``ParseResult``), a primitive (``void``), a
    qualified name (``Foo.Bar``), or a union of them (``A | B``) — is built from
    letters, digits, ``_``, ``$``, ``.``, ``|``, ``&``, and the whitespace between
    them.
    """
    return (
        character.isalnum()
        or character.isspace()
        or character in ALL_JAVASCRIPT_BARE_RETURN_TYPE_EXTRA_CHARACTERS
    )


def _bare_return_type_annotation_colon_index(
    blanked_content: str, identifier_end_index: int
) -> int | None:
    """Return the ``:`` index that opens a bracket-free return-type annotation.

    A bare return type ends in an identifier character rather than a bracket, so the
    scan walks backward from that last character at ``identifier_end_index`` across the
    type's characters to the return-type ``:``. A closing bracket reached mid-walk
    marks a bracketed segment inside the annotation — a generic union member
    (``Promise<Foo> | Bar``) or a function type (``(x: number) => void``) — so the
    scan hands off to the bracket-balancing walk from that bracket. The result is
    None when any other non-bare character is reached first, so a plain block brace
    is not read as a function body.
    """
    for each_index in range(identifier_end_index, -1, -1):
        character = blanked_content[each_index]
        if character == ":":
            return each_index
        if character in ALL_JAVASCRIPT_RETURN_TYPE_TERMINATORS:
            return _return_type_annotation_colon_index(blanked_content, each_index)
        if not _is_bare_return_type_character(character):
            return None
    return None


def _return_type_annotation_colon_index_for_shape(
    blanked_content: str, preceding_index: int
) -> int | None:
    """Return the return-type ``:`` index for the annotation ending at ``preceding_index``.

    A return type ends either in a bracket (``}``, ``>``, ``]`` — an inline object
    literal, a generic, or a tuple type), which balances nested brackets back to the
    colon, or in an identifier character (a named type ``ParseResult``, a primitive
    ``void``, a qualified or union type), which walks back across type characters to
    the colon. The result is None when neither shape reaches a return-type colon.
    """
    if blanked_content[preceding_index] in ALL_JAVASCRIPT_RETURN_TYPE_TERMINATORS:
        return _return_type_annotation_colon_index(blanked_content, preceding_index)
    if _is_bare_return_type_character(blanked_content[preceding_index]):
        return _bare_return_type_annotation_colon_index(blanked_content, preceding_index)
    return None


def _parameter_list_close_index(blanked_content: str, preceding_index: int) -> int | None:
    """Return the index of the parameter-list ``)`` a function body brace follows.

    A plain function body brace follows the ``)`` directly. A TypeScript body brace
    follows a ``: <return type>`` annotation, so the scan walks back across the
    annotation — a bracket-terminated type (``}``, ``>``, ``]``) or a bare
    identifier, primitive, qualified, or union type — to the return-type ``:`` and
    reports the ``)`` before it. The result is None when the brace opens a plain
    block rather than a function body.
    """
    if blanked_content[preceding_index] == ")":
        return preceding_index
    colon_index = _return_type_annotation_colon_index_for_shape(blanked_content, preceding_index)
    if colon_index is None:
        return None
    parenthesis_index = colon_index - 1
    while parenthesis_index >= 0 and blanked_content[parenthesis_index].isspace():
        parenthesis_index -= 1
    if parenthesis_index < 0 or blanked_content[parenthesis_index] != ")":
        return None
    return parenthesis_index


def _bare_word_ending_at(blanked_content: str, end_index: int) -> str:
    """Return the identifier word whose last character sits at ``end_index``."""
    start_index = end_index
    while start_index > 0 and (
        blanked_content[start_index - 1].isalnum()
        or blanked_content[start_index - 1] in ALL_JAVASCRIPT_IDENTIFIER_EXTRA_CHARACTERS
    ):
        start_index -= 1
    return blanked_content[start_index : end_index + 1]


def _is_function_scope_opener(blanked_content: str, brace_index: int) -> bool:
    """Report whether the ``{`` at ``brace_index`` opens a function or arrow body.

    An arrow body follows ``=>``. A function or method body follows the parameter
    list ``)`` — directly, or across a TypeScript ``: <return type>`` annotation of
    any shape (a bracket-terminated object, generic, or tuple type, or a bare
    identifier, primitive, qualified, or union type) — whose matching ``(`` is not
    preceded by a control-flow keyword. A control block (``if``, ``for``,
    ``for await``, ``while``, ``switch``, ``catch``, ``with``) opens a plain block,
    not a scope, so a return inside it belongs to the enclosing function; the
    ``await`` token of a ``for await`` head is the word the lookback reads, so it
    sits in the keyword set. A parenthesis-free block keyword (``else``, ``do``,
    ``try``, ``finally``) opens a plain block the same way, without a parameter
    list to look back across.
    """
    preceding_index = brace_index - 1
    while preceding_index >= 0 and blanked_content[preceding_index].isspace():
        preceding_index -= 1
    if preceding_index < 1:
        return False
    if blanked_content[preceding_index] == ">" and blanked_content[preceding_index - 1] == "=":
        return True
    if blanked_content[preceding_index].isalnum():
        preceding_word = _bare_word_ending_at(blanked_content, preceding_index)
        if preceding_word in ALL_JAVASCRIPT_PARENTHESIS_FREE_BLOCK_KEYWORDS:
            return False
    parameter_close_index = _parameter_list_close_index(blanked_content, preceding_index)
    if parameter_close_index is None:
        return False
    open_parenthesis_index = _matching_open_parenthesis_index(blanked_content, parameter_close_index)
    if open_parenthesis_index is None:
        return False
    keyword_end_index = open_parenthesis_index - 1
    while keyword_end_index >= 0 and blanked_content[keyword_end_index].isspace():
        keyword_end_index -= 1
    preceding_keyword = _bare_word_ending_at(blanked_content, keyword_end_index)
    return preceding_keyword not in ALL_JAVASCRIPT_CONTROL_FLOW_BLOCK_KEYWORDS


def _split_top_level_object_entry_spans(inner_content: str) -> list[tuple[int, int]]:
    """Split object-literal inner text into ``(start, end)`` spans at depth-zero commas.

    Spans index into ``inner_content`` so a caller reads each entry's key from the
    blanked source and its value from the original source at the same offsets.
    """
    spans: list[tuple[int, int]] = []
    depth = 0
    entry_start_index = 0
    for each_index, each_character in enumerate(inner_content):
        if each_character in ALL_JAVASCRIPT_BRACKET_OPENERS:
            depth += 1
        elif each_character in ALL_JAVASCRIPT_BRACKET_CLOSERS:
            depth -= 1
        elif each_character == "," and depth == 0:
            spans.append((entry_start_index, each_index))
            entry_start_index = each_index + 1
    spans.append((entry_start_index, len(inner_content)))
    return spans


def _top_level_colon_index(entry_content: str) -> int | None:
    """Return the index of the first bracket-depth-zero ``:`` in the entry, or None."""
    depth = 0
    for each_index, each_character in enumerate(entry_content):
        if each_character in ALL_JAVASCRIPT_BRACKET_OPENERS:
            depth += 1
        elif each_character in ALL_JAVASCRIPT_BRACKET_CLOSERS:
            depth -= 1
        elif each_character == ":" and depth == 0:
            return each_index
    return None


def _string_literal_value_or_none(value_text: str) -> str | None:
    """Return the string literal's content when the value is one, else None.

    A discriminated-union tag is a string literal (``'created'``). Only the
    leading literal is read — the opening quote is matched to its own closing
    quote (backslash escapes honored) — so trailing non-code such as a comment
    (``'created' /* legacy */``) never leaks into the content, and ``'created'``
    and ``"created"`` carry the same content and compare equal. A value that is
    a boolean, number, variable, call, or other expression is not a tag, so it
    maps to None and never suppresses a drift finding for its key.
    """
    if not value_text or value_text[0] not in ALL_JAVASCRIPT_STRING_DELIMITERS:
        return None
    opening_quote = value_text[0]
    for each_index in range(1, len(value_text)):
        if value_text[each_index] == opening_quote and not _is_escaped(value_text, each_index):
            return value_text[1:each_index]
    return value_text


def _top_level_object_key_values(
    blanked_content: str, content: str, brace_index: int
) -> dict[str, str | None]:
    """Return each top-level key mapped to its string-literal value, or None.

    The literal begins at the ``{`` at ``brace_index``. Entry boundaries and keys
    come from the blanked source, so a brace, comma, or colon inside a nested
    object, array, call, or string never counts toward a key. Each value is read
    from the original ``content`` at the same offsets, so a string discriminant such
    as ``action: 'created'`` keeps its quote-stripped text; a shorthand key, a
    method-shorthand key, and a non-string value map to None. A spread entry, a
    computed key, and a quoted string-literal key are skipped.
    """
    blanked_span = _balanced_brace_body(blanked_content, brace_index)
    if blanked_span is None:
        return {}
    blanked_inner = blanked_span[1:-1]
    inner_start_index = brace_index + 1
    key_values: dict[str, str | None] = {}
    for each_entry_start_index, each_entry_end_index in _split_top_level_object_entry_spans(
        blanked_inner
    ):
        blanked_entry = blanked_inner[each_entry_start_index:each_entry_end_index]
        stripped_entry = blanked_entry.strip()
        if not stripped_entry or stripped_entry.startswith(JAVASCRIPT_OBJECT_SPREAD_PREFIX):
            continue
        colon_index = _top_level_colon_index(blanked_entry)
        if colon_index is None:
            method_shorthand_match = JS_OBJECT_METHOD_SHORTHAND_KEY_PATTERN.match(
                stripped_entry
            )
            if method_shorthand_match is not None:
                key_values[method_shorthand_match.group(1)] = None
                continue
            if not JS_OBJECT_KEY_IDENTIFIER_PATTERN.fullmatch(stripped_entry):
                continue
            key_values[stripped_entry] = None
            continue
        candidate_key = blanked_entry[:colon_index].strip()
        if not JS_OBJECT_KEY_IDENTIFIER_PATTERN.fullmatch(candidate_key):
            continue
        value_start_index = inner_start_index + each_entry_start_index + colon_index + 1
        value_end_index = inner_start_index + each_entry_end_index
        original_value = content[value_start_index:value_end_index].strip()
        key_values[candidate_key] = _string_literal_value_or_none(original_value)
    return key_values


def _return_object_literal_records(content: str) -> list[tuple[int, dict[str, str | None], int]]:
    """Return one record per returned ``{ ... }`` object literal in the JS source.

    A record comes from an explicit ``return { ... }`` or from a concise-body
    arrow's implicit return, ``() => ({ ... })``. Each record pairs the enclosing
    function-scope id, the literal's top-level key-to-string-literal-value map,
    and its 1-based line number. Each value is the key's string literal or None.
    Two returns share a scope id when the nearest enclosing function or arrow
    body is the same; a module-top-level return carries the module sentinel. A
    control-flow block does not open a scope, so an early return inside an
    ``if`` block shares its function's scope.
    """
    blanked_content = _blank_non_code_regions(content)
    return_brace_indices = {
        each_match.end() - 1
        for each_match in RETURN_OBJECT_LITERAL_OPENING_PATTERN.finditer(blanked_content)
    } | {
        each_match.end() - 1
        for each_match in ARROW_CONCISE_BODY_OBJECT_LITERAL_OPENING_PATTERN.finditer(
            blanked_content
        )
    }
    records: list[tuple[int, dict[str, str | None], int]] = []
    scope_restore_stack: list[int] = []
    current_scope_id = JAVASCRIPT_MODULE_SCOPE_SENTINEL
    current_line_number = 1
    for each_index, each_character in enumerate(blanked_content):
        if each_character == "\n":
            current_line_number += 1
        elif each_character == "{":
            if each_index in return_brace_indices:
                object_key_values = _top_level_object_key_values(
                    blanked_content, content, each_index
                )
                records.append((current_scope_id, object_key_values, current_line_number))
            scope_restore_stack.append(current_scope_id)
            if _is_function_scope_opener(blanked_content, each_index):
                current_scope_id = each_index
        elif each_character == "}":
            if scope_restore_stack:
                current_scope_id = scope_restore_stack.pop()
    return records


def _shares_differing_string_discriminant(
    all_candidate_key_values: dict[str, str | None],
    all_sibling_key_values: dict[str, str | None],
) -> bool:
    """Report whether two returns share a key carrying differing string literals.

    A shared key whose value is a string literal in both returns but differs between
    them is a discriminated-union tag (``action: 'created'`` versus ``action:
    'skipped-existing'``): the two returns are distinct variants, not one record with
    a drifted field. A boolean or numeric status flag maps to None, so only string
    literals count.
    """
    for each_shared_key in all_candidate_key_values.keys() & all_sibling_key_values.keys():
        candidate_value = all_candidate_key_values[each_shared_key]
        sibling_value = all_sibling_key_values[each_shared_key]
        if candidate_value is None or sibling_value is None:
            continue
        if candidate_value != sibling_value:
            return True
    return False


def _single_missing_sibling_key(
    all_candidate_key_values: dict[str, str | None],
    all_scope_key_value_maps: list[dict[str, str | None]],
) -> str | None:
    """Return the lone key every sibling superset adds to the candidate return.

    A sibling qualifies when the candidate's key set is a proper subset of it,
    exactly one key separates them, and the two returns share no differing
    string-literal discriminant. A discriminated-union variant whose tag differs
    from its sibling is a distinct exit shape, not a drifted record, so it is
    skipped. When every qualifying sibling adds the same single key, that key is
    returned so the caller names the omitted field. When qualifying siblings
    disagree on which key the candidate omits, the scope holds distinct exit
    shapes rather than one drifted record, so None is returned, as it is when no
    sibling qualifies.
    """
    candidate_keys = all_candidate_key_values.keys()
    all_missing_keys: set[str] = set()
    for each_sibling_key_values in all_scope_key_value_maps:
        sibling_keys = each_sibling_key_values.keys()
        if not candidate_keys < sibling_keys:
            continue
        if _shares_differing_string_discriminant(all_candidate_key_values, each_sibling_key_values):
            continue
        extra_keys = sibling_keys - candidate_keys
        if len(extra_keys) == SIBLING_RETURN_OBJECT_EXACT_MISSING_KEY_COUNT:
            all_missing_keys.update(extra_keys)
    if len(all_missing_keys) == SIBLING_RETURN_OBJECT_EXACT_MISSING_KEY_COUNT:
        return next(iter(all_missing_keys))
    return None


def check_js_sibling_return_object_key_drift(content: str, file_path: str) -> list[str]:
    """Flag a return object literal that omits one field a sibling return carries.

    Picture two return paths of the same function or workflow body. Both yield the
    same record, so both list the same fields — except one early return drops a
    single field the other carries. A caller that reads that field off the result
    gets undefined on the short path, while the documented contract and the sibling
    return both promise it.

    Within one function or module scope, the check pairs each ``return { ... }``
    object literal, and each concise-body arrow's implicit ``() => ({ ... })``
    return, against its siblings. A literal whose key set is a proper subset
    of a sibling's, missing exactly one key and carrying at least the minimum key
    count, is flagged for that one missing key. A control-flow block does not open a
    scope, so an early return inside an ``if`` block is compared with the tail
    return of the same function. Three shapes pass: returns differing by two or more
    keys are a distinct exit shape, a discriminated-union variant that shares a
    key carrying a differing string-literal tag with its sibling (``action:
    'created'`` versus ``action: 'skipped-existing'``) is a distinct variant, not a
    drifted record, and a candidate whose qualifying sibling supersets disagree on
    which single key it omits sits among distinct exit shapes rather than one
    drifted record. A TypeScript function whose return type is an inline object,
    generic, or tuple annotation opens its own scope, so its returns are not
    compared with an unrelated function's. This is the JS/.mjs slice of Category O
    doc-vs-implementation drift; the Python enforcer's AST docstring checks never
    inspect JavaScript source.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per return literal that omits a single sibling field, capped at
        the module limit.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []
    if get_file_extension(file_path) not in ALL_JAVASCRIPT_EXTENSIONS:
        return []
    records = _return_object_literal_records(content)
    records_by_scope: dict[int, list[tuple[dict[str, str | None], int]]] = {}
    for each_scope_id, each_key_values, each_line_number in records:
        records_by_scope.setdefault(each_scope_id, []).append(
            (each_key_values, each_line_number)
        )
    issues: list[str] = []
    for each_scope_records in records_by_scope.values():
        all_scope_key_value_maps = [each_record[0] for each_record in each_scope_records]
        for each_key_values, each_line_number in each_scope_records:
            if len(each_key_values) < MINIMUM_SIBLING_RETURN_OBJECT_KEYS:
                continue
            missing_key = _single_missing_sibling_key(each_key_values, all_scope_key_value_maps)
            if missing_key is None:
                continue
            issues.append(
                f"Line {each_line_number}: this return object literal omits '{missing_key}' "
                "that a sibling return in the same scope carries — every return path that "
                f"yields this record carries the same keys, so a caller reading '{missing_key}' "
                f"gets undefined on this path; add '{missing_key}' "
                "(Category O doc-vs-implementation return-shape drift)"
            )
            if len(issues) >= MAX_JS_SIBLING_RETURN_OBJECT_KEY_DRIFT_ISSUES:
                return issues[:MAX_JS_SIBLING_RETURN_OBJECT_KEY_DRIFT_ISSUES]
    return issues[:MAX_JS_SIBLING_RETURN_OBJECT_KEY_DRIFT_ISSUES]


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
