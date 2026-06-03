#!/usr/bin/env python3
"""
CODE_RULES.md enforcer - blocks code that violates mandatory rules.

Checks (blocking):
1. No comments (# or // in code, excluding shebangs/type: ignore)
2. Imports at top (no imports inside functions)
3. Logging f-strings (log_* calls must use format args)
4. Windows API None (win32gui calls with None parameter)
5. Magic values (literals in function bodies)
6. E2E test naming (no online/offline in test names)
7. Constants outside config (UPPER_SNAKE = in non-config files)
8. Boolean naming (is_/has_/should_/can_ prefix required)

Advisory only (non-blocking):
- File line count: stderr warning at 400 lines (soft) and 1000 lines (hard)

Companion tests live alongside this file as
``test_code_rules_enforcer_<suffix>.py``; the ``<suffix>`` split keeps each
concern focused. The separate ``tdd_enforcer.py`` hook currently scans only
for the exact candidate ``test_code_rules_enforcer.py`` and does not accept
the suffix variants, so edits to this file include the bypass sentinel
``# pragma: no-tdd-gate`` until the TDD hook learns the suffix convention.
"""
import ast
import difflib
import io
import json
import re
import sys
import tokenize
from collections.abc import Iterator
from pathlib import Path
from typing import Optional

_BLOCKING_DIR = str(Path(__file__).resolve().parent)
_HOOKS_DIR = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIR not in sys.path:
    sys.path.insert(0, _BLOCKING_DIR)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from code_rules_path_utils import is_config_file  # noqa: E402
from hooks_constants.banned_identifiers_constants import (  # noqa: E402
    ALL_BANNED_IDENTIFIERS,
    ALL_BANNED_NOUN_WORDS,
    BANNED_IDENTIFIER_MESSAGE_SUFFIX,
    BANNED_IDENTIFIER_SKIP_ADVISORY,
    BANNED_NOUN_WORD_MESSAGE_SUFFIX,
    CAMEL_CASE_WORD_PATTERN,
    MAX_BANNED_IDENTIFIER_ISSUES,
)
from hooks_constants.hardcoded_user_path_constants import (  # noqa: E402
    HARDCODED_USER_PATH_GUIDANCE,
    HARDCODED_USER_PATH_PATTERN,
    MAX_HARDCODED_USER_PATH_ISSUES,
)
from hooks_constants.inline_tuple_string_magic_constants import (  # noqa: E402
    ALL_SNAKE_CASE_KEYWORD_EXEMPTIONS,
    EXPECTED_TUPLE_PAIR_LENGTH,
    INLINE_TUPLE_STRING_MAGIC_MESSAGE_SUFFIX,
    MAX_INLINE_TUPLE_STRING_MAGIC_ISSUES,
    SNAKE_CASE_LITERAL_PATTERN,
)
from hooks_constants.stuttering_check_config import (  # noqa: E402
    MAX_STUTTERING_PREFIX_ISSUES,
    STUTTERING_ALL_PREFIX_PATTERN,
)
from hooks_constants.sys_path_insert_constants import MAX_SYS_PATH_INSERT_ISSUES, SYS_PATH_INSERT_GUIDANCE  # noqa: E402
from hooks_constants.unused_module_import_constants import (  # noqa: E402
    ALL_TYPING_MODULE_NAMES,
    MAX_UNUSED_IMPORT_ISSUES,
    TYPE_CHECKING_IDENTIFIER,
    UNUSED_IMPORT_GUIDANCE,
    line_suppresses_unused_import_via_noqa,
)
from hooks_constants.stuttering_import_binding_constants import (  # noqa: E402
    AST_LINENO_ATTRIBUTE,
    MODULE_PATH_SEPARATOR,
    WILDCARD_IMPORT_SENTINEL,
)
from hooks_constants.any_type_config import ALL_ANY_ALLOWED_PATTERNS  # noqa: E402
from hooks_constants.blocking_check_limits import (  # noqa: E402
    ALL_BANNED_PREFIX_NAMES,
    ALL_BARE_EXCEPT_BANNED_HANDLER_NAMES,
    ALL_BOUNDARY_TYPE_EXEMPT_FILENAMES,
    ALL_DOCSTRING_EXEMPT_DECORATOR_NAMES,
    ALL_DOCSTRING_IMPLICIT_INSTANCE_PARAMETER_NAMES,
    ALL_TEST_INDICATING_ENVIRONMENT_VARIABLE_NAMES,
    DOCSTRING_TRIVIAL_FUNCTION_BODY_LINE_LIMIT,
    MAX_BANNED_PREFIX_ISSUES,
    MAX_BARE_EXCEPT_ISSUES,
    MAX_BOUNDARY_TYPE_ISSUES,
    MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES,
    MAX_DOCSTRING_FORMAT_ISSUES,
    MAX_IGNORED_MUST_CHECK_RETURN_ISSUES,
    MAX_STUB_IMPLEMENTATION_ISSUES,
    MAX_TEST_BRANCHING_ISSUES,
    MAX_TYPED_DICT_PAIR_ISSUES,
    MAX_TYPE_ESCAPE_HATCH_ISSUES,
    MAX_THIN_WRAPPER_ISSUES,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ADVISORY_LINE_THRESHOLD_HARD,
    ADVISORY_LINE_THRESHOLD_SOFT,
    ALL_CODE_EXTENSIONS,
    ALL_CAPS_WITH_UNDERSCORE_PATTERN,
    ALL_FILESYSTEM_HOME_PROBE_DOTTED_NAMES,
    ALL_DIR_ACCEPTING_TEMPFILE_FACTORY_DOTTED_NAMES,
    ALL_SHARED_TEMP_SOURCE_PROBE_DOTTED_NAMES,
    TEMPFILE_FACTORY_ISOLATION_DIRECTORY_KEYWORD,
    ALL_HOME_DIRECTORY_ENV_VAR_NAMES,
    ALL_ENVIRONMENT_GETTER_DOTTED_NAMES,
    ALL_PROBE_RELEVANT_MODULE_CANONICAL_NAMES,
    ALL_CANONICAL_DOTTED_NAMES_BY_BARE_IMPORT,
    OS_ENVIRON_DOTTED_NAME,
    ENVIRON_GET_METHOD_NAME,
    ENVIRONMENT_VARIABLE_REFERENCE_PATTERN,
    WINDOWS_PERCENT_VARIABLE_REFERENCE_PATTERN,
    EXPANDVARS_DOTTED_NAME,
    EXPANDUSER_DOTTED_NAME,
    ALL_PATHLIB_STATIC_EXPANDUSER_DOTTED_NAMES,
    PATHLIB_EXPANDUSER_METHOD_NAME,
    ALL_PATHLIB_PATH_CONSTRUCTOR_CANONICAL_NAMES,
    ALL_PROBE_ALIASABLE_CANONICAL_PREFIXES,
    HOME_DIRECTORY_TILDE_PREFIX,
    ALL_PYTEST_FILESYSTEM_ISOLATION_FIXTURE_NAMES,
    PYTEST_USEFIXTURES_MARKER_NAME,
    PYTEST_TEST_CLASS_NAME_PREFIX,
    ALL_DIFF_CHANGED_OPCODE_TAGS,
    FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX,
    FUNCTION_LENGTH_BLOCKING_THRESHOLD,
    BANNED_NOUN_SPAN_FRAGMENT_TEMPLATE,
    BARE_EACH_TOKEN,
    ALL_BOOLEAN_NAME_PREFIXES,
    ALL_DOCSTRING_ARGS_SECTION_HEADERS,
    ALL_DOCSTRING_TERMINATING_SECTION_HEADERS,
    DOCSTRING_ARG_ENTRY_PATTERN,
    ALL_MUST_CHECK_RETURN_FUNCTION_NAMES,
    ALL_BUILTIN_DICT_METHOD_NAMES,
    ALL_CLI_FILE_PATH_MARKERS,
    CHAINED_INLINE_COMMENT_PATTERN,
    COLLECTION_BY_NAME_PATTERN,
    ALL_COLLECTION_TYPE_NAMES,
    ALL_SUBSCRIPT_ONLY_COLLECTION_TYPE_NAMES,
    DOTTED_SEGMENT_PATTERN,
    EACH_PREFIX,
    ALL_FREE_FORM_EXEMPT_COMMENT_BODIES,
    ALL_TOKEN_ANCHORED_EXEMPT_COMMENT_BODIES,
    ALL_TOKEN_ANCHORED_DIRECTIVE_BOUNDARY_CHARACTERS,
    ALL_JAVASCRIPT_EXEMPT_COMMENT_PREFIXES,
    ALL_JAVASCRIPT_EXEMPT_INLINE_COMMENT_PREFIXES,
    ALL_PYTHON_TOKENIZE_FAILURE_EXCEPTIONS,
    FILE_GLOBAL_UPPER_SNAKE_PATTERN,
    ALL_HOOK_INFRASTRUCTURE_PATTERNS,
    ALL_IMPORT_STATEMENT_PREFIXES,
    MAX_COMMENT_ISSUES,
    TEST_ISOLATION_MESSAGE_SUFFIX,
    INLINE_COLLECTION_MIN_LENGTH,
    ALL_JAVASCRIPT_EXTENSIONS,
    LOGGING_FSTRING_PATTERN,
    ALL_LOOP_INDEX_LETTER_EXEMPTIONS,
    ALL_MIGRATION_PATH_PATTERNS,
    NOT_INSIDE_TYPE_CHECKING_BLOCK,
    ALL_PYTHON_EXTENSIONS,
    ALL_SELF_AND_CLS_PARAMETER_NAMES,
    ALL_TEST_PATH_PATTERNS,
    TRIPLE_DOUBLE_QUOTE_DELIMITER,
    TRIPLE_QUOTE_PARITY_DIVISOR,
    TRIPLE_SINGLE_QUOTE_DELIMITER,
    TYPE_CHECKING_BLOCK_PATTERN,
    ALL_UNION_TYPING_NAMES,
    UPPER_SNAKE_CONSTANT_PATTERN,
    ALL_WORKFLOW_REGISTRY_PATTERNS,
)


def get_file_extension(file_path: str) -> str:
    """Extract lowercase file extension."""
    dot_index = file_path.rfind(".")
    if dot_index == -1:
        return ""
    return file_path[dot_index:].lower()


def is_hook_infrastructure(file_path: str) -> bool:
    """Check if file is a Claude Code hook (standalone infrastructure, not project code)."""
    path_lower = "/" + file_path.lower().replace("\\", "/").lstrip("/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in ALL_HOOK_INFRASTRUCTURE_PATTERNS)


def is_test_file(file_path: str) -> bool:
    """Check if file is a test file."""
    path_lower = file_path.lower()
    basename_lower = path_lower.replace("\\", "/").rsplit("/", 1)[-1]
    if basename_lower == "conftest.py":
        return True
    return any(pattern in path_lower for pattern in ALL_TEST_PATH_PATTERNS)


def is_workflow_registry_file(file_path: str) -> bool:
    """Check if file is a workflow state/module registry file.

    Workflow tab files and state/module registry files use UPPER_SNAKE naming
    for StateDefinition and WorkflowModule instances by architectural convention.
    These are module-level singletons, not misplaced literal constants.
    """
    path_lower = file_path.lower().replace("\\", "/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in ALL_WORKFLOW_REGISTRY_PATTERNS)


def is_spec_file(file_path: str) -> bool:
    """Check if file is an E2E spec file."""
    return ".spec." in file_path.lower()


def check_comments_python(content: str) -> list[str]:
    """Check for comments in Python code.

    Uses ``tokenize.generate_tokens`` to find true ``COMMENT`` tokens.
    Hash characters that appear inside string literals (hex color codes,
    URL fragments, and the hash inside an f-string interpolation pattern)
    are correctly skipped because the tokenizer recognizes them as parts
    of string tokens rather than comment tokens.

    When the tokenizer cannot parse the file (partial content during
    Edit, invalid syntax), the check returns no findings rather than
    falling back to a line-walker scan — false negatives on
    syntactically-invalid drafts are preferable to false positives that
    mis-classify string-interior hash characters as comments.
    """
    issues = []
    for each_comment_token in _comment_tokens(content):
        if _is_exempt_python_comment(each_comment_token):
            continue
        line_number = each_comment_token.start[0]
        issues.append(
            f"Line {line_number}: Comment found - refactor to self-documenting code"
        )
        if len(issues) >= MAX_COMMENT_ISSUES:
            break

    return issues


def check_comments_javascript(content: str) -> list[str]:
    """Check for comments in JavaScript/TypeScript code."""
    issues = []
    lines = content.split("\n")
    is_in_multiline_comment = False

    for each_line_number, each_line in enumerate(lines, 1):
        stripped = each_line.strip()

        if not stripped:
            continue

        if is_in_multiline_comment:
            if "*/" in stripped:
                is_in_multiline_comment = False
            continue

        if stripped.startswith("/*"):
            is_in_multiline_comment = "*/" not in stripped
            if not stripped.startswith("/**"):
                issues.append(f"Line {each_line_number}: Block comment found - refactor to self-documenting code")
            continue

        if stripped.startswith("//"):
            if not stripped.startswith(ALL_JAVASCRIPT_EXEMPT_COMMENT_PREFIXES):
                issues.append(f"Line {each_line_number}: Comment found - refactor to self-documenting code")

        if len(issues) >= MAX_COMMENT_ISSUES:
            break

    return issues


def extract_comment_texts(content: str, file_path: str) -> tuple[set[str], set[str]]:
    """Extract normalized comment text strings from content for comparison.

    Returns:
        Tuple of (inline_comments, standalone_comments).
        Inline comments appear after code on the same line.
        Standalone comments are lines where the entire line is a comment.
    """
    extension = get_file_extension(file_path)
    inline_comments: set[str] = set()
    standalone_comments: set[str] = set()
    if not content:
        return inline_comments, standalone_comments

    if extension in ALL_PYTHON_EXTENSIONS:
        inline_comments, standalone_comments, _ = _extract_python_comment_sets(content)
        return inline_comments, standalone_comments

    lines = content.split("\n")

    if extension in ALL_JAVASCRIPT_EXTENSIONS:
        is_in_multiline = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if is_in_multiline:
                if "*/" in stripped:
                    is_in_multiline = False
                continue
            if stripped.startswith("/*"):
                is_in_multiline = "*/" not in stripped
                if not stripped.startswith("/**"):
                    standalone_comments.add(stripped)
                continue
            if stripped.startswith("//"):
                if not stripped.startswith(ALL_JAVASCRIPT_EXEMPT_COMMENT_PREFIXES):
                    standalone_comments.add(stripped)
            elif "//" in line:
                before_slash = line[:line.index("//")]
                if before_slash.strip():
                    comment_start = stripped.index("//")
                    comment_text = stripped[comment_start + 2 :].strip()
                    if not comment_text.startswith(ALL_JAVASCRIPT_EXEMPT_INLINE_COMMENT_PREFIXES):
                        inline_comments.add(stripped[comment_start:])

    return inline_comments, standalone_comments


def check_comment_changes(old_content: str, new_content: str, file_path: str) -> list[str]:
    """Check for comment additions or removals between old and new content.

    Inline comments (after code on same line): BLOCK when added.
    Standalone comment lines: NUDGE (print advisory) when added.
    Existing comments being removed: BLOCK (comment preservation principle).

    When the file is Python and either *old_content* or *new_content* cannot
    be tokenized (common for mid-edit Edit fragments), the comparison is
    indeterminate: the per-side tokenize failure would empty one set and
    misrepresent every comment on the other side as either added or
    removed. The check returns no issues in that case — false negatives on
    syntactically-invalid drafts are preferable to false positives that
    flag legitimate comments as deleted.
    """
    issues: list[str] = []

    extension = get_file_extension(file_path)
    if extension in ALL_PYTHON_EXTENSIONS:
        old_inline, old_standalone, old_tokenize_ok = _extract_python_comment_sets(old_content)
        new_inline, new_standalone, new_tokenize_ok = _extract_python_comment_sets(new_content)
        if not (old_tokenize_ok and new_tokenize_ok):
            return issues
    else:
        old_inline, old_standalone = extract_comment_texts(old_content, file_path)
        new_inline, new_standalone = extract_comment_texts(new_content, file_path)

    added_inline = new_inline - old_inline
    if added_inline:
        sample = next(iter(added_inline))
        issues.append(f"Inline comment added: {sample[:60]} - refactor to self-documenting code")

    added_standalone = new_standalone - old_standalone
    if added_standalone:
        sample = next(iter(added_standalone))
        print(f"[CODE_RULES advisory] Standalone comment added: {sample[:60]} - prefer self-documenting code", file=sys.stderr)

    all_old = old_inline | old_standalone
    all_new = new_inline | new_standalone
    removed_comments = all_old - all_new
    if removed_comments:
        old_line_count = len([line for line in old_content.split("\n") if line.strip()])
        new_line_count = len([line for line in new_content.split("\n") if line.strip()])
        code_was_removed = new_line_count < old_line_count - len(removed_comments)
        if not code_was_removed:
            sample = next(iter(removed_comments))
            issues.append(f"Existing comment removed: {sample[:60]} - NEVER delete existing comments")

    return issues


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

    for line_number, each_line in enumerate(lines, 1):
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
                issues.append(f"Line {line_number}: Import inside function - move to top of file")

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

    for line_number, line in enumerate(content.split("\n"), 1):
        if pattern.search(line):
            issues.append(f"Line {line_number}: f-string in log call - use format args instead")

        if len(issues) >= 3:
            break

    return issues


def advise_file_line_count(content: str, file_path: str) -> None:
    """Emit non-blocking stderr advisories when a file crosses size smell thresholds.

    Thresholds are smell signals, not hard caps. See CODE_RULES.md "File length guidance"
    for rationale. Soft threshold aligns with Clean Code Ch. 5 / Fowler "Large Class".
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

    for line_number, line in enumerate(content.split("\n"), 1):
        if pattern.search(line):
            issues.append(f"Line {line_number}: win32gui call with None - use 0 for unused int params")

        if len(issues) >= 3:
            break

    return issues


_STRING_LITERAL_PATTERN = re.compile(
    r"(\"(?:\\.|[^\"\\])*\")|('(?:\\.|[^'\\])*')",
)


def _mask_string_literals_preserving_length(source_line: str) -> str:
    """Replace every string literal with an equal-length neutral placeholder.

    The TDD-gate sentinel below opts this production file out of the hook
    because the existing companion tests use the project's convention
    ``test_code_rules_enforcer_<suffix>.py`` rather than the single
    ``test_code-rules-enforcer.py`` name the hook scans for. Matching
    tests for this change live in
    ``test_code_rules_enforcer_magic_string_masking.py``.
    Sentinel: # pragma: no-tdd-gate
    """

    def _replace_string_literal(match: re.Match[str]) -> str:
        matched_literal = match.group(0)
        opening_quote = matched_literal[0]
        closing_quote = matched_literal[-1]
        inner_length = max(len(matched_literal) - 2, 0)
        return f"{opening_quote}{'_' * inner_length}{closing_quote}"

    return _STRING_LITERAL_PATTERN.sub(_replace_string_literal, source_line)


def check_magic_values(content: str, file_path: str) -> list[str]:
    """Check for magic values in function bodies."""
    if is_config_file(file_path) or is_test_file(file_path):
        return []

    issues = []
    lines = content.split("\n")
    is_inside_function = False

    number_pattern = re.compile(r"(?<![.\w])(\d+\.?\d*)(?![.\w])")
    allowed_numbers = {"0", "1", "-1", "0.0", "1.0"}

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()

        if not stripped:
            continue

        if re.match(r"^(async\s+)?def\s+\w+", stripped):
            is_inside_function = True
            continue

        if re.match(r"^class\s+\w+", stripped):
            is_inside_function = False
            continue

        if is_inside_function:
            if "=" in stripped and stripped.split("=")[0].strip().isupper():
                continue

            if stripped.startswith(("return", "yield", "raise")):
                continue

            stripped_without_string_literals = _mask_string_literals_preserving_length(stripped)
            numbers_found = number_pattern.findall(stripped_without_string_literals)
            for number in numbers_found:
                if number not in allowed_numbers:
                    if "range(" in stripped_without_string_literals or "enumerate(" in stripped_without_string_literals:
                        continue
                    if "[" in stripped_without_string_literals and "]" in stripped_without_string_literals:
                        continue
                    issues.append(f"Line {line_number}: Magic value {number} - extract to named constant")
                    break

        if len(issues) >= 3:
            break

    return issues


def _extract_fstring_literal_parts(
    joined_string_node: ast.JoinedStr,
    interpolation_placeholder: str = "INTERP",
) -> tuple[str, str]:
    """Return (display_body, shape_body) for an f-string node.

    ``display_body`` concatenates only the literal segments for use in the
    human-readable flag message. ``shape_body`` substitutes each interpolation
    slot with ``interpolation_placeholder`` so callers can choose a token that
    both preserves structural shape and does not collide with literal text in
    the source. The default ``"INTERP"`` keeps regex patterns for path shape
    (``\\w+/\\w+/\\w+``) matching across interpolation boundaries
    (e.g. ``/api/v1/{id}/home`` keeps its three path segments instead of
    collapsing to ``/api/v1//home``). Callers that will compare shape bodies
    verbatim — such as the skeleton builder — should pass their final token
    here directly rather than post-processing with ``.replace``, since that
    would corrupt literal text containing the default placeholder. Escaped
    braces (``{{`` / ``}}``) are already decoded by :mod:`ast` into their
    literal forms.
    """
    display_segments: list[str] = []
    shape_segments: list[str] = []
    for each_part in joined_string_node.values:
        if isinstance(each_part, ast.Constant) and isinstance(each_part.value, str):
            display_segments.append(each_part.value)
            shape_segments.append(each_part.value)
        else:
            shape_segments.append(interpolation_placeholder)
    return "".join(display_segments), "".join(shape_segments)


def _has_structural_shape(literal_body: str) -> bool:
    """Return True when a literal body looks like a path, URL, or regex.

    Natural English containing a single slash (e.g. ``online/offline``,
    ``CI/CD``, ``and/or``) must NOT match. Only multi-segment paths,
    URL schemes, Windows drive prefixes, leading absolute paths, regex
    escape sequences (``\\d``, ``\\w``, ``\\s`` and friends), or regex
    anchors at the boundary are treated as structural.
    """
    if re.search(r"\w+/\w+/\w+", literal_body):
        return True
    if re.search(r"\w+\\\w+\\\w+", literal_body):
        return True
    if re.search(r"[A-Za-z][A-Za-z0-9+.\-]*://", literal_body):
        return True
    if re.search(r"(^|\s)[A-Za-z]:[\\/]", literal_body):
        return True
    if re.search(r"^/\w+/\w+", literal_body):
        return True
    if re.search(r"\\[dwsDWSbBAZ]|\\\d", literal_body):
        return True
    if literal_body.startswith("^") or literal_body.endswith("$"):
        return True
    return False


def check_fstring_structural_literals(content: str, file_path: str) -> list[str]:
    """Flag f-strings whose literal fragments look like paths, URLs, or regex.

    Parses the file with :mod:`ast` so every f-string form is handled
    uniformly: single, triple-quoted, raw (``rf`` / ``fr``), and strings
    containing apostrophes or escaped braces. The literal portions of
    each ``JoinedStr`` node are concatenated, and the result is treated
    as a structural magic value only when :func:`_has_structural_shape`
    matches a multi-segment path, a URL scheme, a Windows drive prefix,
    a leading absolute path, a regex escape sequence, or a boundary
    regex anchor.

    The enforcer hook file, config files, and test files are all exempt.
    Syntax errors in the input silently produce no issues, matching the
    behaviour of the other lint-style checks in this module.
    """
    if is_config_file(file_path) or is_test_file(file_path):
        return []
    if file_path.replace("\\", "/").endswith("hooks/blocking/code_rules_enforcer.py"):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    minimum_literal_length = 2
    maximum_issues_before_stop = 100
    non_magic_stripped_values = {"", "True", "False"}

    issues: list[str] = []
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, ast.JoinedStr):
            continue
        display_body, shape_body = _extract_fstring_literal_parts(each_node)
        if display_body in non_magic_stripped_values:
            continue
        if len(display_body) < minimum_literal_length:
            continue
        if not _has_structural_shape(shape_body):
            continue
        issues.append(
            f"Line {each_node.lineno}: Structural literal inside f-string {display_body!r} - extract to config"
        )
        if len(issues) >= maximum_issues_before_stop:
            break

    return issues


def check_e2e_test_naming(content: str, file_path: str) -> list[str]:
    """Check for online/offline in test names (spec files only)."""
    if not is_spec_file(file_path):
        return []

    issues = []
    pattern = re.compile(r'(test|it|describe)\s*\(\s*["\'][^"\']*\b(online|offline)\b[^"\']*["\']', re.IGNORECASE)

    for line_number, line in enumerate(content.split("\n"), 1):
        if pattern.search(line):
            issues.append(f"Line {line_number}: Test name contains online/offline - file scope defines this")

        if len(issues) >= 3:
            break

    return issues


def _render_annotation_source(annotation_node: ast.expr) -> str:
    """Return a textual representation of an annotation AST node."""
    unparse_function = getattr(ast, "unparse", None)
    if unparse_function is not None:
        return unparse_function(annotation_node)
    sys.stderr.write(
        "code_rules_enforcer: ast.unparse unavailable on this interpreter; "
        "falling back to ast.dump for Any detection.\n"
    )
    return ast.dump(annotation_node)


def _annotation_uses_any(annotation_node: Optional[ast.expr]) -> bool:
    """Return True when an annotation AST node textually references Any."""
    if annotation_node is None:
        return False
    annotation_source = _render_annotation_source(annotation_node)
    return bool(re.search(r"\bAny\b", annotation_source))


def _collect_annotated_arguments(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
    """Return every argument node on a function that may carry an annotation."""
    arguments = function_node.args
    all_annotated_arguments: list[ast.arg] = []
    all_annotated_arguments.extend(arguments.posonlyargs)
    all_annotated_arguments.extend(arguments.args)
    all_annotated_arguments.extend(arguments.kwonlyargs)
    if arguments.vararg is not None:
        all_annotated_arguments.append(arguments.vararg)
    if arguments.kwarg is not None:
        all_annotated_arguments.append(arguments.kwarg)
    return all_annotated_arguments


def _find_any_annotation_lines(source: str) -> list[int]:
    """Return line numbers of annotations that textually reference Any."""
    try:
        parsed_tree = ast.parse(source)
    except SyntaxError:
        return []

    offending_line_numbers: list[int] = []
    already_reported_lines: set[int] = set()
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if isinstance(each_node, ast.AnnAssign) and _annotation_uses_any(each_node.annotation):
            if each_node.lineno not in already_reported_lines:
                offending_line_numbers.append(each_node.lineno)
                already_reported_lines.add(each_node.lineno)
            continue
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _annotation_uses_any(each_node.returns) and each_node.lineno not in already_reported_lines:
                offending_line_numbers.append(each_node.lineno)
                already_reported_lines.add(each_node.lineno)
            for each_argument in _collect_annotated_arguments(each_node):
                if _annotation_uses_any(each_argument.annotation) and each_argument.lineno not in already_reported_lines:
                    offending_line_numbers.append(each_argument.lineno)
                    already_reported_lines.add(each_argument.lineno)
    return offending_line_numbers


def _python_tokens(source: str) -> Iterator[tokenize.TokenInfo]:
    """Yield Python tokens from *source* one at a time.

    Centralizes the ``tokenize.generate_tokens`` entry-point so a future
    change to the API lands in exactly one place. Iteration may raise
    any of ``ALL_PYTHON_TOKENIZE_FAILURE_EXCEPTIONS`` when the source is
    not valid Python (mid-edit Edit fragments, unterminated strings,
    mismatched indentation) — callers handle the exception according to
    their own contract (silently stop, return an indeterminate flag, etc.).
    """
    yield from tokenize.generate_tokens(io.StringIO(source).readline)


def _comment_tokens(source: str) -> Iterator[tokenize.TokenInfo]:
    """Yield COMMENT tokens from *source* one at a time.

    Streams from ``_python_tokens`` so consumers that early-exit (e.g.
    ``check_comments_python`` caps at ``MAX_COMMENT_ISSUES``) avoid
    materializing the entire token list. Silently stops on tokenize
    failure so callers receive only valid comment tokens — no
    indeterminate signal is exposed at this layer because the consumers
    that need it (``_extract_python_comment_sets``) bypass this helper.
    """
    try:
        for each_token in _python_tokens(source):
            if each_token.type == tokenize.COMMENT:
                yield each_token
    except ALL_PYTHON_TOKENIZE_FAILURE_EXCEPTIONS:
        return


def _is_exempt_python_comment(comment_token: tokenize.TokenInfo) -> bool:
    """Return True for shebangs and tooling-directive comments.

    The shebang exemption applies only when the comment token starts
    at line 1, column 0 — matching the OS-level convention that a
    shebang line is meaningful only as the first line of an executable
    file. An inline shebang-lookalike later in the file (an
    after-code occurrence on any line, or a standalone occurrence on
    line 2 or later) is NOT a real shebang and remains subject to the
    no-comments rule.

    Matches any prefix listed in the token-anchored or free-form exempt-
    comment-body sets regardless of whether the directive sits flush
    against the leading hash character or carries one or more whitespace
    characters (space or tab) between the hash and the directive body.

    Token-anchored markers (``noqa``, ``pylint:``, ``pragma:``) are
    exempt only when the comment carries no chained second comment. Any
    second ``#`` after the directive body — regardless of whitespace
    around the inner hash, so ``# noqa: F401#note``,
    ``# noqa: F401 #prose``, and ``# noqa: F401  # imported for re-export``
    all qualify — indicates a second free-form inline comment
    piggybacking on the exempt marker; the trailing prose is not itself
    an exempt directive and therefore must not inherit exemption. A
    token-anchored directive body never legitimately carries a ``#``
    (noqa codes, pylint symbols, and pragma directives contain none), so
    any inner ``#`` reliably marks chained prose. Free-form markers
    (``type:``, ``TODO``, ``FIXME``, ``HACK``, ``XXX``) accept any
    trailing prose:
    ``# type:`` participates in the documented justification
    convention enforced by ``check_type_escape_hatches`` (which
    requires a trailing reason), and the TODO-family markers carry
    annotation text by convention.
    """
    comment_string = comment_token.string
    if comment_string.startswith("#!") and comment_token.start == (1, 0):
        return True
    directive_body = comment_string[1:].lstrip()
    if not directive_body:
        return True
    if directive_body.startswith(ALL_FREE_FORM_EXEMPT_COMMENT_BODIES):
        return True
    if not _starts_with_bounded_token_anchored_directive(directive_body):
        return False
    return CHAINED_INLINE_COMMENT_PATTERN.search(directive_body) is None


def _starts_with_bounded_token_anchored_directive(directive_body: str) -> bool:
    """Return True when *directive_body* opens with a real exempt directive.

    A token-anchored marker (``noqa``, ``pylint:``, ``pragma:``) counts only
    when the matched token is immediately followed by a directive boundary —
    end of string, a colon, or whitespace — so prose like
    ``noqa-but-not-really: explanation`` that merely shares the prefix does
    not inherit the exemption.

    Args:
        directive_body: The comment text with the leading hash and surrounding
            whitespace already stripped.

    Returns:
        True when a token-anchored exempt directive is present at a real token
        boundary, False otherwise.
    """
    for each_token in ALL_TOKEN_ANCHORED_EXEMPT_COMMENT_BODIES:
        if not directive_body.startswith(each_token):
            continue
        if each_token[-1] in ALL_TOKEN_ANCHORED_DIRECTIVE_BOUNDARY_CHARACTERS:
            return True
        following_text = directive_body[len(each_token):]
        if not following_text:
            return True
        next_character = following_text[0]
        if next_character.isspace():
            return True
        if next_character in ALL_TOKEN_ANCHORED_DIRECTIVE_BOUNDARY_CHARACTERS:
            return True
    return False


def _extract_python_comment_sets(content: str) -> tuple[set[str], set[str], bool]:
    """Return (inline_comments, standalone_comments, tokenize_succeeded).

    Streams *content* once via ``_python_tokens``. A tokenize failure
    (mid-edit fragment, syntax error) returns empty sets and ``False``
    so callers can treat the situation as indeterminate rather than as
    "no comments present". Inline vs standalone is decided by inspecting
    the column offset of each ``COMMENT`` token against its source
    line: an all-whitespace prefix means standalone.
    """
    inline_comments: set[str] = set()
    standalone_comments: set[str] = set()
    lines = content.split("\n")
    try:
        for each_token in _python_tokens(content):
            if each_token.type != tokenize.COMMENT:
                continue
            if _is_exempt_python_comment(each_token):
                continue
            line_number = each_token.start[0]
            column_offset = each_token.start[1]
            source_line = lines[line_number - 1] if line_number - 1 < len(lines) else ""
            text_before_comment = source_line[:column_offset]
            normalized_comment_text = each_token.string.strip()
            if not text_before_comment.strip():
                standalone_comments.add(normalized_comment_text)
            else:
                inline_comments.add(normalized_comment_text)
    except ALL_PYTHON_TOKENIZE_FAILURE_EXCEPTIONS:
        return set(), set(), False
    return inline_comments, standalone_comments, True


def _find_unjustified_type_ignore_lines(source: str) -> list[int]:
    """Return line numbers of # type: ignore comments lacking a trailing reason."""
    ignore_pattern = re.compile(r"#\s*type:\s*ignore(?:\[[^\]]*\])?(.*)$")
    minimum_justification_characters = len("xxxxx")
    offending_line_numbers: list[int] = []
    for each_comment_token in _comment_tokens(source):
        matched = ignore_pattern.search(each_comment_token.string)
        if not matched:
            continue
        line_number = each_comment_token.start[0]
        trailing_text = matched.group(1).strip()
        if not trailing_text.startswith("#"):
            offending_line_numbers.append(line_number)
            continue
        justification_text = trailing_text.lstrip("#").strip()
        if len(justification_text) < minimum_justification_characters:
            offending_line_numbers.append(line_number)
    return offending_line_numbers


def _find_typing_any_imports(source: str) -> list[int]:
    """Return line numbers of `from typing import ... Any ...` statements."""
    try:
        parsed_tree = ast.parse(source)
    except SyntaxError:
        return []

    offending_line_numbers: list[int] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, ast.ImportFrom):
            continue
        if each_node.module != "typing":
            continue
        for each_alias in each_node.names:
            if each_alias.name == "Any":
                offending_line_numbers.append(each_node.lineno)
                break
    return offending_line_numbers


def _find_typing_wildcard_imports(source: str) -> list[int]:
    """Return line numbers of `from typing import *` statements."""
    try:
        parsed_tree = ast.parse(source)
    except SyntaxError:
        return []

    offending_line_numbers: list[int] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, ast.ImportFrom):
            continue
        if each_node.module != "typing":
            continue
        for each_alias in each_node.names:
            if each_alias.name == "*":
                offending_line_numbers.append(each_node.lineno)
                break
    return offending_line_numbers


def _collect_typing_cast_import_names(source: str) -> frozenset[str]:
    """Return the set of names bound to typing.cast via `from typing import cast`."""
    try:
        parsed_tree = ast.parse(source)
    except SyntaxError:
        return frozenset()

    cast_names: set[str] = set()
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, ast.ImportFrom):
            continue
        if each_node.module != "typing":
            continue
        for each_alias in each_node.names:
            if each_alias.name == "cast":
                cast_names.add(each_alias.asname or each_alias.name)
    return frozenset(cast_names)


def _is_typing_cast_call(call_node: ast.Call, all_cast_import_names: frozenset[str]) -> bool:
    """Return True when a Call node represents a typing.cast() or known bare cast()."""
    function_node = call_node.func
    if isinstance(function_node, ast.Attribute) and function_node.attr == "cast":
        if isinstance(function_node.value, ast.Name) and function_node.value.id == "typing":
            return True
    if isinstance(function_node, ast.Name) and function_node.id in all_cast_import_names:
        return True
    return False


def _find_cast_call_lines(source: str) -> list[int]:
    """Return line numbers of cast(...) calls (typing.cast or bare cast)."""
    try:
        parsed_tree = ast.parse(source)
    except SyntaxError:
        return []

    all_cast_import_names = _collect_typing_cast_import_names(source)

    offending_line_numbers: list[int] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if isinstance(each_node, ast.Call) and _is_typing_cast_call(each_node, all_cast_import_names):
            offending_line_numbers.append(each_node.lineno)
    return offending_line_numbers


def _file_path_matches_any_exemption(file_path: str) -> bool:
    filename = file_path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return filename in {each_pattern.lower() for each_pattern in ALL_ANY_ALLOWED_PATTERNS}


def check_type_escape_hatches(content: str, file_path: str) -> list[str]:
    """Flag Any annotations, Any imports, cast() calls, and unjustified # type: ignore."""
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    issues: list[str] = []
    is_any_exempt = _file_path_matches_any_exemption(file_path)

    if not is_any_exempt:
        any_annotation_issues: list[str] = []
        for each_any_line in _find_any_annotation_lines(content):
            any_annotation_issues.append(f"Line {each_any_line}: Any annotation - replace with explicit type")
        issues.extend(any_annotation_issues[:MAX_TYPE_ESCAPE_HATCH_ISSUES])

        any_import_issues: list[str] = []
        for each_import_line in _find_typing_any_imports(content):
            any_import_issues.append(
                f"Line {each_import_line}: 'from typing import Any' - remove the Any import and use explicit types"
            )
        issues.extend(any_import_issues[:MAX_TYPE_ESCAPE_HATCH_ISSUES])

        wildcard_issues: list[str] = []
        for each_wildcard_line in _find_typing_wildcard_imports(content):
            wildcard_issues.append(
                f"Line {each_wildcard_line}: 'from typing import *' wildcard import - import explicit names instead"
            )
        issues.extend(wildcard_issues[:MAX_TYPE_ESCAPE_HATCH_ISSUES])

        cast_issues: list[str] = []
        for each_cast_line in _find_cast_call_lines(content):
            cast_issues.append(
                f"Line {each_cast_line}: cast() call - escape hatch around the type system; use explicit types or runtime validation"
            )
        issues.extend(cast_issues[:MAX_TYPE_ESCAPE_HATCH_ISSUES])

    type_ignore_issues: list[str] = []
    for each_ignore_line in _find_unjustified_type_ignore_lines(content):
        type_ignore_issues.append(
            f"Line {each_ignore_line}: Unjustified # type: ignore - add trailing '# reason' explaining why"
        )
    issues.extend(type_ignore_issues[:MAX_TYPE_ESCAPE_HATCH_ISSUES])

    return issues


def is_migration_file(file_path: str) -> bool:
    """Check if file is a Django migration (must be self-contained)."""
    path_lower = file_path.lower().replace("\\", "/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in ALL_MIGRATION_PATH_PATTERNS)


def check_constants_outside_config(content: str, file_path: str) -> list[str]:
    """Check for UPPER_SNAKE constants defined outside config files."""
    if is_config_file(file_path):
        return []

    if is_test_file(file_path):
        return []

    if is_workflow_registry_file(file_path):
        return []

    if is_migration_file(file_path):
        return []

    issues = []
    lines = content.split("\n")
    is_inside_function = False
    is_inside_class = False

    constant_pattern = re.compile(r"^([A-Z][A-Z0-9_]{2,})(?:\s*:\s*[^=]+)?\s*=\s*[^=]")

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()

        if not stripped:
            continue

        if re.match(r"^(async\s+)?def\s+\w+", stripped):
            is_inside_function = True
            continue

        if re.match(r"^class\s+\w+", stripped):
            is_inside_class = True
            is_inside_function = False
            continue

        indent = len(line) - len(line.lstrip())
        if indent == 0 and stripped and not stripped.startswith(("#", "@", ")")):
            is_inside_function = False
            is_inside_class = False

        if not is_inside_function and not is_inside_class:
            match = constant_pattern.match(stripped)
            if match:
                constant_name = match.group(1)
                if constant_name not in ("__all__",):
                    issues.append(f"Line {line_number}: Constant {constant_name} - move to config/")

    return issues


def _is_exempt_for_advisory_scan(file_path: str) -> bool:
    """Return True when the file is exempt from the function-local UPPER_SNAKE advisory."""
    if is_config_file(file_path):
        return True
    if is_test_file(file_path):
        return True
    if is_workflow_registry_file(file_path):
        return True
    if is_migration_file(file_path):
        return True
    return False


def _scan_function_body_constants(content: str) -> list[str]:
    """Return advisory messages for UPPER_SNAKE assignments inside function bodies.

    Only lines inside a function body (tracked via an indent stack) are
    flagged. Module-level assignments and class-body assignments are ignored.
    """
    advisory_issues: list[str] = []
    lines = content.split("\n")
    function_indent_stack: list[int] = []
    constant_pattern = re.compile(r"^([A-Z][A-Z0-9_]{2,})(?:\s*:\s*[^=]+)?\s*=\s*[^=]")

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()

        if not stripped:
            continue

        indent = len(line) - len(line.lstrip())

        while function_indent_stack and indent <= function_indent_stack[-1] and not stripped.startswith(("#", "@", ")")):
            function_indent_stack.pop()

        if re.match(r"^class\s+\w+", stripped):
            if indent == 0:
                function_indent_stack.clear()
            continue

        if re.match(r"^(async\s+)?def\s+\w+", stripped):
            function_indent_stack.append(indent)
            continue

        if function_indent_stack:
            match = constant_pattern.match(stripped)
            if match:
                constant_name = match.group(1)
                advisory_issues.append(
                    f"Line {line_number}: Function-local constant {constant_name} - consider moving to config/"
                )

    return advisory_issues


def check_constants_outside_config_advisory(content: str, file_path: str) -> list[str]:
    """Return advisory entries for UPPER_SNAKE assignments inside function bodies.

    Module-level UPPER_SNAKE outside config/ is blocking (see
    check_constants_outside_config). Function-local UPPER_SNAKE is a softer
    smell — it belongs in config/ but does not block the write. This function
    surfaces those as advisory so callers can route them to stderr rather than
    to the blocking deny payload.
    """
    if _is_exempt_for_advisory_scan(file_path):
        return []
    return _scan_function_body_constants(content)


def _collect_target_names(target: ast.expr) -> list[ast.Name]:
    """Return every ast.Name reachable through tuple/list/starred unpacking targets."""
    if isinstance(target, ast.Name):
        return [target]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[ast.Name] = []
        for each_element in target.elts:
            names.extend(_collect_target_names(each_element))
        return names
    if isinstance(target, ast.Starred):
        return _collect_target_names(target.value)
    return []


def _collect_banned_names_from_target(target: ast.expr) -> list[ast.Name]:
    """Return every banned ast.Name reachable through tuple/list unpacking or starred targets."""
    return [
        each_name_node
        for each_name_node in _collect_target_names(target)
        if each_name_node.id in ALL_BANNED_IDENTIFIERS
    ]


def _value_is_parse_args_namespace_call(value_node: ast.AST | None) -> bool:
    if value_node is None:
        return False
    if not isinstance(value_node, ast.Call):
        return False
    callee = value_node.func
    return isinstance(callee, ast.Attribute) and callee.attr == "parse_args"


def _without_parse_args_namespace_exemption(
    all_banned_names: list[ast.Name], value_node: ast.AST | None
) -> list[ast.Name]:
    if not _value_is_parse_args_namespace_call(value_node):
        return all_banned_names
    return [each_name for each_name in all_banned_names if each_name.id != "args"]


def _synthesize_alias_name_node(
    bound_identifier: str, alias_node: ast.alias
) -> ast.Name:
    synthetic_name = ast.Name(id=bound_identifier, ctx=ast.Store())
    synthetic_name.lineno = alias_node.lineno
    synthetic_name.col_offset = alias_node.col_offset
    return synthetic_name


def _collect_banned_names_from_import(
    import_statement: ast.Import | ast.ImportFrom,
) -> list[ast.Name]:
    banned_alias_nodes: list[ast.Name] = []
    for each_alias in import_statement.names:
        bound_identifier = each_alias.asname or each_alias.name.split(".")[0]
        if bound_identifier in ALL_BANNED_IDENTIFIERS:
            banned_alias_nodes.append(
                _synthesize_alias_name_node(bound_identifier, each_alias)
            )
    return banned_alias_nodes


def _collect_banned_names_from_node(node: ast.AST) -> list[ast.Name]:
    """Return banned ast.Name nodes introduced by a single binding construct."""
    if isinstance(node, ast.Assign):
        banned_names: list[ast.Name] = []
        for each_target in node.targets:
            banned_names.extend(_collect_banned_names_from_target(each_target))
        return _without_parse_args_namespace_exemption(banned_names, node.value)
    if isinstance(node, ast.AnnAssign):
        banned_names = _collect_banned_names_from_target(node.target)
        return _without_parse_args_namespace_exemption(banned_names, node.value)
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return _collect_banned_names_from_target(node.target)
    if isinstance(node, ast.comprehension):
        return _collect_banned_names_from_target(node.target)
    if isinstance(node, ast.withitem):
        if node.optional_vars is None:
            return []
        return _collect_banned_names_from_target(node.optional_vars)
    if isinstance(node, ast.NamedExpr):
        banned_names = _collect_banned_names_from_target(node.target)
        return _without_parse_args_namespace_exemption(banned_names, node.value)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return _collect_banned_names_from_import(node)
    return []


def check_banned_identifiers(content: str, file_path: str) -> list[str]:
    """Flag assignments to identifiers banned by the project Naming rules."""
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        print(f"{file_path}: {BANNED_IDENTIFIER_SKIP_ADVISORY}", file=sys.stderr)
        return []

    banned_name_nodes: list[ast.Name] = []
    for each_node in ast.walk(parsed_tree):
        banned_name_nodes.extend(_collect_banned_names_from_node(each_node))

    banned_name_nodes.sort(key=lambda each_name: (each_name.lineno, each_name.col_offset))

    issues: list[str] = []
    for each_name in banned_name_nodes:
        issues.append(
            f"Line {each_name.lineno}: Banned identifier '{each_name.id}' - {BANNED_IDENTIFIER_MESSAGE_SUFFIX}"
        )
        if len(issues) >= MAX_BANNED_IDENTIFIER_ISSUES:
            break

    return issues


def _identifier_word_parts(identifier: str) -> list[str]:
    """Split an identifier into lowercase word parts.

    Handles snake_case (split on ``_``), SCREAMING_SNAKE_CASE, and camelCase /
    PascalCase (split on capital-letter boundaries). Returns a list of
    lowercased word tokens for membership comparison against banned-noun
    vocabularies.

    Args:
        identifier: A Python identifier (variable, parameter, class, or
            function name).

    Returns:
        Word tokens in their original order, lowercased. Empty list when the
        identifier carries no letter characters.
    """
    all_words: list[str] = []
    for each_snake_segment in identifier.split("_"):
        if not each_snake_segment:
            continue
        camel_pieces = CAMEL_CASE_WORD_PATTERN.findall(each_snake_segment)
        if camel_pieces:
            for each_piece in camel_pieces:
                all_words.append(each_piece.lower())
        else:
            all_words.append(each_snake_segment.lower())
    return all_words


def _find_banned_noun_word(identifier: str) -> str | None:
    """Return the first banned-noun word embedded in *identifier*, or None.

    Args:
        identifier: A Python identifier.

    Returns:
        The lowercased banned noun word that appears as a word part inside the
        identifier (e.g., ``'result'`` for ``'HolidayPeakResult'``). Returns
        ``None`` when no banned noun word is present.
    """
    for each_word in _identifier_word_parts(identifier):
        if each_word in ALL_BANNED_NOUN_WORDS:
            return each_word
    return None


def _is_dunder_name(identifier: str) -> bool:
    return identifier.startswith("__") and identifier.endswith("__")


def _collect_banned_noun_word_bindings(
    parsed_tree: ast.AST,
) -> list[tuple[str, int, int, str]]:
    """Yield ``(identifier, lineno, col_offset, banned_word)`` for each binding.

    Walks assignment targets, annotated assignments, function/method
    parameters, function/method definitions, and class definitions. Skips
    identifiers that already match ``ALL_BANNED_IDENTIFIERS`` exactly (those
    are reported by ``check_banned_identifiers``) and dunder names.
    """
    flagged_bindings: list[tuple[str, int, int, str]] = []
    seen_keys: set[tuple[str, int, int]] = set()

    def record(name: str, lineno: int, col_offset: int) -> None:
        if name in ALL_BANNED_IDENTIFIERS:
            return
        if _is_dunder_name(name):
            return
        banned_word = _find_banned_noun_word(name)
        if banned_word is None:
            return
        key = (name, lineno, col_offset)
        if key in seen_keys:
            return
        seen_keys.add(key)
        flagged_bindings.append((name, lineno, col_offset, banned_word))

    for each_node in ast.walk(parsed_tree):
        if isinstance(each_node, ast.Assign):
            for each_target in each_node.targets:
                for each_name_node in _collect_target_names(each_target):
                    record(each_name_node.id, each_name_node.lineno, each_name_node.col_offset)
        elif isinstance(each_node, ast.AnnAssign):
            for each_name_node in _collect_target_names(each_node.target):
                record(each_name_node.id, each_name_node.lineno, each_name_node.col_offset)
        elif isinstance(each_node, (ast.For, ast.AsyncFor)):
            for each_name_node in _collect_target_names(each_node.target):
                record(each_name_node.id, each_name_node.lineno, each_name_node.col_offset)
        elif isinstance(each_node, ast.NamedExpr) and isinstance(each_node.target, ast.Name):
            record(each_node.target.id, each_node.target.lineno, each_node.target.col_offset)
        elif isinstance(each_node, ast.comprehension):
            for each_name_node in _collect_target_names(each_node.target):
                record(each_name_node.id, each_name_node.lineno, each_name_node.col_offset)
        elif isinstance(each_node, ast.withitem) and each_node.optional_vars is not None:
            for each_name_node in _collect_target_names(each_node.optional_vars):
                record(each_name_node.id, each_name_node.lineno, each_name_node.col_offset)
        elif isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            record(each_node.name, each_node.lineno, each_node.col_offset)
            for each_arg in _collect_annotated_arguments(each_node):
                if each_arg.arg in ALL_SELF_AND_CLS_PARAMETER_NAMES:
                    continue
                record(each_arg.arg, each_arg.lineno, each_arg.col_offset)
        elif isinstance(each_node, ast.ClassDef):
            record(each_node.name, each_node.lineno, each_node.col_offset)
        elif isinstance(each_node, (ast.Import, ast.ImportFrom)):
            for each_alias in each_node.names:
                if each_alias.asname is None:
                    continue
                record(each_alias.asname, each_node.lineno, each_node.col_offset)

    flagged_bindings.sort(key=lambda binding: (binding[1], binding[2]))
    return flagged_bindings


def check_banned_noun_word_boundary(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag identifiers containing CODE_RULES §5 banned noun words.

    Companion to ``check_banned_identifiers`` (exact-match cases only). This
    check catches the wider pattern: a banned noun word from
    ``ALL_BANNED_NOUN_WORDS`` — the singular nouns ``result``, ``data``,
    ``output``, ``response``, ``value``, ``item``, ``temp`` plus the plural
    forms ``results``, ``outputs``, ``responses``, ``values``, ``items`` —
    appearing as a snake_case word part or camelCase word part inside a longer
    identifier (``canned_results``, ``HolidayPeakResult``, ``OUTPUT_DIR``,
    ``cached_response``).

    Skips test files, config files, hook infrastructure, workflow registries,
    and migrations. Identifiers that exactly match ``ALL_BANNED_IDENTIFIERS``
    are skipped because they are already reported by
    ``check_banned_identifiers``.

    Scoping mirrors ``check_function_length`` and
    ``check_tests_use_isolated_filesystem_paths`` through the shared
    ``_scope_violations_to_changed_lines`` helper. A banned-noun binding is a
    point fact about one identifier, so its enclosing unit is its own binding
    line: each violation carries the binding line as a one-line ``range`` for
    terminal diff scoping and a ``(binding span at line X, spanning 1 lines)``
    message fragment the commit gate reconstructs through the same shared span
    extractor registry the other two scoped checks use. Anchoring to the
    binding line (rather than the whole enclosing function) matches the
    companion exact-match ``check_banned_identifiers`` and keeps a pre-existing
    binding out of scope when an unrelated line of its enclosing function is
    edited. On a terminal Edit only violations whose binding line is among
    ``all_changed_lines`` are returned; on a new-file or full-file write every
    violation is in scope; ``defer_scope_to_caller`` returns every violation so
    the gate scopes by added line.

    Args:
        content: The reconstructed effective file content to analyze (the
            whole post-edit file on an Edit, the whole file at the gate).
        file_path: The path of the file being checked (used for exemption
            routing).
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a violation
            blocks only when its binding line is among the changed lines.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate's ``split_violations_by_scope`` can scope by added
            line and report the in-scope set.

    Returns:
        Issue strings, each describing one offending binding. When
        *defer_scope_to_caller* is True every binding is returned for the gate
        to scope; otherwise every binding in scope is returned.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path):
        return []
    if is_migration_file(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    single_line_span = 1
    all_violations_in_walk_order: list[tuple[range, str]] = []
    for each_name, each_lineno, _, each_word in _collect_banned_noun_word_bindings(parsed_tree):
        span_range = range(each_lineno, each_lineno + single_line_span)
        span_fragment = BANNED_NOUN_SPAN_FRAGMENT_TEMPLATE.format(
            definition_line=each_lineno, line_span=single_line_span
        )
        message = (
            f"Line {each_lineno}: Identifier {each_name!r} {BANNED_NOUN_WORD_MESSAGE_SUFFIX} "
            f"(word: {each_word!r}) {span_fragment}"
        )
        all_violations_in_walk_order.append((span_range, message))
    return _scope_violations_to_changed_lines(
        all_violations_in_walk_order,
        all_changed_lines,
        defer_scope_to_caller,
    )




def _string_constant_value(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_environ_attribute(node: ast.expr) -> bool:
    if isinstance(node, ast.Attribute) and node.attr == "environ":
        return isinstance(node.value, ast.Name) and node.value.id == "os"
    return False


def _environ_get_call_argument_names(call_node: ast.Call) -> list[str]:
    function_node = call_node.func
    if not isinstance(function_node, ast.Attribute):
        return []
    if function_node.attr != "get":
        return []
    if not _is_environ_attribute(function_node.value):
        return []
    if not call_node.args:
        return []
    first_argument = _string_constant_value(call_node.args[0])
    return [first_argument] if first_argument is not None else []


def _environ_subscript_key_names(subscript_node: ast.Subscript) -> list[str]:
    if not _is_environ_attribute(subscript_node.value):
        return []
    key = _string_constant_value(subscript_node.slice)
    return [key] if key is not None else []


def _environ_membership_key_names(compare_node: ast.Compare) -> list[str]:
    if not compare_node.ops:
        return []
    if not isinstance(compare_node.ops[0], (ast.In, ast.NotIn)):
        return []
    if not compare_node.comparators:
        return []
    if not _is_environ_attribute(compare_node.comparators[0]):
        return []
    key = _string_constant_value(compare_node.left)
    return [key] if key is not None else []


def _collect_test_env_variable_references(parsed_tree: ast.AST) -> list[tuple[int, str]]:
    references: list[tuple[int, str]] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        candidate_names: list[str] = []
        if isinstance(each_node, ast.Call):
            candidate_names = _environ_get_call_argument_names(each_node)
        elif isinstance(each_node, ast.Subscript):
            candidate_names = _environ_subscript_key_names(each_node)
        elif isinstance(each_node, ast.Compare):
            candidate_names = _environ_membership_key_names(each_node)
        for each_candidate_name in candidate_names:
            if each_candidate_name in ALL_TEST_INDICATING_ENVIRONMENT_VARIABLE_NAMES:
                references.append((each_node.lineno, each_candidate_name))
    return references


def check_test_branching_in_production(content: str, file_path: str) -> list[str]:
    """Flag production code that branches on TESTING-style env vars.

    Production code reading TESTING / PYTEST_CURRENT_TEST creates two
    parallel implementations and hides bugs. Use dependency injection
    (override the dependency in tests) instead.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    references = _collect_test_env_variable_references(parsed_tree)
    references.sort(key=lambda each_reference: each_reference[0])

    issues: list[str] = []
    already_reported_lines: set[int] = set()
    for each_line_number, each_variable_name in references:
        if each_line_number in already_reported_lines:
            continue
        already_reported_lines.add(each_line_number)
        issues.append(
            f"Line {each_line_number}: Production code reads test indicator '{each_variable_name}' — "
            "use dependency injection so production stays single-path"
        )
        if len(issues) >= MAX_TEST_BRANCHING_ISSUES:
            break

    return issues


def _bare_except_handler_label(handler_node: ast.ExceptHandler) -> str | None:
    """Return a label for handlers we flag, or None for safe handlers."""
    handler_type = handler_node.type
    if handler_type is None:
        return "bare except:"
    if isinstance(handler_type, ast.Name) and handler_type.id in ALL_BARE_EXCEPT_BANNED_HANDLER_NAMES:
        return f"except {handler_type.id}:"
    if (
        isinstance(handler_type, ast.Attribute)
        and handler_type.attr in ALL_BARE_EXCEPT_BANNED_HANDLER_NAMES
    ):
        return f"except {handler_type.attr}:"
    if isinstance(handler_type, ast.Tuple):
        banned_names: list[str] = []
        for each_element in handler_type.elts:
            if isinstance(each_element, ast.Name) and each_element.id in ALL_BARE_EXCEPT_BANNED_HANDLER_NAMES:
                banned_names.append(each_element.id)
            elif (
                isinstance(each_element, ast.Attribute)
                and each_element.attr in ALL_BARE_EXCEPT_BANNED_HANDLER_NAMES
            ):
                banned_names.append(each_element.attr)
        if banned_names:
            return f"except {', '.join(banned_names)} (in tuple):"
    return None


def check_bare_except(content: str, file_path: str) -> list[str]:
    """Flag bare/over-broad exception handlers in production code.

    ``except:`` and ``except BaseException:`` swallow KeyboardInterrupt and
    SystemExit; ``except Exception:`` hides bugs by catching nearly every
    error class. Production code should name the specific exception(s) it
    intends to catch
    (a tuple form like `except (ValueError, KeyError):` is fine).
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, ast.ExceptHandler):
            continue
        handler_label = _bare_except_handler_label(each_node)
        if handler_label is None:
            continue
        issues.append(
            f"Line {each_node.lineno}: {handler_label} is over-broad — name the "
            "specific exception(s) you intend to handle"
        )
        if len(issues) >= MAX_BARE_EXCEPT_ISSUES:
            break
    return issues


def _is_init_file(file_path: str) -> bool:
    return file_path.replace("\\", "/").rsplit("/", 1)[-1] == "__init__.py"


def _statement_is_module_docstring(statement_node: ast.stmt) -> bool:
    return (
        isinstance(statement_node, ast.Expr)
        and isinstance(statement_node.value, ast.Constant)
        and isinstance(statement_node.value.value, str)
    )


def _statement_is_dunder_all_assignment(statement_node: ast.stmt) -> bool:
    if isinstance(statement_node, ast.Assign):
        for each_target in statement_node.targets:
            if isinstance(each_target, ast.Name) and each_target.id == "__all__":
                return True
        return False
    if isinstance(statement_node, ast.AnnAssign):
        target = statement_node.target
        return isinstance(target, ast.Name) and target.id == "__all__"
    return False


def _statement_is_import_or_reexport(statement_node: ast.stmt) -> bool:
    if isinstance(statement_node, (ast.Import, ast.ImportFrom)):
        return True
    if _statement_is_dunder_all_assignment(statement_node):
        return True
    return False


def check_thin_wrapper_files(content: str, file_path: str) -> list[str]:
    """Flag non-`__init__.py` modules that are only imports + `__all__`.

    A re-export-only wrapper outside `__init__.py` forces callers through an
    indirection layer with no payload of its own. Callers should import from
    the real module. `__init__.py` is the canonical re-export surface and is
    exempt; test files, hook infrastructure, and `config/` are also exempt.
    """
    if (
        is_test_file(file_path)
        or is_hook_infrastructure(file_path)
        or is_config_file(file_path)
        or _is_init_file(file_path)
    ):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    body_statements = list(parsed_tree.body)
    if not body_statements:
        return []

    statements_after_docstring = (
        body_statements[1:]
        if _statement_is_module_docstring(body_statements[0])
        else body_statements
    )
    if not statements_after_docstring:
        return []

    for each_statement in statements_after_docstring:
        if not _statement_is_import_or_reexport(each_statement):
            return []

    issues = [
        f"Line 1: {file_path}: thin wrapper file — module body is only imports (optionally with __all__); "
        "callers should import from the real module instead of going through this indirection"
    ]
    return issues[:MAX_THIN_WRAPPER_ISSUES]


def _annotation_node_references_any(annotation_node: ast.expr | None) -> bool:
    if annotation_node is None:
        return False
    for each_descendant in ast.walk(annotation_node):
        if isinstance(each_descendant, ast.Name) and each_descendant.id == "Any":
            return True
        if isinstance(each_descendant, ast.Attribute) and each_descendant.attr == "Any":
            return True
    return False


def _file_has_exempt_boundary_filename(file_path: str) -> bool:
    filename = file_path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return filename in {each_name.lower() for each_name in ALL_BOUNDARY_TYPE_EXEMPT_FILENAMES}


def _signature_annotations(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[
    tuple[ast.expr, str, int]
]:
    collected_annotations: list[tuple[ast.expr, str, int]] = []
    function_name = function_node.name
    for each_argument in function_node.args.args:
        if each_argument.annotation is not None:
            collected_annotations.append(
                (each_argument.annotation, f"{function_name}({each_argument.arg})", each_argument.lineno)
            )
    for each_argument in function_node.args.posonlyargs:
        if each_argument.annotation is not None:
            collected_annotations.append(
                (each_argument.annotation, f"{function_name}({each_argument.arg})", each_argument.lineno)
            )
    for each_argument in function_node.args.kwonlyargs:
        if each_argument.annotation is not None:
            collected_annotations.append(
                (each_argument.annotation, f"{function_name}({each_argument.arg})", each_argument.lineno)
            )
    if function_node.args.vararg is not None and function_node.args.vararg.annotation is not None:
        collected_annotations.append(
            (function_node.args.vararg.annotation, f"{function_name}(*{function_node.args.vararg.arg})", function_node.args.vararg.lineno)
        )
    if function_node.args.kwarg is not None and function_node.args.kwarg.annotation is not None:
        collected_annotations.append(
            (function_node.args.kwarg.annotation, f"{function_name}(**{function_node.args.kwarg.arg})", function_node.args.kwarg.lineno)
        )
    if function_node.returns is not None:
        collected_annotations.append(
            (function_node.returns, f"{function_name} -> return", function_node.returns.lineno)
        )
    return collected_annotations


def _class_attribute_annotations(class_node: ast.ClassDef) -> list[tuple[ast.expr, str, int]]:
    collected_annotations: list[tuple[ast.expr, str, int]] = []
    for each_statement in class_node.body:
        if isinstance(each_statement, ast.AnnAssign) and isinstance(each_statement.target, ast.Name):
            collected_annotations.append(
                (
                    each_statement.annotation,
                    f"{class_node.name}.{each_statement.target.id}",
                    each_statement.lineno,
                )
            )
    return collected_annotations


def check_boundary_types(content: str, file_path: str) -> list[str]:
    """Flag `Any` appearing in function signatures or class attribute annotations.

    Module boundaries (function parameters, return types, class attributes)
    must name the concrete shape they accept and produce. Local variable
    annotations are private and exempt; `protocols.py` and `types.py` are
    interface-declaration files and exempt.
    """
    if (
        is_test_file(file_path)
        or is_hook_infrastructure(file_path)
        or _file_has_exempt_boundary_filename(file_path)
    ):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for each_annotation, each_label, each_line_number in _signature_annotations(each_node):
                if _annotation_node_references_any(each_annotation):
                    issues.append(
                        f"Line {each_line_number}: {each_label} uses Any at module boundary — "
                        "name the concrete shape callers receive/produce"
                    )
        elif isinstance(each_node, ast.ClassDef):
            for each_annotation, each_label, each_line_number in _class_attribute_annotations(each_node):
                if _annotation_node_references_any(each_annotation):
                    issues.append(
                        f"Line {each_line_number}: {each_label} uses Any at class boundary — "
                        "name the concrete shape this attribute holds"
                    )
        if len(issues) >= MAX_BOUNDARY_TYPE_ISSUES:
            break
    return issues[:MAX_BOUNDARY_TYPE_ISSUES]


def _function_is_private_or_dunder(function_name: str) -> bool:
    if function_name.startswith("__") and function_name.endswith("__"):
        return True
    return function_name.startswith("_")


def _decorator_label(decorator_node: ast.expr) -> str:
    if isinstance(decorator_node, ast.Name):
        return decorator_node.id
    if isinstance(decorator_node, ast.Attribute):
        prefix = (
            decorator_node.value.id
            if isinstance(decorator_node.value, ast.Name)
            else ""
        )
        return f"{prefix}.{decorator_node.attr}" if prefix else decorator_node.attr
    if isinstance(decorator_node, ast.Call):
        return _decorator_label(decorator_node.func)
    return ""


def _function_has_exempt_decorator(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    for each_decorator in function_node.decorator_list:
        if _decorator_label(each_decorator) in ALL_DOCSTRING_EXEMPT_DECORATOR_NAMES:
            return True
    return False


def _function_body_line_count(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int:
    if not function_node.body:
        return 0
    first_body_index = 0
    if (
        isinstance(function_node.body[0], ast.Expr)
        and isinstance(function_node.body[0].value, ast.Constant)
        and isinstance(function_node.body[0].value.value, str)
    ):
        if len(function_node.body) == 1:
            return 0
        first_body_index = 1
    last_statement = function_node.body[-1]
    end_line = getattr(last_statement, "end_lineno", last_statement.lineno)
    first_line = function_node.body[first_body_index].lineno
    return max(0, end_line - first_line + 1)


def _function_documentable_parameter_count(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int:
    documentable_count = 0
    for each_argument in function_node.args.args:
        if each_argument.arg in ALL_DOCSTRING_IMPLICIT_INSTANCE_PARAMETER_NAMES:
            continue
        documentable_count += 1
    documentable_count += len(function_node.args.kwonlyargs)
    for each_argument in function_node.args.posonlyargs:
        if each_argument.arg in ALL_DOCSTRING_IMPLICIT_INSTANCE_PARAMETER_NAMES:
            continue
        documentable_count += 1
    if function_node.args.vararg is not None:
        documentable_count += 1
    if function_node.args.kwarg is not None:
        documentable_count += 1
    return documentable_count


def _annotation_is_explicit_none_return(annotation_node: ast.expr | None) -> bool:
    if annotation_node is None:
        return False
    if isinstance(annotation_node, ast.Constant) and annotation_node.value is None:
        return True
    return isinstance(annotation_node, ast.Name) and annotation_node.id == "None"


def _annotation_is_noreturn(annotation_node: ast.expr | None) -> bool:
    if annotation_node is None:
        return False
    if isinstance(annotation_node, ast.Name) and annotation_node.id == "NoReturn":
        return True
    return isinstance(annotation_node, ast.Attribute) and annotation_node.attr == "NoReturn"


def _walk_skipping_nested_functions(node: ast.AST) -> "Iterator[ast.AST]":
    for each_child in ast.iter_child_nodes(node):
        if isinstance(each_child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield each_child
        yield from _walk_skipping_nested_functions(each_child)


def _is_type_checking_guard(if_node: ast.If) -> bool:
    test_node = if_node.test
    if isinstance(test_node, ast.Name) and test_node.id == TYPE_CHECKING_IDENTIFIER:
        return True
    return isinstance(test_node, ast.Attribute) and test_node.attr == TYPE_CHECKING_IDENTIFIER


def _walk_skipping_type_checking_blocks(node: ast.AST) -> "Iterator[ast.AST]":
    for each_child in ast.iter_child_nodes(node):
        if isinstance(each_child, ast.If) and _is_type_checking_guard(each_child):
            continue
        yield each_child
        yield from _walk_skipping_type_checking_blocks(each_child)


def _function_body_contains_raise(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    return any(
        isinstance(each_descendant, ast.Raise)
        for each_descendant in _walk_skipping_nested_functions(function_node)
    )


def _function_body_contains_yield(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    return any(
        isinstance(each_descendant, (ast.Yield, ast.YieldFrom))
        for each_descendant in _walk_skipping_nested_functions(function_node)
    )


def _function_docstring_text(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> str:
    docstring_value = ast.get_docstring(function_node)
    return docstring_value or ""


def _missing_docstring_sections(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[str]:
    docstring_text = _function_docstring_text(function_node)
    documentable_parameter_count = _function_documentable_parameter_count(function_node)
    has_non_none_return = (
        function_node.returns is not None
        and not _annotation_is_explicit_none_return(function_node.returns)
        and not _annotation_is_noreturn(function_node.returns)
    )
    has_raise_statement = _function_body_contains_raise(function_node)
    has_yield_statement = _function_body_contains_yield(function_node)
    missing_sections: list[str] = []
    if documentable_parameter_count > 0 and "Args:" not in docstring_text:
        missing_sections.append("Args:")
    if has_non_none_return and not (
        "Returns:" in docstring_text or "Yields:" in docstring_text
    ):
        section_label = "Yields:" if has_yield_statement else "Returns:"
        missing_sections.append(section_label)
    if has_raise_statement and "Raises:" not in docstring_text:
        missing_sections.append("Raises:")
    return missing_sections


def check_docstring_format(content: str, file_path: str) -> list[str]:
    """Flag public functions missing required Google-style docstring sections.

    A public function whose signature has documentable parameters, returns
    a non-None value, or raises must have the matching `Args:` / `Returns:`
    (or `Yields:`) / `Raises:` sections so callers can read the contract
    without scanning the body.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _function_is_private_or_dunder(each_node.name):
            continue
        if _function_has_exempt_decorator(each_node):
            continue
        if _function_body_line_count(each_node) <= DOCSTRING_TRIVIAL_FUNCTION_BODY_LINE_LIMIT:
            continue
        missing_sections = _missing_docstring_sections(each_node)
        if not missing_sections:
            continue
        issues.append(
            f"Line {each_node.lineno}: {each_node.name}() docstring missing required "
            f"section(s): {', '.join(missing_sections)} — Google style required for public APIs"
        )
        if len(issues) >= MAX_DOCSTRING_FORMAT_ISSUES:
            break
    return issues[:MAX_DOCSTRING_FORMAT_ISSUES]


def _signature_parameter_names(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    arguments = function_node.args
    real_names: set[str] = set()
    for each_argument in arguments.posonlyargs + arguments.args + arguments.kwonlyargs:
        real_names.add(each_argument.arg)
    if arguments.vararg is not None:
        real_names.add(arguments.vararg.arg)
    if arguments.kwarg is not None:
        real_names.add(arguments.kwarg.arg)
    return real_names - ALL_SELF_AND_CLS_PARAMETER_NAMES


def _is_docstring_terminating_section_header(stripped_line: str) -> bool:
    return stripped_line in ALL_DOCSTRING_TERMINATING_SECTION_HEADERS


def _documented_argument_names(docstring_text: str) -> list[str]:
    docstring_lines = docstring_text.splitlines()
    args_section_index = _find_args_section_index(docstring_lines)
    if args_section_index is None:
        return []
    documented_names: list[str] = []
    entry_indent: int | None = None
    for each_line in docstring_lines[args_section_index + 1:]:
        stripped_line = each_line.strip()
        if not stripped_line:
            continue
        if _is_docstring_terminating_section_header(stripped_line):
            break
        current_indent = len(each_line) - len(each_line.lstrip())
        if current_indent == 0:
            break
        if entry_indent is None:
            entry_indent = current_indent
        if current_indent > entry_indent:
            continue
        entry_match = DOCSTRING_ARG_ENTRY_PATTERN.match(stripped_line)
        if entry_match is not None:
            documented_names.append(entry_match.group(1))
    return documented_names


def _find_args_section_index(all_docstring_lines: list[str]) -> int | None:
    for each_line_index, each_line in enumerate(all_docstring_lines):
        if each_line.strip() in ALL_DOCSTRING_ARGS_SECTION_HEADERS:
            return each_line_index
    return None


def check_docstring_args_match_signature(content: str, file_path: str) -> list[str]:
    """Flag docstring Args: entries naming a parameter the signature lacks.

    A fix that renames a parameter often leaves the adjacent ``Args:`` line
    stale. Each documented argument name is compared to the real signature;
    a documented name with no matching parameter is reported. Only the
    ``Args:`` section is validated — ``Raises:`` is left alone because
    callee-propagated exceptions cause false positives. Functions that
    accept ``**kwargs`` are skipped because their documented names may be
    keyword keys the signature cannot enumerate.

    Args:
        content: The source text to inspect.
        file_path: The path the source will be written to, used for exemptions.

    Returns:
        One issue per stale documented argument, capped at the module limit.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _function_is_private_or_dunder(each_node.name):
            continue
        if _function_has_exempt_decorator(each_node):
            continue
        if _function_body_line_count(each_node) <= DOCSTRING_TRIVIAL_FUNCTION_BODY_LINE_LIMIT:
            continue
        if each_node.args.kwarg is not None:
            continue
        documented_names = _documented_argument_names(_function_docstring_text(each_node))
        if not documented_names:
            continue
        real_names = _signature_parameter_names(each_node)
        for each_documented_name in documented_names:
            if each_documented_name in real_names:
                continue
            issues.append(
                f"Line {each_node.lineno}: {each_node.name}() docstring Args: lists "
                f"'{each_documented_name}' which is not a parameter - update the "
                "docstring to match the signature"
            )
            if len(issues) >= MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES:
                return issues[:MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES]
    return issues[:MAX_DOCSTRING_ARGS_SIGNATURE_ISSUES]


_PASCAL_TO_SNAKE_WORD_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _pascal_to_snake_case(pascal_name: str) -> str:
    return _PASCAL_TO_SNAKE_WORD_BOUNDARY.sub("_", pascal_name).lower()


def _class_inherits_from_typed_dict(class_node: ast.ClassDef) -> bool:
    for each_base in class_node.bases:
        if isinstance(each_base, ast.Name) and each_base.id == "TypedDict":
            return True
        if isinstance(each_base, ast.Attribute) and each_base.attr == "TypedDict":
            return True
    return False


def _collect_typed_dict_class_names(parsed_tree: ast.AST) -> list[tuple[str, int]]:
    typed_dict_entries: list[tuple[str, int]] = []
    for each_statement in parsed_tree.body:
        if isinstance(each_statement, ast.ClassDef) and _class_inherits_from_typed_dict(each_statement):
            typed_dict_entries.append((each_statement.name, each_statement.lineno))
    return typed_dict_entries


def _collect_module_function_names(parsed_tree: ast.AST) -> set[str]:
    module_function_names: set[str] = set()
    for each_statement in parsed_tree.body:
        if isinstance(each_statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            module_function_names.add(each_statement.name)
    return module_function_names


def check_typed_dict_encode_decode(content: str, file_path: str) -> list[str]:
    """Flag TypedDict declarations missing companion `_encode_*` / `_decode_*` functions."""
    if (
        is_test_file(file_path)
        or is_hook_infrastructure(file_path)
        or _is_init_file(file_path)
    ):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    typed_dict_entries = _collect_typed_dict_class_names(parsed_tree)
    if not typed_dict_entries:
        return []

    module_function_names = _collect_module_function_names(parsed_tree)

    issues: list[str] = []
    for each_typed_dict_name, each_typed_dict_line in typed_dict_entries:
        snake_name = _pascal_to_snake_case(each_typed_dict_name)
        encoder_function_name = f"_encode_{snake_name}"
        decoder_function_name = f"_decode_{snake_name}"
        is_encoder_present = encoder_function_name in module_function_names
        is_decoder_present = decoder_function_name in module_function_names
        if is_encoder_present and is_decoder_present:
            continue
        missing_companions: list[str] = []
        if not is_encoder_present:
            missing_companions.append(encoder_function_name)
        if not is_decoder_present:
            missing_companions.append(decoder_function_name)
        issues.append(
            f"Line {each_typed_dict_line}: TypedDict '{each_typed_dict_name}' missing companion "
            f"{' and '.join(missing_companions)} — add explicit encode/decode functions"
        )
        if len(issues) >= MAX_TYPED_DICT_PAIR_ISSUES:
            break

    return issues


def _function_decorator_is_abstractmethod(decorator_node: ast.expr) -> bool:
    if isinstance(decorator_node, ast.Name) and decorator_node.id == "abstractmethod":
        return True
    if isinstance(decorator_node, ast.Attribute) and decorator_node.attr == "abstractmethod":
        return True
    return False


def _function_is_abstract(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        _function_decorator_is_abstractmethod(each_decorator)
        for each_decorator in function_node.decorator_list
    )


def _function_is_overload(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for each_decorator in function_node.decorator_list:
        if isinstance(each_decorator, ast.Name) and each_decorator.id == "overload":
            return True
        if isinstance(each_decorator, ast.Attribute) and each_decorator.attr == "overload":
            return True
    return False


def _class_is_protocol(class_node: ast.ClassDef) -> bool:
    for each_base in class_node.bases:
        if isinstance(each_base, ast.Name) and each_base.id == "Protocol":
            return True
        if isinstance(each_base, ast.Attribute) and each_base.attr == "Protocol":
            return True
    return False


def _class_inherits_from_protocol_or_abc(class_node: ast.ClassDef) -> bool:
    for each_base in class_node.bases:
        if isinstance(each_base, ast.Name) and each_base.id in {"Protocol", "ABC"}:
            return True
        if isinstance(each_base, ast.Attribute) and each_base.attr in {"Protocol", "ABC"}:
            return True
    return False






def _statement_is_pass(statement_node: ast.stmt) -> bool:
    return isinstance(statement_node, ast.Pass)


def _statement_is_ellipsis(statement_node: ast.stmt) -> bool:
    return (
        isinstance(statement_node, ast.Expr)
        and isinstance(statement_node.value, ast.Constant)
        and statement_node.value.value is Ellipsis
    )


def _statement_is_raise_not_implemented(statement_node: ast.stmt) -> bool:
    if not isinstance(statement_node, ast.Raise):
        return False
    raised_expression = statement_node.exc
    if raised_expression is None:
        return False
    if isinstance(raised_expression, ast.Name) and raised_expression.id == "NotImplementedError":
        return True
    if (
        isinstance(raised_expression, ast.Call)
        and isinstance(raised_expression.func, ast.Name)
        and raised_expression.func.id == "NotImplementedError"
    ):
        return True
    return False


def _function_body_is_stub(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body_statements = list(function_node.body)
    if body_statements and _statement_is_module_docstring(body_statements[0]):
        body_statements = body_statements[1:]
    if len(body_statements) != 1:
        return False
    sole_statement = body_statements[0]
    return (
        _statement_is_pass(sole_statement)
        or _statement_is_ellipsis(sole_statement)
        or _statement_is_raise_not_implemented(sole_statement)
    )


def check_stub_implementations(content: str, file_path: str) -> list[str]:
    """Flag production functions whose body is only pass/.../raise NotImplementedError.

    Stubs ship as placeholders that the rest of the system depends on but the
    function does not deliver. ABC/Protocol abstract methods are exempt — they
    are placeholders BY contract, not by oversight.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    abstract_class_function_ids: set[int] = set()
    for each_node in ast.walk(parsed_tree):
        if isinstance(each_node, ast.ClassDef) and _class_inherits_from_protocol_or_abc(each_node):
            is_protocol = _class_is_protocol(each_node)
            for each_class_member in each_node.body:
                if not isinstance(each_class_member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if is_protocol or _function_is_abstract(each_class_member):
                    abstract_class_function_ids.add(id(each_class_member))

    stub_function_nodes: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _function_is_abstract(each_node) or _function_is_overload(each_node):
            continue
        if id(each_node) in abstract_class_function_ids:
            continue
        if _function_body_is_stub(each_node):
            stub_function_nodes.append(each_node)

    stub_function_nodes.sort(key=lambda each_function: each_function.lineno)

    issues: list[str] = []
    for each_function in stub_function_nodes:
        issues.append(
            f"Line {each_function.lineno}: Function '{each_function.name}' is a stub "
            "(pass/.../raise NotImplementedError) — implement or remove"
        )
        if len(issues) >= MAX_STUB_IMPLEMENTATION_ISSUES:
            break

    return issues


def check_banned_prefixes(content: str, file_path: str) -> list[str]:
    """Flag function and method names using generic banned prefixes.

    Per CODE_RULES.md / AGENTS.md Naming, function names use specific verbs.
    Generic prefixes ``handle_``, ``process_``, ``manage_``, ``do_`` are
    placeholders that hide the actual responsibility and are flagged so the
    author renames the function to a specific verb.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path) or is_config_file(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    flagged_function_nodes: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if any(each_node.name.startswith(each_prefix) for each_prefix in ALL_BANNED_PREFIX_NAMES):
            flagged_function_nodes.append(each_node)

    flagged_function_nodes.sort(key=lambda each_function: each_function.lineno)

    issues: list[str] = []
    for each_function in flagged_function_nodes:
        issues.append(
            f"Line {each_function.lineno}: Function '{each_function.name}' uses banned prefix - "
            "rename to a specific verb (see CODE_RULES Naming section)"
        )
        if len(issues) >= MAX_BANNED_PREFIX_ISSUES:
            break

    return issues


def _is_bool_constant(node: ast.AST) -> bool:
    return isinstance(node, ast.Constant) and isinstance(node.value, bool)


def _rhs_names_if_all_bool(value_node: ast.AST, target_node: ast.AST) -> list[str]:
    """Return names from a tuple assignment target when every RHS element is a bool constant.

    Handles cases like `valid, permitted = True, False` where target is a Tuple
    and value is a Tuple of bool constants. Returns empty list otherwise.
    """
    if not isinstance(target_node, ast.Tuple):
        return []
    if not isinstance(value_node, ast.Tuple):
        return []
    if len(target_node.elts) != len(value_node.elts):
        return []
    if not all(_is_bool_constant(element) for element in value_node.elts):
        return []
    names: list[str] = []
    for element in target_node.elts:
        if isinstance(element, ast.Name):
            names.append(element.id)
    return names


def _assign_target_names_for_bool(node: ast.Assign) -> list[str]:
    if not node.targets:
        return []
    names: list[str] = []
    for target in node.targets:
        if isinstance(target, ast.Name) and _is_bool_constant(node.value):
            names.append(target.id)
        else:
            names.extend(_rhs_names_if_all_bool(node.value, target))
    return names


def _annassign_target_name_for_bool(node: ast.AnnAssign) -> list[str]:
    if not isinstance(node.target, ast.Name):
        return []
    is_annotation_bool_type = isinstance(node.annotation, ast.Name) and node.annotation.id == "bool"
    is_value_bool_constant = node.value is not None and _is_bool_constant(node.value)
    if is_annotation_bool_type and is_value_bool_constant:
        return [node.target.id]
    return []


def _walrus_name_for_bool(node: ast.NamedExpr) -> list[str]:
    if not isinstance(node.target, ast.Name):
        return []
    if not _is_bool_constant(node.value):
        return []
    return [node.target.id]


def _collect_boolean_assignments(tree: ast.Module) -> list[tuple[str, int, bool]]:
    """Collect boolean-constant assignments with (name, line_number, is_upper_snake_scope).

    `is_upper_snake_scope` is True for module-level statements and direct class body
    statements, where UPPER_SNAKE constants are acceptable (dataclass fields, class
    constants). Function/method scope is False.

    Invariant: relies on `ast.walk` returning the same node instances that were
    stored in `upper_snake_scope_ids` via their `id()`. Do not call this helper
    on a tree that has been rebuilt through an `ast.NodeTransformer` — the
    transformer may replace nodes with fresh instances, and the identity-based
    scope tagging will silently fail for the replaced nodes.
    """
    upper_snake_scope_ids: set[int] = set()
    for statement in tree.body:
        upper_snake_scope_ids.add(id(statement))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for class_statement in node.body:
                upper_snake_scope_ids.add(id(class_statement))
    collected: list[tuple[str, int, bool]] = []
    for node in ast.walk(tree):
        names: list[str] = []
        line_number = 0
        if isinstance(node, ast.Assign):
            names = _assign_target_names_for_bool(node)
            line_number = node.lineno
        elif isinstance(node, ast.AnnAssign):
            names = _annassign_target_name_for_bool(node)
            line_number = node.lineno
        elif isinstance(node, ast.NamedExpr):
            names = _walrus_name_for_bool(node)
            line_number = node.lineno
        if not names:
            continue
        is_in_upper_snake_scope = id(node) in upper_snake_scope_ids
        for name in names:
            collected.append((name, line_number, is_in_upper_snake_scope))
    return collected


def _argument_is_boolean(argument_node: ast.arg, default_node: ast.expr | None) -> bool:
    annotation_is_bool = (
        isinstance(argument_node.annotation, ast.Name)
        and argument_node.annotation.id == "bool"
    )
    default_is_bool = default_node is not None and _is_bool_constant(default_node)
    return annotation_is_bool or default_is_bool


def _bool_parameters_for_function(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[tuple[str, int]]:
    arguments = function_node.args
    positional_arguments = arguments.posonlyargs + arguments.args
    positional_defaults = arguments.defaults
    leading_without_default = len(positional_arguments) - len(positional_defaults)
    bool_parameters: list[tuple[str, int]] = []
    for each_position, each_argument in enumerate(positional_arguments):
        default_index = each_position - leading_without_default
        default_node = (
            positional_defaults[default_index] if default_index >= 0 else None
        )
        if each_argument.arg in ALL_SELF_AND_CLS_PARAMETER_NAMES:
            continue
        if _argument_is_boolean(each_argument, default_node):
            bool_parameters.append((each_argument.arg, each_argument.lineno))
    for each_argument, each_default in zip(arguments.kwonlyargs, arguments.kw_defaults):
        if each_argument.arg in ALL_SELF_AND_CLS_PARAMETER_NAMES:
            continue
        if _argument_is_boolean(each_argument, each_default):
            bool_parameters.append((each_argument.arg, each_argument.lineno))
    return bool_parameters


def _collect_bool_parameter_names(tree: ast.Module) -> list[tuple[str, int]]:
    """Collect (name, line_number) for boolean-typed function parameters.

    A parameter counts as boolean when its annotation is the ``bool`` name or
    its default is a boolean literal. ``self`` and ``cls`` are skipped.

    Args:
        tree: The parsed module to inspect.

    Returns:
        Each boolean parameter as a (name, line_number) pair.
    """
    bool_parameters: list[tuple[str, int]] = []
    for each_node in ast.walk(tree):
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bool_parameters.extend(_bool_parameters_for_function(each_node))
    return bool_parameters


def check_boolean_naming(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag boolean assignments and parameters whose name lacks a required prefix.

    The caller passes the reconstructed full file as *content* so ``ast.parse``
    sees a complete module rather than an Edit's ``new_string`` fragment, which is
    rarely valid standalone Python. Findings are then scoped to *all_changed_lines*
    so an Edit blocks on the unprefixed boolean it just introduced while a
    pre-existing violation on an untouched line does not block the edit.

    Args:
        content: The source text to inspect — the reconstructed full file on an
            Edit so the parse succeeds.
        file_path: The path the source will be written to, used for exemptions.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a violation
            blocks only when its source line intersects the changed lines.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate's ``split_violations_by_scope`` can scope by added
            line.

    Returns:
        One issue per unprefixed boolean assignment and parameter, scoped to the
        changed lines unless *defer_scope_to_caller* is True or *all_changed_lines*
        is None. This check has no module cap.
    """
    if is_test_file(file_path):
        return []
    if is_hook_infrastructure(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError as parse_error:
        print(
            f"[CODE_RULES advisory] {file_path}: boolean-naming check skipped - "
            f"SyntaxError at line {parse_error.lineno}: {parse_error.msg}",
            file=sys.stderr,
        )
        return []
    all_violations_in_walk_order: list[tuple[range, str]] = []
    for each_name, each_line_number, each_is_in_upper_snake_scope in _collect_boolean_assignments(tree):
        if len(each_name) == 1:
            continue
        if each_is_in_upper_snake_scope and UPPER_SNAKE_CONSTANT_PATTERN.match(each_name):
            continue
        if each_name.startswith(ALL_BOOLEAN_NAME_PREFIXES):
            continue
        message = (
            f"Line {each_line_number}: Boolean {each_name} - prefix with "
            "is_/has_/should_/can_/was_/did_"
        )
        all_violations_in_walk_order.append(
            (range(each_line_number, each_line_number + 1), message)
        )
    for each_name, each_line_number in _collect_bool_parameter_names(tree):
        if len(each_name) == 1:
            continue
        if each_name.startswith(ALL_BOOLEAN_NAME_PREFIXES):
            continue
        message = (
            f"Line {each_line_number}: Boolean parameter {each_name} - prefix with "
            "is_/has_/should_/can_/was_/did_"
        )
        all_violations_in_walk_order.append(
            (range(each_line_number, each_line_number + 1), message)
        )
    return _scope_violations_to_changed_lines(
        all_violations_in_walk_order,
        all_changed_lines,
        defer_scope_to_caller,
    )


def _called_terminal_name(call_node: ast.Call) -> str | None:
    callee = call_node.func
    if isinstance(callee, ast.Name):
        return callee.id
    if isinstance(callee, ast.Attribute):
        return callee.attr
    return None


def check_ignored_must_check_return(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag bare-expression calls whose discarded return is the only failure signal.

    Functions in ``ALL_MUST_CHECK_RETURN_FUNCTION_NAMES`` report success or failure
    solely through their return value. A bare-statement call discards that value,
    so the caller silently proceeds on failure. Bare ``ast.Expr`` calls are flagged,
    including a bare ``await``-wrapped call (``await find_and_click(...)`` as a
    statement); an assigned or branched-on call is exempt.

    The caller passes the reconstructed full file as *content* so ``ast.parse``
    sees a complete module rather than an Edit's ``new_string`` fragment, which is
    rarely valid standalone Python (a bare ``await find_and_click(...)`` line is a
    SyntaxError on its own). Findings are then scoped to *all_changed_lines* so an
    Edit blocks on the discarded return it just introduced while a pre-existing
    violation on an untouched line does not block the edit.

    Args:
        content: The source text to inspect — the reconstructed full file on an
            Edit so the parse succeeds.
        file_path: The path the source will be written to, used for exemptions.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a violation
            blocks only when the bare call's line intersects the changed lines.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate's ``split_violations_by_scope`` can scope by added
            line.

    Returns:
        One issue per discarded must-check return, scoped to the changed lines
        unless *defer_scope_to_caller* is True or *all_changed_lines* is None. When
        *defer_scope_to_caller* is True every violation is returned uncapped so the
        gate can scope by added line and apply its own ceiling; otherwise the
        terminal result is capped at the module limit.
    """
    if is_test_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    all_violations_in_walk_order: list[tuple[range, str]] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Expr):
            continue
        expression_value = each_node.value
        call_node = (
            expression_value.value
            if isinstance(expression_value, ast.Await)
            else expression_value
        )
        if not isinstance(call_node, ast.Call):
            continue
        called_name = _called_terminal_name(call_node)
        if called_name is None or called_name not in ALL_MUST_CHECK_RETURN_FUNCTION_NAMES:
            continue
        end_line_number = each_node.end_lineno or each_node.lineno
        line_span = range(each_node.lineno, end_line_number + 1)
        message = (
            f"Line {each_node.lineno}: return value of {called_name}() is discarded - "
            "assign and check it (the boolean/outcome is the only failure signal)"
        )
        all_violations_in_walk_order.append((line_span, message))
    scoped_issues = _scope_violations_to_changed_lines(
        all_violations_in_walk_order,
        all_changed_lines,
        defer_scope_to_caller,
    )
    if defer_scope_to_caller:
        return scoped_issues
    return scoped_issues[:MAX_IGNORED_MUST_CHECK_RETURN_ISSUES]


def _decorator_name_contains_skip(decorator_node: ast.expr) -> bool:
    """Return True when a decorator AST node references an identifier containing 'skip'."""
    if isinstance(decorator_node, ast.Name):
        return "skip" in decorator_node.id.lower()
    if isinstance(decorator_node, ast.Attribute):
        return "skip" in decorator_node.attr.lower()
    if isinstance(decorator_node, ast.Call):
        return _decorator_name_contains_skip(decorator_node.func)
    return False


def check_skip_decorators_in_tests(content: str, file_path: str) -> list[str]:
    """Flag @skip decorators on test functions in test files.

    Tests must fail on missing dependencies rather than skip silently.
    Only applies to test files; production files are exempt.
    Only flags decorators applied to functions whose names start with 'test'.
    """
    if not is_test_file(file_path):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not each_node.name.startswith("test"):
            continue
        for each_decorator in each_node.decorator_list:
            if _decorator_name_contains_skip(each_decorator):
                issues.append(
                    f"Line {each_decorator.lineno}: @skip decorator on test"
                    f" — tests must fail on missing deps"
                )

    return issues


def _dotted_call_attribute_chain(call_node: ast.Call) -> str | None:
    """Return the dotted name path of *call_node*'s callee, or None.

    For ``pathlib.Path.home()`` returns ``"pathlib.Path.home"``; for
    ``Path.home()`` returns ``"Path.home"``; for ``tempfile.gettempdir()``
    returns ``"tempfile.gettempdir"``. Returns ``None`` when the call target
    is not a pure attribute chain rooted at an ``ast.Name`` (for example,
    ``obj.method()`` where ``obj`` is the result of another expression).
    """
    chain_parts: list[str] = []
    walker: ast.expr = call_node.func
    while isinstance(walker, ast.Attribute):
        chain_parts.append(walker.attr)
        walker = walker.value
    if not isinstance(walker, ast.Name):
        return None
    chain_parts.append(walker.id)
    chain_parts.reverse()
    return ".".join(chain_parts)


def _record_probe_import_aliases(
    import_node: ast.Import | ast.ImportFrom,
    all_canonical_names_by_alias: dict[str, str],
) -> None:
    """Record the probe-relevant alias entries from a single import statement.

    Module aliases are recorded only for the probe-relevant modules in
    ``ALL_PROBE_RELEVANT_MODULE_CANONICAL_NAMES``. Bare-imported names are
    recorded only for the ``(module, name)`` pairs in
    ``ALL_CANONICAL_DOTTED_NAMES_BY_BARE_IMPORT``. Imports outside those sets are
    ignored so unrelated bindings never rewrite a chain.

    Args:
        import_node: A single ``ast.Import`` or ``ast.ImportFrom`` statement.
        all_canonical_names_by_alias: The alias map to mutate in place with any
            probe-relevant local-name to canonical-dotted-prefix entries.
    """
    if isinstance(import_node, ast.Import):
        for each_alias in import_node.names:
            if each_alias.name not in ALL_PROBE_RELEVANT_MODULE_CANONICAL_NAMES:
                continue
            local_name = each_alias.asname or each_alias.name
            all_canonical_names_by_alias[local_name] = each_alias.name
        return
    for each_alias in import_node.names:
        canonical_dotted = ALL_CANONICAL_DOTTED_NAMES_BY_BARE_IMPORT.get(
            (import_node.module or "", each_alias.name)
        )
        if canonical_dotted is None:
            continue
        local_name = each_alias.asname or each_alias.name
        all_canonical_names_by_alias[local_name] = canonical_dotted


def _build_alias_canonicalization_map(syntax_tree: ast.Module) -> dict[str, str]:
    """Map each module-level probe import local name to its canonical prefix.

    Resolves both module aliases and bare-imported names so a dotted-call
    chain rooted at any module-level binding rewrites to the canonical form the
    probe set already matches:

    - ``import os as o`` -> ``o`` resolves to ``os`` (so ``o.getenv`` ->
      ``os.getenv`` and ``o.path.expanduser`` -> ``os.path.expanduser``).
    - ``import os.path as op`` -> ``op`` resolves to ``os.path`` (so
      ``op.expanduser`` -> ``os.path.expanduser``).
    - ``import pathlib as pl`` -> ``pl`` resolves to ``pathlib``.
    - ``from pathlib import Path as P`` -> ``P`` resolves to ``Path``.
    - ``from os import path`` -> ``path`` resolves to ``os.path`` (so
      ``path.expanduser`` -> ``os.path.expanduser``).
    - ``from os.path import expanduser as e`` -> ``e`` resolves to
      ``os.path.expanduser``; ``from os import getenv`` -> ``getenv``
      resolves to ``os.getenv``; ``from os import environ`` -> ``environ``
      resolves to ``os.environ``.

    An import is module-scoped — and enters this shared map — when it is not
    lexically inside any ``FunctionDef``/``AsyncFunctionDef``/``ClassDef`` body.
    That admits top-level imports nested in module-level ``try``/``except``,
    ``if``, or ``with`` blocks (the ``try: import os as o except ImportError:``
    optional-import idiom binds ``o`` module-wide) while excluding both
    function-local and class-body imports. A function-local import binds its
    name only inside the function it appears in, and a class-body import binds
    its alias only within the class namespace; neither may enter this shared,
    module-wide map — otherwise a probe import inside one test would
    canonicalize a same-named reference in a sibling test that never imported
    it. Function-local imports are scoped to their own function by
    ``_collect_local_probe_alias_bindings``.

    Args:
        syntax_tree: The parsed module to scan for module-scoped import
            statements.

    Returns:
        Mapping from module-level local binding name to its canonical dotted
        prefix.
    """
    parent_by_child_id = _build_parent_map(syntax_tree)
    all_canonical_names_by_alias: dict[str, str] = {}
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, (ast.Import, ast.ImportFrom)):
            continue
        if _node_is_lexically_inside_function_or_class(each_node, parent_by_child_id):
            continue
        _record_probe_import_aliases(each_node, all_canonical_names_by_alias)
    return all_canonical_names_by_alias


def _node_is_lexically_inside_function_or_class(
    node: ast.AST, parent_by_child_id: dict[int, ast.AST],
) -> bool:
    """Return True when *node* is nested inside a function or class body.

    Walks ancestors via *parent_by_child_id*. A node nested only inside
    module-level ``try``/``if``/``with`` blocks has no enclosing function or
    class and is module-scoped; a node inside a
    ``FunctionDef``/``AsyncFunctionDef``/``ClassDef`` body is scoped to that
    enclosing definition and is not module-scoped. A class-body import binds
    its alias only within the class namespace, so it must not enter the
    module-wide alias map any more than a function-local import does.

    Args:
        node: The node whose lexical scope is being classified.
        parent_by_child_id: Child-``id()``-to-parent map from
            ``_build_parent_map``.

    Returns:
        True when an enclosing
        ``FunctionDef``/``AsyncFunctionDef``/``ClassDef`` exists.
    """
    current_ancestor = parent_by_child_id.get(id(node))
    while current_ancestor is not None:
        if isinstance(
            current_ancestor,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            return True
        current_ancestor = parent_by_child_id.get(id(current_ancestor))
    return False


def _collect_os_environ_local_binding_names(
    scope_node: ast.FunctionDef | ast.AsyncFunctionDef,
    all_canonical_names_by_alias: dict[str, str],
) -> set[str]:
    """Return local names bound to ``os.environ`` within *scope_node*.

    Scoped to the single test function passed as *scope_node* so a binding in
    one test never attributes a same-named access in a sibling test. Tracks
    ``e = os.environ`` style assignments (resolving the right-hand side through
    *all_canonical_names_by_alias* so ``e = o.environ`` with ``import os as o``
    is recognized) and ``from os import environ`` bindings (rare inside a
    function but supported for completeness). Subscript and ``.get(...)`` reads
    on these local names are treated as ``os.environ`` accesses.

    Args:
        scope_node: The single test function node to scan for bindings.
        all_canonical_names_by_alias: Import-alias map from
            ``_build_alias_canonicalization_map``.

    Returns:
        Set of local variable names that reference ``os.environ``.
    """
    environ_bindings: set[str] = set()
    for each_node in _descend_within_test_scope(scope_node):
        if isinstance(each_node, ast.ImportFrom):
            for each_alias in each_node.names:
                canonical_dotted = ALL_CANONICAL_DOTTED_NAMES_BY_BARE_IMPORT.get(
                    (each_node.module or "", each_alias.name)
                )
                if canonical_dotted == OS_ENVIRON_DOTTED_NAME:
                    environ_bindings.add(each_alias.asname or each_alias.name)
            continue
        if not isinstance(each_node, ast.Assign):
            continue
        if not _attribute_chain_resolves_to_os_environ(each_node.value, all_canonical_names_by_alias):
            continue
        for each_target in each_node.targets:
            if isinstance(each_target, ast.Name):
                environ_bindings.add(each_target.id)
    return environ_bindings


def _collect_pathlib_path_local_binding_names(
    scope_node: ast.FunctionDef | ast.AsyncFunctionDef,
    all_canonical_names_by_alias: dict[str, str],
) -> set[str]:
    """Return local names bound to a home-tilde ``pathlib.Path(...)`` construction.

    Scoped to the single test function passed as *scope_node* so a binding in
    one test never attributes a same-named ``.expanduser()`` call in a sibling
    test. Tracks ``candidate = Path('~/x')`` style assignments whose first
    constructor argument is a literal string beginning with ``~`` (resolving
    the constructor through *all_canonical_names_by_alias* so an aliased
    ``candidate = P('~/x')`` with ``from pathlib import Path as P`` and a
    fully qualified ``candidate = pathlib.Path('~/x')`` are both recognized).
    A later ``candidate.expanduser()`` call on such a name is attributed to a
    home-directory probe. A tilde-free or dynamic constructor argument
    (``Path('/tmp/x')`` / ``Path(some_path)``) expands no home directory and
    is not collected, keeping the instance ``.expanduser()`` form symmetric
    with ``os.path.expanduser`` argument inspection.

    Args:
        scope_node: The single test function node to scan for bindings.
        all_canonical_names_by_alias: Import-alias map from
            ``_build_alias_canonicalization_map``.

    Returns:
        Set of local variable names bound to a home-tilde ``pathlib.Path``
        construction.
    """
    path_bindings: set[str] = set()
    for each_node in _descend_within_test_scope(scope_node):
        if not isinstance(each_node, ast.Assign):
            continue
        if not _pathlib_path_construction_uses_home_tilde(
            each_node.value, all_canonical_names_by_alias
        ):
            continue
        for each_target in each_node.targets:
            if isinstance(each_target, ast.Name):
                path_bindings.add(each_target.id)
    return path_bindings


def _collect_local_probe_alias_bindings(
    scope_node: ast.FunctionDef | ast.AsyncFunctionDef,
    all_canonical_names_by_alias: dict[str, str],
) -> dict[str, str]:
    """Return a per-test overlay mapping local names to canonical probe prefixes.

    Scoped to the single test function passed as *scope_node* so an alias bound
    in one test never resolves a same-named access in a sibling test. Two
    binding forms are tracked, both scoped to this function only:

    - Function-local imports — ``import os as o``, ``from os import environ``,
      ``from pathlib import Path`` — resolved through the same probe-relevant
      filtering ``_build_alias_canonicalization_map`` applies to module-level
      imports. Because the shared module map omits function-local imports, this
      overlay is the only place a probe import inside one test takes effect, and
      it stays confined to that test's body.
    - Rebindings of a probe module, class, or callable to a local name —
      ``path_class = Path``, ``read_env = os.getenv``, ``temp_module = tempfile``,
      ``path_module = os.path``, ``e = os.environ`` — by resolving each
      right-hand side through *all_canonical_names_by_alias* and keeping only
      those whose canonical prefix is probe-aliasable
      (``ALL_PROBE_ALIASABLE_CANONICAL_PREFIXES``).

    Merged over the module-level alias map, the overlay lets a later
    ``path_class.home()`` / ``read_env('HOME')`` / ``temp_module.mkdtemp()``
    resolve to its canonical probe chain.

    Args:
        scope_node: The single test function node to scan for alias bindings.
        all_canonical_names_by_alias: Module-level import-alias map from
            ``_build_alias_canonicalization_map``.

    Returns:
        Mapping from local binding name to its canonical probe prefix.
    """
    local_alias_canonical_names: dict[str, str] = {}
    for each_node in _descend_within_test_scope(scope_node):
        if isinstance(each_node, (ast.Import, ast.ImportFrom)):
            _record_probe_import_aliases(each_node, local_alias_canonical_names)
            continue
        if not isinstance(each_node, ast.Assign):
            continue
        canonical_prefix = _canonical_probe_prefix_for_value(
            each_node.value, all_canonical_names_by_alias
        )
        if canonical_prefix is None:
            continue
        for each_target in each_node.targets:
            if isinstance(each_target, ast.Name):
                local_alias_canonical_names[each_target.id] = canonical_prefix
    return local_alias_canonical_names


def _canonical_probe_prefix_for_value(
    node: ast.expr, all_canonical_names_by_alias: dict[str, str],
) -> str | None:
    if isinstance(node, ast.Name):
        candidate_prefix = all_canonical_names_by_alias.get(node.id, node.id)
    elif isinstance(node, ast.Attribute):
        attribute_chain = _dotted_attribute_chain(node)
        if attribute_chain is None:
            return None
        candidate_prefix = _resolve_chain_through_aliases(
            attribute_chain, all_canonical_names_by_alias
        )
    else:
        return None
    if candidate_prefix in ALL_PROBE_ALIASABLE_CANONICAL_PREFIXES:
        return candidate_prefix
    return None


def _pathlib_path_construction_uses_home_tilde(
    node: ast.expr, all_canonical_names_by_alias: dict[str, str],
) -> bool:
    """Return True for a ``pathlib.Path('~...')`` construction with a home tilde.

    The node is a Path construction when its callee chain resolves (directly,
    aliased, or fully qualified) to a member of
    ``ALL_PATHLIB_PATH_CONSTRUCTOR_CANONICAL_NAMES``. It uses the home tilde
    when its first argument is a literal string beginning with ``~``. A
    tilde-free or dynamic first argument expands no home directory and returns
    False, mirroring ``_expanduser_argument_references_home``.

    Args:
        node: The candidate ``Path(...)`` construction expression.
        all_canonical_names_by_alias: Import-alias map from
            ``_build_alias_canonicalization_map``.

    Returns:
        True when *node* constructs a ``pathlib.Path`` from a leading-tilde
        literal string.
    """
    if not isinstance(node, ast.Call):
        return False
    constructor_chain = _dotted_call_attribute_chain(node)
    if constructor_chain is None:
        return False
    canonical_chain = _resolve_chain_through_aliases(
        constructor_chain, all_canonical_names_by_alias
    )
    if canonical_chain not in ALL_PATHLIB_PATH_CONSTRUCTOR_CANONICAL_NAMES:
        return False
    return _expanduser_argument_references_home(node)


def _expanduser_method_call_targets_pathlib_path(
    call_node: ast.Call,
    all_canonical_names_by_alias: dict[str, str],
    all_path_local_bindings: set[str],
) -> bool:
    """Return True for a ``.expanduser()`` call on a home-tilde ``pathlib.Path``.

    ``Path.expanduser`` expands the ``~`` bound into the receiver Path, so the
    call resolves the home directory only when that receiver carries a leading
    tilde. The receiver carries a tilde when it is a ``pathlib.Path('~...')``
    construction (directly, aliased, or fully qualified) or a local variable
    previously bound to such a construction. A tilde-free or dynamic receiver
    (``Path('/tmp/x').expanduser()`` / ``Path(some_path).expanduser()``)
    expands no home directory and is not flagged, keeping the form symmetric
    with ``os.path.expanduser`` argument inspection.

    Args:
        call_node: The call whose callee attribute is ``expanduser``.
        all_canonical_names_by_alias: Import-alias map from
            ``_build_alias_canonicalization_map``.
        all_path_local_bindings: Local names bound to a home-tilde
            ``pathlib.Path`` construction from
            ``_collect_pathlib_path_local_binding_names``.

    Returns:
        True when the ``expanduser`` receiver resolves to a home-tilde
        ``pathlib.Path``.
    """
    callee = call_node.func
    if not isinstance(callee, ast.Attribute):
        return False
    if callee.attr != PATHLIB_EXPANDUSER_METHOD_NAME:
        return False
    receiver = callee.value
    if isinstance(receiver, ast.Name):
        return receiver.id in all_path_local_bindings
    return _pathlib_path_construction_uses_home_tilde(receiver, all_canonical_names_by_alias)


def _attribute_chain_resolves_to_os_environ(
    node: ast.expr, all_canonical_names_by_alias: dict[str, str],
) -> bool:
    if not isinstance(node, ast.Attribute):
        return False
    chain = _dotted_attribute_chain(node)
    if chain is None:
        return False
    canonical_chain = _resolve_chain_through_aliases(
        chain, all_canonical_names_by_alias
    )
    return canonical_chain == OS_ENVIRON_DOTTED_NAME


def _dotted_attribute_chain(attribute_node: ast.Attribute) -> str | None:
    chain_parts: list[str] = []
    walker: ast.expr = attribute_node
    while isinstance(walker, ast.Attribute):
        chain_parts.append(walker.attr)
        walker = walker.value
    if not isinstance(walker, ast.Name):
        return None
    chain_parts.append(walker.id)
    chain_parts.reverse()
    return ".".join(chain_parts)


def _resolve_chain_through_aliases(
    chain: str, all_canonical_names_by_alias: dict[str, str],
) -> str:
    """Rewrite the leading segment of *chain* through the alias map.

    Args:
        chain: A dotted callee chain such as ``"P.home"``,
            ``"op.expanduser"``, or ``"o.path.expanduser"``.
        all_canonical_names_by_alias: Local-binding-to-canonical-prefix
            mapping from ``_build_alias_canonicalization_map``.

    Returns:
        The chain with its leading segment replaced by the canonical
        (possibly multi-segment) prefix when a binding matches; otherwise
        the chain unchanged.
    """
    first_segment, separator, remainder = chain.partition(".")
    canonical_prefix = all_canonical_names_by_alias.get(first_segment)
    if canonical_prefix is None:
        return chain
    if not separator:
        return canonical_prefix
    return f"{canonical_prefix}{separator}{remainder}"


def _expandvars_argument_references_home_or_temp(call_node: ast.Call) -> bool:
    """Return True when an ``expandvars`` call expands a home/temp env var.

    Inspects the first string argument for dollar-style ``$NAME`` / ``${NAME}``
    references and Windows percent-style ``%NAME%`` references, then reports
    whether any referenced name is a home/temp env var. ``os.path.expandvars``
    expands percent syntax on Windows, so both forms reach the same home/temp
    env-var name set. A non-constant or absent argument is treated as not
    referencing a home/temp variable, mirroring the conservative env-name
    filtering applied to ``os.getenv``.

    Args:
        call_node: The ``os.path.expandvars(...)`` call node.

    Returns:
        True when at least one expanded variable name is in
        ``ALL_HOME_DIRECTORY_ENV_VAR_NAMES``.
    """
    if not call_node.args:
        return False
    first_argument = call_node.args[0]
    if not (
        isinstance(first_argument, ast.Constant)
        and isinstance(first_argument.value, str)
    ):
        return False
    dollar_style_names = ENVIRONMENT_VARIABLE_REFERENCE_PATTERN.findall(
        first_argument.value
    )
    percent_style_names = WINDOWS_PERCENT_VARIABLE_REFERENCE_PATTERN.findall(
        first_argument.value
    )
    all_referenced_names = dollar_style_names + percent_style_names
    return any(
        each_name in ALL_HOME_DIRECTORY_ENV_VAR_NAMES
        for each_name in all_referenced_names
    )


def _expanduser_argument_references_home(call_node: ast.Call) -> bool:
    """Return True when an ``expanduser`` call expands the home directory.

    ``os.path.expanduser`` only substitutes a leading ``~`` (``~`` alone or
    ``~user``); a string without a leading tilde is returned unchanged and
    never touches HOME. A non-constant or absent argument is treated as not
    referencing home, mirroring the conservative argument inspection applied
    to ``expandvars``.

    Args:
        call_node: The ``os.path.expanduser(...)`` call node.

    Returns:
        True when the first string argument begins with the home-directory
        tilde prefix.
    """
    if not call_node.args:
        return False
    first_argument = call_node.args[0]
    if not (
        isinstance(first_argument, ast.Constant)
        and isinstance(first_argument.value, str)
    ):
        return False
    return first_argument.value.startswith(HOME_DIRECTORY_TILDE_PREFIX)


def _tempfile_factory_call_is_isolated_by_dir(
    call_node: ast.Call,
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
) -> bool:
    """Return True when a tempfile factory's ``dir=`` sandboxes the allocation.

    A ``dir=`` keyword sandboxes the allocation only when its value is a
    plausibly isolated path (typically the pytest ``tmp_path`` fixture). A
    ``dir=`` value that resolves to the shared temp directory does not isolate
    the call and is treated as absent:

    - a constant ``None`` selects the default shared temp directory; and
    - a shared-temp source — ``os.getenv('TMPDIR'|'TEMP'|'TMP')`` /
      ``os.environ['TMPDIR'|...]`` / ``os.environ.get('TMPDIR'|...)``, or
      ``tempfile.gettempdir()`` / ``tempfile.gettempprefix()`` — returns the
      shared temp directory.

    Only an explicit ``dir=`` keyword counts; a ``**kwargs`` ``dir`` cannot be
    resolved statically and is treated as absent, mirroring the conservative
    argument inspection applied to ``expandvars`` and ``expanduser``.

    Args:
        call_node: The tempfile factory call node.
        all_canonical_names_by_alias: Import-alias map used to resolve aliased
            shared-temp sources passed as the ``dir=`` value.
        all_environ_local_bindings: Local names bound to ``os.environ`` within
            the test function, used to recognize aliased ``os.environ`` reads.

    Returns:
        True when an explicit ``dir=`` keyword is present and its value is not
        a recognized shared-temp source.
    """
    for each_keyword in call_node.keywords:
        if each_keyword.arg != TEMPFILE_FACTORY_ISOLATION_DIRECTORY_KEYWORD:
            continue
        return not _dir_value_resolves_to_shared_temp(
            each_keyword.value,
            all_canonical_names_by_alias,
            all_environ_local_bindings,
        )
    return False


def _dir_value_resolves_to_shared_temp(
    dir_value: ast.expr,
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
) -> bool:
    """Return True when a tempfile ``dir=`` value points at the shared temp dir.

    Args:
        dir_value: The expression supplied as the factory's ``dir=`` value.
        all_canonical_names_by_alias: Import-alias map used to resolve aliased
            ``os.getenv`` / ``os.environ`` / ``tempfile`` references.
        all_environ_local_bindings: Local names bound to ``os.environ`` within
            the test function.

    Returns:
        True when the value is a constant ``None`` or a recognized shared-temp
        source that yields the default shared temp directory.
    """
    if isinstance(dir_value, ast.Constant) and dir_value.value is None:
        return True
    if isinstance(dir_value, ast.Call):
        environ_key = _environ_key_string_from_call(
            dir_value, all_canonical_names_by_alias, all_environ_local_bindings
        )
        if environ_key in ALL_HOME_DIRECTORY_ENV_VAR_NAMES:
            return True
        raw_chain = _dotted_call_attribute_chain(dir_value)
        if raw_chain is None:
            return False
        canonical_chain = _resolve_chain_through_aliases(
            raw_chain, all_canonical_names_by_alias
        )
        return canonical_chain in ALL_SHARED_TEMP_SOURCE_PROBE_DOTTED_NAMES
    if isinstance(dir_value, ast.Subscript):
        environ_key = _environ_key_string_from_subscript(
            dir_value, all_canonical_names_by_alias, all_environ_local_bindings
        )
        return environ_key in ALL_HOME_DIRECTORY_ENV_VAR_NAMES
    return False


def _environ_key_string_from_call(
    call_node: ast.Call,
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
) -> str | None:
    if not _call_is_environment_getter(call_node, all_canonical_names_by_alias, all_environ_local_bindings):
        return None
    if not call_node.args:
        return None
    first_argument = call_node.args[0]
    if isinstance(first_argument, ast.Constant) and isinstance(first_argument.value, str):
        return first_argument.value
    return None


def _call_is_environment_getter(
    call_node: ast.Call,
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
) -> bool:
    """Return True when *call_node* reads an env var via a recognized getter.

    Recognizes the canonical ``os.getenv(...)`` / ``os.environ.get(...)``
    chains and the local-alias ``e.get(...)`` form where ``e`` is a name in
    *all_environ_local_bindings* (a binding to ``os.environ`` collected from
    the same test function).

    Args:
        call_node: The call to inspect.
        all_canonical_names_by_alias: Import-alias map from
            ``_build_alias_canonicalization_map``.
        all_environ_local_bindings: Local names bound to ``os.environ`` within
            the test function being analyzed.

    Returns:
        True when the call is an environment getter whose key argument is
        worth inspecting.
    """
    if _call_targets_local_environ_get(call_node, all_environ_local_bindings):
        return True
    raw_chain = _dotted_call_attribute_chain(call_node)
    if raw_chain is None:
        return False
    canonical_chain = _resolve_chain_through_aliases(raw_chain, all_canonical_names_by_alias)
    return canonical_chain in ALL_ENVIRONMENT_GETTER_DOTTED_NAMES


def _call_targets_local_environ_get(
    call_node: ast.Call, all_environ_local_bindings: set[str],
) -> bool:
    callee = call_node.func
    if not isinstance(callee, ast.Attribute):
        return False
    if callee.attr != ENVIRON_GET_METHOD_NAME:
        return False
    receiver = callee.value
    return isinstance(receiver, ast.Name) and receiver.id in all_environ_local_bindings


def _environ_key_string_from_subscript(
    subscript_node: ast.Subscript,
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
) -> str | None:
    if not _subscript_target_is_os_environ(
        subscript_node.value, all_canonical_names_by_alias, all_environ_local_bindings
    ):
        return None
    key_node = subscript_node.slice
    if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
        return key_node.value
    return None


def _subscript_target_is_os_environ(
    target_node: ast.expr,
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
) -> bool:
    if isinstance(target_node, ast.Name):
        if target_node.id in all_environ_local_bindings:
            return True
        return all_canonical_names_by_alias.get(target_node.id) == OS_ENVIRON_DOTTED_NAME
    if isinstance(target_node, ast.Attribute):
        return _attribute_chain_resolves_to_os_environ(target_node, all_canonical_names_by_alias)
    return False


def _collect_pytest_collectable_test_functions(
    syntax_tree: ast.Module,
) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Enumerate the function nodes pytest would actually collect as tests.

    Walks module-level statements and the top-level methods of module-level
    classes only. Functions nested inside other functions or lambdas are
    excluded because pytest does not collect nested callables. Module-level
    classes whose name does not start with the
    ``PYTEST_TEST_CLASS_NAME_PREFIX`` (``Test``) are skipped because the
    repo's ``pytest.ini`` declares ``python_classes = Test*``; methods on
    non-``Test*`` helper classes are never collected by pytest.
    """
    collectable: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for each_module_statement in syntax_tree.body:
        if isinstance(each_module_statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                each_module_statement.name.startswith("test_")
                or each_module_statement.name.startswith("should_")
            ):
                collectable.append(each_module_statement)
        elif isinstance(each_module_statement, ast.ClassDef):
            if not each_module_statement.name.startswith(PYTEST_TEST_CLASS_NAME_PREFIX):
                continue
            for each_class_member in each_module_statement.body:
                if isinstance(each_class_member, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                    each_class_member.name.startswith("test_")
                    or each_class_member.name.startswith("should_")
                ):
                    collectable.append(each_class_member)
    return collectable


def _detect_home_or_temp_probes_in_body(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
    all_path_local_bindings: set[str],
) -> list[tuple[int, str]]:
    """Yield ``(line, probe_label)`` pairs for HOME/TMP probes in *function_node*.

    The walk descends into ``ClassDef`` nodes nested inside the test body and
    into their class-level statements. Class-level statements (class attribute
    initializers) run at class-creation time as the ``class`` statement
    executes during the test, so a probe in an initializer such as ``root =
    Path.home()`` is on the test's runtime path and is reported. A method of a
    nested class is a callable-scope boundary: Python does not run a method
    just because its class is defined, so the walk does not descend into method
    bodies. Standalone nested helper functions and lambdas defined anywhere are
    likewise scope boundaries — each runs in its own callable scope and carries
    its own isolation contract. Probes that genuinely execute on the test path
    (top-level statements and class-level initializers) are still detected.

    Args:
        function_node: The test function whose body is being scanned.
        all_canonical_names_by_alias: Local-binding-to-canonical-prefix mapping used to resolve
            aliased imports before probe membership checks.
        all_environ_local_bindings: Local names bound to ``os.environ`` (scoped
            to *function_node*) used to attribute subscript and ``.get(...)``
            reads to a HOME/TMP env probe.
        all_path_local_bindings: Local names bound to a ``pathlib.Path``
            construction (scoped to *function_node*) used to attribute a
            ``.expanduser()`` method call to a home-directory probe.

    Returns:
        A list of ``(line_number, probe_label)`` tuples for each HOME/TMP
        probe attributed to the test, in stack-pop order.
    """
    probes: list[tuple[int, str]] = []
    for each_descendant in _descend_within_test_scope(function_node):
        _record_home_or_temp_probe(
            each_descendant,
            probes,
            all_canonical_names_by_alias,
            all_environ_local_bindings,
            all_path_local_bindings,
        )
    probes.sort(key=lambda each_probe: each_probe[0])
    return probes


def _record_home_or_temp_probe(
    node: ast.AST,
    all_probes: list[tuple[int, str]],
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
    all_path_local_bindings: set[str],
) -> None:
    if isinstance(node, ast.Call):
        if _expanduser_method_call_targets_pathlib_path(
            node, all_canonical_names_by_alias, all_path_local_bindings
        ):
            all_probes.append((node.lineno, f"Path.{PATHLIB_EXPANDUSER_METHOD_NAME}()"))
            return
        raw_chain = _dotted_call_attribute_chain(node)
        if raw_chain is None:
            return
        canonical_chain = _resolve_chain_through_aliases(raw_chain, all_canonical_names_by_alias)
        if canonical_chain == EXPANDVARS_DOTTED_NAME:
            if _expandvars_argument_references_home_or_temp(node):
                all_probes.append((node.lineno, f"{canonical_chain}()"))
            return
        if canonical_chain == EXPANDUSER_DOTTED_NAME:
            if _expanduser_argument_references_home(node):
                all_probes.append((node.lineno, f"{canonical_chain}()"))
            return
        if canonical_chain in ALL_PATHLIB_STATIC_EXPANDUSER_DOTTED_NAMES:
            if _expanduser_argument_references_home(node):
                all_probes.append((node.lineno, f"{canonical_chain}()"))
            return
        if canonical_chain in ALL_FILESYSTEM_HOME_PROBE_DOTTED_NAMES:
            if (
                canonical_chain in ALL_DIR_ACCEPTING_TEMPFILE_FACTORY_DOTTED_NAMES
                and _tempfile_factory_call_is_isolated_by_dir(
                    node, all_canonical_names_by_alias, all_environ_local_bindings
                )
            ):
                return
            all_probes.append((node.lineno, f"{canonical_chain}()"))
            return
        environ_key = _environ_key_string_from_call(
            node, all_canonical_names_by_alias, all_environ_local_bindings
        )
        if environ_key in ALL_HOME_DIRECTORY_ENV_VAR_NAMES:
            all_probes.append((node.lineno, f"os env probe '{environ_key}'"))
        return
    if isinstance(node, ast.Subscript):
        environ_key = _environ_key_string_from_subscript(
            node, all_canonical_names_by_alias, all_environ_local_bindings
        )
        if environ_key in ALL_HOME_DIRECTORY_ENV_VAR_NAMES:
            all_probes.append((node.lineno, f"os.environ['{environ_key}']"))


def _children_to_descend_into(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        return []
    if isinstance(node, ast.ClassDef):
        return list(node.body)
    return list(ast.iter_child_nodes(node))


def _descend_within_test_scope(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Iterator[ast.AST]:
    """Yield every descendant of *function_node* on the test's own runtime path.

    Bounded traversal that shares ``_children_to_descend_into`` so every caller
    treats the same nodes as in scope. Nested function definitions, methods, and
    lambdas are scope boundaries — Python does not run a callable's body just
    because the callable (or its enclosing class) is defined, so a binding or
    probe inside one does not leak onto the test's runtime path. Nested
    ``ClassDef`` bodies stay in scope because their class-creation statements
    (class attribute initializers) run as the ``class`` statement executes
    during the test; descent stops at the methods declared in that class body.

    Args:
        function_node: The test function whose in-scope descendants to yield.

    Yields:
        Each descendant node within the test's bounded scope, in stack-pop
        order.
    """
    nodes_to_visit: list[ast.AST] = list(ast.iter_child_nodes(function_node))
    while nodes_to_visit:
        each_descendant = nodes_to_visit.pop()
        yield each_descendant
        nodes_to_visit.extend(_children_to_descend_into(each_descendant))


def _usefixtures_decorator_requests_isolation_fixture(decorator_node: ast.expr) -> bool:
    """Report whether a decorator is ``usefixtures`` requesting an isolation fixture.

    Recognizes ``@pytest.mark.usefixtures("monkeypatch")`` and the
    ``@mark.usefixtures("monkeypatch")`` short form: an ``ast.Call`` whose callee
    attribute chain ends in ``usefixtures`` and whose string-constant arguments
    include any name in ``ALL_PYTEST_FILESYSTEM_ISOLATION_FIXTURE_NAMES``.

    Args:
        decorator_node: A single decorator expression from a test's decorator list.

    Returns:
        True when the decorator injects an isolation fixture by name.
    """
    if not isinstance(decorator_node, ast.Call):
        return False
    if not isinstance(decorator_node.func, ast.Attribute):
        return False
    callee_chain = _dotted_attribute_chain(decorator_node.func)
    if callee_chain is None:
        return False
    if not callee_chain.endswith(PYTEST_USEFIXTURES_MARKER_NAME):
        return False
    for each_argument in decorator_node.args:
        if (
            isinstance(each_argument, ast.Constant)
            and isinstance(each_argument.value, str)
            and each_argument.value in ALL_PYTEST_FILESYSTEM_ISOLATION_FIXTURE_NAMES
        ):
            return True
    return False


def _function_uses_pytest_isolation_fixture(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    for each_argument in function_node.args.posonlyargs:
        if each_argument.arg in ALL_PYTEST_FILESYSTEM_ISOLATION_FIXTURE_NAMES:
            return True
    for each_argument in function_node.args.args:
        if each_argument.arg in ALL_PYTEST_FILESYSTEM_ISOLATION_FIXTURE_NAMES:
            return True
    for each_argument in function_node.args.kwonlyargs:
        if each_argument.arg in ALL_PYTEST_FILESYSTEM_ISOLATION_FIXTURE_NAMES:
            return True
    for each_decorator in function_node.decorator_list:
        if _usefixtures_decorator_requests_isolation_fixture(each_decorator):
            return True
    return False


def check_tests_use_isolated_filesystem_paths(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag test functions that probe HOME or TMP without pytest isolation.

    Pattern class: tests that call ``Path.home()``, ``os.path.expanduser('~')``,
    ``os.getenv('HOME'|'USERPROFILE'|'TMPDIR'|…)``, ``os.environ['HOME'|…]``, or
    ``tempfile.gettempdir()`` against the real environment leak state across
    the suite and surface as environment-coupled bugs (audit Theme M).

    Test functions whose signatures take ``monkeypatch`` are treated as
    intentionally isolated and pass — ``monkeypatch.setenv('HOME', ...)``
    can intercept every env-derived probe, and this suppression applies
    uniformly to every probe type below. ``tmp_path`` / ``tmp_path_factory``
    / ``tmpdir`` / ``tmpdir_factory`` allocate alternative sandbox paths but
    do not intercept env reads, so their presence alone does not suppress
    the check. Module-level helpers and fixtures (any function whose name
    does not start with ``test_`` or ``should_``) are out of scope — only
    pytest-collectable ``def test_*`` / ``async def test_*`` / ``def
    should_*`` module-level or class-method functions are scanned.

    Covered forms (API surface × access form):
        Probe API surfaces — ``pathlib.Path.home()``,
        ``pathlib.Path('~...').expanduser()``, ``os.path.expanduser(arg)``,
        ``os.path.expandvars(arg)``, ``os.getenv(name)``,
        ``os.environ[name]``, ``os.environ.get(name)``, and the ``tempfile``
        allocators (``gettempdir``, ``gettempdirb``, ``gettempprefix``,
        ``mkstemp``, ``mkdtemp``, ``mktemp``, ``NamedTemporaryFile``,
        ``TemporaryFile``, ``TemporaryDirectory``, ``SpooledTemporaryFile``).
        Each surface is recognized through four access forms: (1) canonical
        dotted (``os.path.expanduser``), (2) module-level ``from X import
        name`` bare use (``from os import environ; environ['HOME']``),
        (3) module-level aliased import (``import tempfile as tf;
        tf.mkdtemp()``), and (4) a function-local binding tracked per test —
        either a function-local import (``def t(): from os import environ;
        environ['HOME']``) or a local rebinding (``path_class = Path;
        path_class.home()``; ``read_env = os.getenv; read_env('HOME')``). A
        function-local binding never leaks into a sibling test, so a same-named
        bare reference in another test that lacks its own binding does not fire.
        Gating is symmetric across the two ``expanduser`` forms (flag only on a
        leading-``~`` literal) and across the env getters / subscript (flag only
        on a home/temp env-var name). Probes are reported in source-line order
        for every probe type.

    Out of scope by design (dynamically constructed call targets that no
    AST-level pattern can resolve statically): attribute access through
    ``getattr(os, 'environ')``, callable names assembled at runtime by
    string concatenation, and calls built through ``exec``/``eval``. These
    bound the detector to a fixed, documented surface rather than an
    open-ended chase.

    Args:
        content: The Python source to analyze.
        file_path: The path of the file being checked. The check only fires
            on test files.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a probe
            blocks when any line of its enclosing test function's declared span
            (signature line through last body line) is among the changed lines,
            so editing the signature to remove an isolation fixture brings an
            unchanged-body probe into scope.
        defer_scope_to_caller: When True, return every probe so the commit/push
            gate's ``split_violations_by_scope`` can scope by added line and
            report the in-scope set.

    Returns:
        A list of issue strings naming each offending probe call. When
        *defer_scope_to_caller* is True every probe is returned for the gate to
        scope; otherwise every probe in scope is returned.
    """
    if not is_test_file(file_path):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    all_module_canonical_names_by_alias = _build_alias_canonicalization_map(syntax_tree)
    all_violations_in_source_line_order: list[tuple[range, str]] = []
    for each_node in _collect_pytest_collectable_test_functions(syntax_tree):
        if _function_uses_pytest_isolation_fixture(each_node):
            continue
        all_canonical_names_by_alias = {
            **all_module_canonical_names_by_alias,
            **_collect_local_probe_alias_bindings(each_node, all_module_canonical_names_by_alias),
        }
        all_environ_local_bindings = _collect_os_environ_local_binding_names(each_node, all_canonical_names_by_alias)
        all_path_local_bindings = _collect_pathlib_path_local_binding_names(each_node, all_canonical_names_by_alias)
        line_span = _function_definition_line_span(each_node)
        enclosing_function_span = range(each_node.lineno, each_node.lineno + line_span)
        for each_line, each_probe_label in _detect_home_or_temp_probes_in_body(
            each_node, all_canonical_names_by_alias, all_environ_local_bindings, all_path_local_bindings
        ):
            message = (
                f"Line {each_line}: Test {each_node.name!r} "
                f"(defined at line {each_node.lineno}, spanning {line_span} lines) "
                f"probes {each_probe_label} - {TEST_ISOLATION_MESSAGE_SUFFIX}"
            )
            all_violations_in_source_line_order.append(
                (enclosing_function_span, message)
            )
    return _scope_violations_to_changed_lines(
        all_violations_in_source_line_order,
        all_changed_lines,
        defer_scope_to_caller,
    )


def _collect_assert_nodes_bounded(node: ast.AST) -> list[ast.Assert]:
    """Collect Assert nodes under node without crossing scope boundaries.

    Terminates descent at FunctionDef, AsyncFunctionDef, ClassDef, and Lambda
    nodes so that assertions belonging to nested scopes are not attributed to
    the enclosing function body.
    """
    scope_boundary_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
    assertions: list[ast.Assert] = []
    nodes_to_visit: list[ast.AST] = list(ast.iter_child_nodes(node))
    while nodes_to_visit:
        current = nodes_to_visit.pop()
        if isinstance(current, ast.Assert):
            assertions.append(current)
        if isinstance(current, scope_boundary_types):
            continue
        nodes_to_visit.extend(ast.iter_child_nodes(current))
    return assertions


def _collect_body_assertions(statement_nodes: list[ast.stmt]) -> list[ast.Assert]:
    """Collect Assert nodes from a function body without descending into nested scopes."""
    assertions: list[ast.Assert] = []
    for each_stmt in statement_nodes:
        if isinstance(each_stmt, ast.Assert):
            assertions.append(each_stmt)
            continue
        if isinstance(each_stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        assertions.extend(_collect_assert_nodes_bounded(each_stmt))
    return assertions


def _is_existence_only_assertion(call_node: ast.Call) -> bool:
    """Return True when a Call node is callable() or hasattr()."""
    function_reference = call_node.func
    if isinstance(function_reference, ast.Name):
        return function_reference.id in ("callable", "hasattr")
    if isinstance(function_reference, ast.Attribute):
        return function_reference.attr in ("callable", "hasattr")
    return False


def _test_body_has_only_existence_assertions(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Return True when a test function body contains only existence-check assertions."""
    assertion_nodes = _collect_body_assertions(function_node.body)
    if not assertion_nodes:
        return False

    non_existence_assertions = 0
    for each_assert in assertion_nodes:
        test_expr = each_assert.test
        if isinstance(test_expr, ast.Call) and _is_existence_only_assertion(test_expr):
            continue
        if isinstance(test_expr, ast.Compare):
            comparators = test_expr.comparators
            ops = test_expr.ops
            if (
                len(ops) == 1
                and isinstance(ops[0], ast.IsNot)
                and len(comparators) == 1
                and isinstance(comparators[0], ast.Constant)
                and comparators[0].value is None
            ):
                continue
        non_existence_assertions += 1

    return non_existence_assertions == 0


def check_existence_check_tests(content: str, file_path: str) -> list[str]:
    """Flag test functions containing only existence-check assertions.

    Tests asserting only callable(x), hasattr(m, 'name'), or x is not None
    verify nothing about behavior. They should be deleted or replaced with
    assertions that exercise actual functionality.
    Only applies to test files.
    """
    if not is_test_file(file_path):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not each_node.name.startswith("test"):
            continue
        if _test_body_has_only_existence_assertions(each_node):
            issues.append(
                f"Line {each_node.lineno}: existence-check test"
                f" — delete or replace with a behavior test"
            )

    return issues


def _is_upper_snake_name(name: str) -> bool:
    """Return True when an identifier is written in UPPER_SNAKE_CASE."""
    return bool(UPPER_SNAKE_CONSTANT_PATTERN.match(name))


def _assert_is_constant_equality_only(assert_node: ast.Assert) -> bool:
    """Return True when the assertion compares an UPPER_SNAKE name to a literal."""
    test_expr = assert_node.test
    if not isinstance(test_expr, ast.Compare):
        return False
    if len(test_expr.ops) != 1 or not isinstance(test_expr.ops[0], ast.Eq):
        return False
    left = test_expr.left
    right = test_expr.comparators[0]
    is_left_upper_snake = isinstance(left, ast.Name) and _is_upper_snake_name(left.id)
    is_right_upper_snake = isinstance(right, ast.Name) and _is_upper_snake_name(right.id)
    if is_left_upper_snake and is_right_upper_snake:
        return False
    is_left_a_literal = isinstance(left, ast.Constant)
    is_right_a_literal = isinstance(right, ast.Constant)
    return (
        (is_left_upper_snake and is_right_a_literal)
        or (is_right_upper_snake and is_left_a_literal)
    )


def check_constant_equality_tests(content: str, file_path: str) -> list[str]:
    """Flag test functions whose sole assertion compares a constant to a literal.

    Tests like 'assert CACHE_DIR == "cache"' cover no behavior — they just
    verify the constant has not changed. Such tests should be deleted.
    Only applies to test files; production files are exempt.
    """
    if not is_test_file(file_path):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not each_node.name.startswith("test"):
            continue
        all_assertions = _collect_body_assertions(each_node.body)
        if not all_assertions:
            continue
        if len(all_assertions) > 1:
            continue
        if _assert_is_constant_equality_only(all_assertions[0]):
            issues.append(
                f"Line {each_node.lineno}: constant-value test"
                f" — delete; tests must cover behavior"
            )

    return issues


def _is_upper_snake_constant_name(name: str) -> bool:
    """Return True for UPPER_SNAKE identifiers including those with a leading underscore."""
    return bool(FILE_GLOBAL_UPPER_SNAKE_PATTERN.match(name))


def _collect_module_level_upper_snake_constants(
    module_tree: ast.Module,
) -> dict[str, int]:
    """Return mapping of module-level UPPER_SNAKE constant name to its line number."""
    constants_by_name: dict[str, int] = {}
    for each_node in module_tree.body:
        if isinstance(each_node, ast.Assign):
            for each_target in each_node.targets:
                if isinstance(each_target, ast.Name) and _is_upper_snake_constant_name(each_target.id):
                    constants_by_name.setdefault(each_target.id, each_node.lineno)
        elif isinstance(each_node, ast.AnnAssign):
            if isinstance(each_node.target, ast.Name) and _is_upper_snake_constant_name(each_node.target.id):
                constants_by_name.setdefault(each_node.target.id, each_node.lineno)
    return constants_by_name


def _build_parent_map(module_tree: ast.Module) -> dict[int, ast.AST]:
    """Map child node id() to its parent node for ancestor walking."""
    parent_by_child_id: dict[int, ast.AST] = {}
    for each_parent in ast.walk(module_tree):
        for each_child in ast.iter_child_nodes(each_parent):
            parent_by_child_id[id(each_child)] = each_parent
    return parent_by_child_id


def _resolve_enclosing_function_qname(
    load_node: ast.Name,
    parent_by_child_id: dict[int, ast.AST],
) -> Optional[str]:
    """Return 'ClassName.function_name' or 'function_name' for the enclosing function.

    Returns None when the reference is at module scope (no enclosing function).
    Decorator expressions on a function/method count as belonging to that function.
    """
    enclosing_function_name: Optional[str] = None
    enclosing_class_name: Optional[str] = None
    current_ancestor = parent_by_child_id.get(id(load_node))
    while current_ancestor is not None:
        if isinstance(current_ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)) and enclosing_function_name is None:
            enclosing_function_name = current_ancestor.name
        elif isinstance(current_ancestor, ast.ClassDef):
            enclosing_class_name = current_ancestor.name
            break
        current_ancestor = parent_by_child_id.get(id(current_ancestor))
    if enclosing_function_name is None:
        if enclosing_class_name is not None:
            return f"<class:{enclosing_class_name}>"
        return None
    if enclosing_class_name is not None:
        return f"{enclosing_class_name}.{enclosing_function_name}"
    return enclosing_function_name


def check_file_global_constants_use_count(content: str, file_path: str) -> list[str]:
    """Flag module-level UPPER_SNAKE constants referenced by only one function/method.

    Enforces jl-cmd/claude-code-config#180: a file-global constant used by just
    one caller belongs in that caller's scope. Test files, config files, and
    non-Python files are exempt. Constants with zero references are out of
    scope. Hook infrastructure files define module-level scalar constants by
    convention and are exempt to avoid self-blocking.
    """
    if is_test_file(file_path):
        return []
    if is_config_file(file_path):
        return []
    if get_file_extension(file_path) not in ALL_PYTHON_EXTENSIONS:
        return []
    if file_path.replace("\\", "/").endswith("hooks/blocking/code_rules_enforcer.py"):
        return []

    try:
        module_tree = ast.parse(content)
    except SyntaxError:
        return []

    constants_by_name = _collect_module_level_upper_snake_constants(module_tree)
    if not constants_by_name:
        return []

    parent_by_child_id = _build_parent_map(module_tree)
    callers_by_constant: dict[str, set[str]] = {name: set() for name in constants_by_name}
    for each_node in ast.walk(module_tree):
        if not isinstance(each_node, ast.Name):
            continue
        if not isinstance(each_node.ctx, ast.Load):
            continue
        if each_node.id not in callers_by_constant:
            continue
        enclosing_qname = _resolve_enclosing_function_qname(each_node, parent_by_child_id)
        if enclosing_qname is None:
            callers_by_constant[each_node.id].add("<module-scope>")
        else:
            callers_by_constant[each_node.id].add(enclosing_qname)

    issues: list[str] = []
    for each_constant_name, line_number in sorted(constants_by_name.items(), key=lambda pair: pair[1]):
        caller_count = len(callers_by_constant[each_constant_name])
        if caller_count == 1:
            issues.append(
                f"Line {line_number}: File-global constant {each_constant_name} used by only 1 function/method - move to method scope or add a second caller"
            )

    return issues


def _collect_optional_param_defaults(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, ast.expr]:
    """Return mapping of param name to its default AST node for params with defaults."""
    arguments = function_node.args
    all_args = arguments.posonlyargs + arguments.args
    defaults_aligned = [None] * (len(all_args) - len(arguments.defaults)) + list(arguments.defaults)
    param_defaults: dict[str, ast.expr] = {}
    for each_arg, each_default in zip(all_args, defaults_aligned):
        if each_default is not None:
            param_defaults[each_arg.arg] = each_default
    for each_kwarg, each_kwdefault in zip(arguments.kwonlyargs, arguments.kw_defaults):
        if each_kwdefault is not None:
            param_defaults[each_kwarg.arg] = each_kwdefault
    return param_defaults


_NON_LITERAL_DEFAULT_SENTINEL = object()


def _is_non_literal_default(candidate_default: object) -> bool:
    """Return True when a value is the sentinel for a non-literal default."""
    return candidate_default is _NON_LITERAL_DEFAULT_SENTINEL


def _ast_constant_value(node: ast.expr) -> object:
    """Return the Python value of a Constant node, or a stable sentinel for non-constants.

    Non-literal defaults (e.g. DEFAULT_TIMEOUT) return a single shared sentinel
    so that the unused-optional check can identify and skip them rather than
    treating every non-literal as automatically different.
    """
    if isinstance(node, ast.Constant):
        return node.value
    return _NON_LITERAL_DEFAULT_SENTINEL


def _call_passes_keyword_argument_differing_from_default(
    call_node: ast.Call,
    param_name: str,
    default_value: object,
) -> bool:
    """Return True when a Call passes param_name with a value different from default.

    Returns True conservatively when **kwargs expansion is present, because the
    expansion may pass the parameter with an unknown value — treating it as
    indeterminate prevents false positives from the unused-optional check.
    """
    for each_keyword in call_node.keywords:
        if each_keyword.arg is None:
            return True
        if each_keyword.arg == param_name:
            passed_value = _ast_constant_value(each_keyword.value)
            return passed_value != default_value
    return False


def _call_has_kwargs_expansion(call_node: ast.Call) -> bool:
    """Return True when a Call contains a **kwargs expansion (arg=None in AST keywords)."""
    return any(each_keyword.arg is None for each_keyword in call_node.keywords)


def _call_has_starargs_expansion(call_node: ast.Call) -> bool:
    """Return True when a Call contains a *args expansion (Starred node in positional args)."""
    return any(isinstance(each_arg, ast.Starred) for each_arg in call_node.args)


def _call_passes_positional_argument_for_param(
    call_node: ast.Call,
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    param_name: str,
    default_value: object,
) -> bool:
    """Return True when a Call passes param_name positionally with a varied value.

    Returns False when **kwargs expansion is present (the keyword helper covers
    that case). Returns True conservatively when *args expansion is present,
    because the expanded iterable may provide the parameter at runtime.
    """
    if _call_has_kwargs_expansion(call_node):
        return False
    if _call_has_starargs_expansion(call_node):
        return True
    all_args = function_node.args.posonlyargs + function_node.args.args
    try:
        param_index = next(
            each_index
            for each_index, each_arg in enumerate(all_args)
            if each_arg.arg == param_name
        )
    except StopIteration:
        return False
    if param_index >= len(call_node.args):
        return False
    passed_value = _ast_constant_value(call_node.args[param_index])
    return passed_value != default_value


def _function_name_from_call(call_node: ast.Call) -> str | None:
    """Return the function name for direct calls only, or None.

    Only direct calls (ast.Name) are matched as same-file call sites.
    Attribute calls like obj.foo() are not counted because the receiver
    object may not be the same file's definition — returning the attr name
    would cause false positives against any local function sharing that name.
    """
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id
    return None


def _collect_mock_dict_keys(assign_value: ast.expr) -> set[str] | None:
    """Return the string key set for a dict literal, or None if not a dict literal."""
    if not isinstance(assign_value, ast.Dict):
        return None
    key_names: set[str] = set()
    for each_key in assign_value.keys:
        if isinstance(each_key, ast.Constant) and isinstance(each_key.value, str):
            key_names.add(each_key.value)
    return key_names


def _target_binds_name(target_node: ast.AST, variable_name: str) -> bool:
    """Return True when an assignment target binds variable_name.

    Handles the recursive assignment target shapes Python permits:
    a bare ``Name``, a ``Tuple`` or ``List`` of targets (including
    nested ones), and a ``Starred`` wrapper around any of the above.
    """
    if isinstance(target_node, ast.Name):
        return target_node.id == variable_name
    if isinstance(target_node, (ast.Tuple, ast.List)):
        return any(_target_binds_name(each_element, variable_name) for each_element in target_node.elts)
    if isinstance(target_node, ast.Starred):
        return _target_binds_name(target_node.value, variable_name)
    return False


def _function_arguments_bind_name(
    arguments_node: ast.arguments,
    variable_name: str,
) -> bool:
    """Return True when any parameter slot declares variable_name."""
    all_positional_arguments = list(arguments_node.posonlyargs) + list(arguments_node.args)
    for each_argument in all_positional_arguments + list(arguments_node.kwonlyargs):
        if each_argument.arg == variable_name:
            return True
    if arguments_node.vararg is not None and arguments_node.vararg.arg == variable_name:
        return True
    if arguments_node.kwarg is not None and arguments_node.kwarg.arg == variable_name:
        return True
    return False


def _node_binds_name(node: ast.AST, variable_name: str) -> bool:
    """Return True when a single AST node binds variable_name in its enclosing scope."""
    if isinstance(node, ast.Assign):
        return any(_target_binds_name(each_target, variable_name) for each_target in node.targets)
    if isinstance(node, ast.AnnAssign):
        return _target_binds_name(node.target, variable_name)
    if isinstance(node, ast.AugAssign):
        return _target_binds_name(node.target, variable_name)
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return _target_binds_name(node.target, variable_name)
    if isinstance(node, (ast.With, ast.AsyncWith)):
        for each_item in node.items:
            optional_target = each_item.optional_vars
            if optional_target is not None and _target_binds_name(optional_target, variable_name):
                return True
        return False
    if isinstance(node, ast.ExceptHandler):
        return node.name == variable_name
    if isinstance(node, ast.NamedExpr):
        return _target_binds_name(node.target, variable_name)
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        for each_alias in node.names:
            bound_name = each_alias.asname if each_alias.asname is not None else each_alias.name.split(".")[0]
            if bound_name == variable_name:
                return True
        return False
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return node.name == variable_name
    return False


def _body_binds_name_recursively(body_statements: list[ast.stmt], variable_name: str) -> bool:
    """Return True when any node reachable within body_statements binds variable_name.

    Walks the body using a stack, descending into control-flow constructs
    (if/for/while/try/with) but treating nested function, async-function,
    class, and lambda definitions as opaque: their bodies belong to a
    different scope and do not affect bindings in the enclosing one.
    Function/class definitions themselves still bind their own name in
    the enclosing scope, which is handled by _node_binds_name.
    """
    nodes_to_visit: list[ast.AST] = list(body_statements)
    while nodes_to_visit:
        current_node = nodes_to_visit.pop()
        if _node_binds_name(current_node, variable_name):
            return True
        if isinstance(current_node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
            continue
        nodes_to_visit.extend(ast.iter_child_nodes(current_node))
    return False


def _scope_shadows_name(
    scope_node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
    variable_name: str,
) -> bool:
    """Return True when scope_node locally binds variable_name.

    Detects every binding form Python treats as a local assignment:
    plain ``Assign``, annotated ``AnnAssign``, augmented ``AugAssign``,
    ``for`` targets, ``with`` as-targets, ``except`` handler names,
    walrus ``NamedExpr`` targets, ``import`` and ``from`` bindings
    (base name or ``as`` alias), nested function/class definitions
    (whose own name binds locally), and function parameters for
    ``FunctionDef`` / ``AsyncFunctionDef`` scopes. Bindings are
    detected at any nesting depth inside control-flow constructs;
    nested function, async-function, class, and lambda bodies are
    treated as opaque because their contents live in a different scope.
    """
    if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if _function_arguments_bind_name(scope_node.args, variable_name):
            return True
    return _body_binds_name_recursively(list(scope_node.body), variable_name)


def _walk_scope_skipping_shadowed(
    scope_node: ast.AST,
    variable_name: str,
) -> list[ast.AST]:
    """Walk all nodes in a scope, skipping nested function/class bodies that shadow variable_name."""
    collected: list[ast.AST] = []
    nodes_to_visit: list[ast.AST] = [scope_node]
    while nodes_to_visit:
        current = nodes_to_visit.pop()
        collected.append(current)
        for each_child in ast.iter_child_nodes(current):
            if (
                isinstance(each_child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and each_child is not scope_node
                and _scope_shadows_name(each_child, variable_name)
            ):
                continue
            nodes_to_visit.append(each_child)
    return collected


def _collect_mock_field_accesses_in_scope(
    scope_node: ast.AST,
    mock_name: str,
) -> list[tuple[str, int]]:
    """Return (field_name, line_number) for attribute or subscript accesses on mock_name within a scope.

    Skips nested function/class bodies that locally redefine the same mock
    variable to avoid false positives from name shadowing.
    """
    accesses: list[tuple[str, int]] = []
    for each_node in _walk_scope_skipping_shadowed(scope_node, mock_name):
        if isinstance(each_node, ast.Attribute):
            if isinstance(each_node.value, ast.Name) and each_node.value.id == mock_name:
                if isinstance(each_node.ctx, ast.Load):
                    if each_node.attr in ALL_BUILTIN_DICT_METHOD_NAMES:
                        continue
                    accesses.append((each_node.attr, each_node.lineno))
        elif isinstance(each_node, ast.Subscript):
            if isinstance(each_node.value, ast.Name) and each_node.value.id == mock_name:
                if isinstance(each_node.ctx, ast.Load):
                    slice_node = each_node.slice
                    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
                        accesses.append((slice_node.value, each_node.lineno))
    return accesses


def _collect_mock_attribute_assignments_in_scope(
    scope_node: ast.AST,
    mock_name: str,
) -> set[str]:
    """Return field names assigned on a mock variable within a scope.

    Collects both attribute assignments (mock_x.field = ...) and subscript
    assignments with constant string keys (mock_x['field'] = ...).

    Skips nested function/class bodies that locally redefine the same mock
    variable, mirroring _collect_mock_field_accesses_in_scope so an outer
    mock's known-fields set cannot absorb assignments made on a shadowed
    inner mock of the same name.
    """
    assigned_fields: set[str] = set()
    for each_node in _walk_scope_skipping_shadowed(scope_node, mock_name):
        if not isinstance(each_node, ast.Assign):
            continue
        for each_target in each_node.targets:
            if (
                isinstance(each_target, ast.Attribute)
                and isinstance(each_target.value, ast.Name)
                and each_target.value.id == mock_name
            ):
                assigned_fields.add(each_target.attr)
            elif (
                isinstance(each_target, ast.Subscript)
                and isinstance(each_target.value, ast.Name)
                and each_target.value.id == mock_name
                and isinstance(each_target.slice, ast.Constant)
                and isinstance(each_target.slice.value, str)
            ):
                assigned_fields.add(each_target.slice.value)
    return assigned_fields


def _collect_scoped_mock_definitions(
    module_tree: ast.Module,
) -> list[tuple[int, str, set[str], int, ast.AST]]:
    """Return (scope_id, mock_name, declared_keys, definition_line, scope_node) for each mock.

    Keyed by (scope_node id, variable_name) so the same mock name in two different
    test functions is tracked independently. Scope is the enclosing function node,
    or the module node for module-level assignments.
    """
    scope_definitions: list[tuple[int, str, set[str], int, ast.AST]] = []
    for each_scope in ast.walk(module_tree):
        if not isinstance(each_scope, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
            continue
        scope_body = each_scope.body
        for each_stmt in scope_body:
            if not isinstance(each_stmt, ast.Assign):
                continue
            for each_target in each_stmt.targets:
                if not isinstance(each_target, ast.Name):
                    continue
                target_name = each_target.id
                if not (target_name.startswith("mock_") or target_name.startswith("MOCK_")):
                    continue
                mock_keys = _collect_mock_dict_keys(each_stmt.value)
                if mock_keys is not None:
                    scope_definitions.append(
                        (id(each_scope), target_name, mock_keys, each_stmt.lineno, each_scope)
                    )
                elif isinstance(each_stmt.value, ast.Call):
                    scope_definitions.append(
                        (id(each_scope), target_name, set(), each_stmt.lineno, each_scope)
                    )
    return scope_definitions


def check_incomplete_mocks(content: str, file_path: str) -> None:
    """Emit stderr advisories when a mock dict/object is missing fields that are accessed.

    Scans test files for variables named mock_* or MOCK_* whose value is a dict
    literal. Each mock definition is keyed by (scope_node_id, variable_name) so
    the same name in different test functions is checked independently. Advisories
    are deduplicated per (mock_name, field_name) pair within each scope.

    This is advisory-only (no return value, no blocking).
    """
    if not is_test_file(file_path):
        return

    try:
        module_tree = ast.parse(content)
    except SyntaxError:
        return

    all_scoped_definitions = _collect_scoped_mock_definitions(module_tree)

    for _scope_id, mock_name, declared_keys, definition_line, scope_node in all_scoped_definitions:
        assigned_attributes = _collect_mock_attribute_assignments_in_scope(scope_node, mock_name)
        all_known_fields = declared_keys | assigned_attributes
        field_accesses = _collect_mock_field_accesses_in_scope(scope_node, mock_name)
        already_advised: set[tuple[str, str]] = set()
        for accessed_field, access_line in field_accesses:
            if accessed_field in all_known_fields:
                continue
            advisory_key = (mock_name, accessed_field)
            if advisory_key in already_advised:
                continue
            already_advised.add(advisory_key)
            print(
                f"[CODE_RULES advisory] Line {definition_line}: mock {mock_name}"
                f" missing field {accessed_field} accessed at line {access_line}",
                file=sys.stderr,
            )


def _build_fstring_skeleton(joined_str_node: ast.JoinedStr) -> str:
    """Collapse interpolations in an f-string to a placeholder to form a pattern skeleton.

    Injects the skeleton placeholder directly via _extract_fstring_literal_parts
    instead of post-processing, so literal text in the source that happens to
    contain the default placeholder (or any other substring) is preserved
    verbatim and cannot collide with interpolation slots.
    """
    skeleton_interpolation_placeholder = "<x>"
    _display_body, shape_body = _extract_fstring_literal_parts(
        joined_str_node,
        interpolation_placeholder=skeleton_interpolation_placeholder,
    )
    return shape_body


def check_duplicated_format_patterns(content: str, file_path: str) -> None:
    """Emit stderr advisories when an f-string skeleton appears 3+ times in a production file.

    Collapses each f-string's interpolations to '<x>' placeholders, then counts
    skeleton occurrences per file. When any skeleton appears three or more times,
    it suggests the pattern belongs in a helper or model method.

    This is advisory-only (no return value, no blocking). Skips test files,
    config files, workflow registry files, migration files, and hook infrastructure.
    """
    if is_test_file(file_path):
        return
    if is_config_file(file_path):
        return
    if is_workflow_registry_file(file_path):
        return
    if is_migration_file(file_path):
        return
    if is_hook_infrastructure(file_path):
        return

    try:
        module_tree = ast.parse(content)
    except SyntaxError:
        return

    minimum_repetition_count = 3
    minimum_literal_character_count = 5

    skeleton_occurrences: dict[str, list[int]] = {}
    literal_length_by_skeleton: dict[str, int] = {}
    for each_node in ast.walk(module_tree):
        if not isinstance(each_node, ast.JoinedStr):
            continue
        skeleton = _build_fstring_skeleton(each_node)
        literal_body, _shape_body = _extract_fstring_literal_parts(each_node)
        if skeleton not in skeleton_occurrences:
            skeleton_occurrences[skeleton] = []
            literal_length_by_skeleton[skeleton] = len(literal_body)
        skeleton_occurrences[skeleton].append(each_node.lineno)

    for skeleton, line_numbers in skeleton_occurrences.items():
        if len(line_numbers) < minimum_repetition_count:
            continue
        if literal_length_by_skeleton[skeleton] < minimum_literal_character_count:
            continue
        print(
            f"[CODE_RULES advisory] f-string pattern {skeleton!r} appears"
            f" {len(line_numbers)} times — consider encapsulating in a helper or model.",
            file=sys.stderr,
        )


def check_unused_optional_parameters(content: str, file_path: str) -> list[str]:
    """Flag optional parameters never varied at same-file call sites.

    A parameter with a default value that every same-file caller either omits
    or always passes with the identical default literal is never varied and
    should be inlined or dropped per the YAGNI API surface rule.

    Skips test files, config files, workflow registry files, migration files,
    and hook infrastructure files.  Only checks functions that have at least
    one same-file call site.

    Scope limit (v1): only module-level functions are analyzed. Methods defined
    inside a ClassDef are skipped because the positional-index calculation would
    need to account for the implicit self/cls parameter, which is absent at
    call sites using attribute access (obj.method(...)). Method analysis is out
    of scope for this version.
    """
    if is_test_file(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path):
        return []
    if is_migration_file(file_path):
        return []
    if is_hook_infrastructure(file_path):
        return []

    try:
        module_tree = ast.parse(content)
    except SyntaxError:
        return []

    all_function_nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for each_node in module_tree.body:
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            all_function_nodes[each_node.name] = each_node

    all_call_nodes: list[ast.Call] = [
        each_node
        for each_node in ast.walk(module_tree)
        if isinstance(each_node, ast.Call)
    ]

    issues: list[str] = []
    for function_name, function_node in all_function_nodes.items():
        param_defaults = _collect_optional_param_defaults(function_node)
        if not param_defaults:
            continue

        same_file_calls = [
            each_call
            for each_call in all_call_nodes
            if _function_name_from_call(each_call) == function_name
        ]
        if not same_file_calls:
            continue

        for param_name, default_node in param_defaults.items():
            default_value = _ast_constant_value(default_node)
            if _is_non_literal_default(default_value):
                continue
            is_param_varied = any(
                _call_passes_keyword_argument_differing_from_default(
                    each_call, param_name, default_value
                )
                or _call_passes_positional_argument_for_param(
                    each_call, function_node, param_name, default_value
                )
                for each_call in same_file_calls
            )
            if not is_param_varied:
                issues.append(
                    f"Line {function_node.lineno}: optional parameter {param_name}"
                    f" is never varied — inline default or drop"
                )

    return issues




def _annotation_names_collection(annotation_node: ast.expr | None) -> bool:
    if annotation_node is None:
        return False
    if isinstance(annotation_node, ast.Name):
        return annotation_node.id in ALL_COLLECTION_TYPE_NAMES
    if isinstance(annotation_node, ast.Attribute):
        return annotation_node.attr in ALL_COLLECTION_TYPE_NAMES
    if isinstance(annotation_node, ast.BinOp) and isinstance(annotation_node.op, ast.BitOr):
        return (
            _annotation_names_collection(annotation_node.left)
            or _annotation_names_collection(annotation_node.right)
        )
    if isinstance(annotation_node, ast.Subscript):
        outer_value = annotation_node.value
        is_optional_or_union_subscript = (
            (isinstance(outer_value, ast.Name) and outer_value.id in ALL_UNION_TYPING_NAMES)
            or (isinstance(outer_value, ast.Attribute) and outer_value.attr in ALL_UNION_TYPING_NAMES)
        )
        if is_optional_or_union_subscript:
            slice_node = annotation_node.slice
            if isinstance(slice_node, ast.Tuple):
                return any(
                    _annotation_names_collection(each_element)
                    for each_element in slice_node.elts
                )
            return _annotation_names_collection(slice_node)
        is_subscript_only_collection_type = (
            (isinstance(outer_value, ast.Name) and outer_value.id in ALL_SUBSCRIPT_ONLY_COLLECTION_TYPE_NAMES)
            or (isinstance(outer_value, ast.Attribute) and outer_value.attr in ALL_SUBSCRIPT_ONLY_COLLECTION_TYPE_NAMES)
        )
        if is_subscript_only_collection_type:
            return True
        return _annotation_names_collection(outer_value)
    return False


def check_collection_prefix(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for node in tree.body:
        target_name: str | None = None
        target_line = 0
        is_collection_value = False
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            target_name = node.target.id
            target_line = node.lineno
            is_collection_value = _annotation_names_collection(node.annotation)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target_name = node.targets[0].id
            target_line = node.lineno
            is_collection_value = isinstance(node.value, (ast.Tuple, ast.List, ast.Set, ast.Dict))
        if target_name is None or not is_collection_value:
            continue
        if not UPPER_SNAKE_CONSTANT_PATTERN.match(target_name):
            continue
        if target_name.startswith("ALL_") or COLLECTION_BY_NAME_PATTERN.match(target_name.lower()):
            continue
        issues.append(
            f"Line {target_line}: Collection constant {target_name} - prefix with ALL_ (CODE_RULES §5)"
        )
    for each_walked_node in ast.walk(tree):
        if not isinstance(each_walked_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_arg in _collect_annotated_arguments(each_walked_node):
            if not _annotation_names_collection(each_arg.annotation):
                continue
            if each_arg.arg in {"self", "cls"}:
                continue
            if each_arg.arg.startswith("all_") or COLLECTION_BY_NAME_PATTERN.match(each_arg.arg):
                continue
            issues.append(
                f"Line {each_arg.lineno}: Collection parameter {each_arg.arg} - prefix with all_ (CODE_RULES §5)"
            )
    return issues


def _is_stuttering_all_name(name: str) -> bool:
    return bool(STUTTERING_ALL_PREFIX_PATTERN.match(name))


def _walk_assignment_targets(target: ast.expr) -> list[ast.Name]:
    """Recursively collect ast.Name targets through tuple/list/starred unpacking."""
    if isinstance(target, ast.Name):
        return [target]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[ast.Name] = []
        for each_element in target.elts:
            names.extend(_walk_assignment_targets(each_element))
        return names
    if isinstance(target, ast.Starred):
        return _walk_assignment_targets(target.value)
    return []


def _collect_stuttering_name_bindings(tree: ast.Module) -> list[tuple[str, int]]:
    """Return (name, line_number) for bindings whose introduced name stutters all_/ALL_ prefixes.

    Covers assignments, loops, parameters, walrus targets, comprehensions, with/except
    aliases, import aliases, and class definitions.
    """
    bindings: list[tuple[str, int]] = []
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.Assign):
            for each_target in each_node.targets:
                for each_name in _walk_assignment_targets(each_target):
                    if _is_stuttering_all_name(each_name.id):
                        bindings.append((each_name.id, each_name.lineno))
        elif isinstance(each_node, ast.AnnAssign) and isinstance(each_node.target, ast.Name):
            if _is_stuttering_all_name(each_node.target.id):
                bindings.append((each_node.target.id, each_node.target.lineno))
        elif isinstance(each_node, (ast.For, ast.AsyncFor)):
            for each_name in _walk_assignment_targets(each_node.target):
                if _is_stuttering_all_name(each_name.id):
                    bindings.append((each_name.id, each_name.lineno))
        elif isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_stuttering_all_name(each_node.name):
                bindings.append((each_node.name, each_node.lineno))
            for each_arg in _collect_annotated_arguments(each_node):
                if _is_stuttering_all_name(each_arg.arg):
                    bindings.append((each_arg.arg, each_arg.lineno))
        elif isinstance(each_node, ast.NamedExpr) and isinstance(each_node.target, ast.Name):
            if _is_stuttering_all_name(each_node.target.id):
                bindings.append((each_node.target.id, each_node.target.lineno))
        elif isinstance(each_node, ast.comprehension):
            for each_name in _walk_assignment_targets(each_node.target):
                if _is_stuttering_all_name(each_name.id):
                    bindings.append((each_name.id, each_name.lineno))
        elif isinstance(each_node, (ast.With, ast.AsyncWith)):
            for each_with_item in each_node.items:
                if each_with_item.optional_vars is None:
                    continue
                for each_name in _walk_assignment_targets(each_with_item.optional_vars):
                    if _is_stuttering_all_name(each_name.id):
                        bindings.append((each_name.id, each_name.lineno))
        elif isinstance(each_node, ast.ExceptHandler):
            if each_node.name is not None and _is_stuttering_all_name(each_node.name):
                bindings.append((each_node.name, each_node.lineno))
        elif isinstance(each_node, ast.Import):
            for each_alias in each_node.names:
                bound_name = (
                    each_alias.asname
                    if each_alias.asname is not None
                    else each_alias.name.split(MODULE_PATH_SEPARATOR, 1)[0]
                )
                if _is_stuttering_all_name(bound_name):
                    line_number = getattr(each_alias, AST_LINENO_ATTRIBUTE, None) or each_node.lineno
                    bindings.append((bound_name, line_number))
        elif isinstance(each_node, ast.ImportFrom):
            for each_alias in each_node.names:
                if each_alias.name == WILDCARD_IMPORT_SENTINEL:
                    continue
                bound_name = (
                    each_alias.asname
                    if each_alias.asname is not None
                    else each_alias.name
                )
                if _is_stuttering_all_name(bound_name):
                    line_number = getattr(each_alias, AST_LINENO_ATTRIBUTE, None) or each_node.lineno
                    bindings.append((bound_name, line_number))
        elif isinstance(each_node, ast.ClassDef):
            if _is_stuttering_all_name(each_node.name):
                bindings.append((each_node.name, each_node.lineno))
    return bindings


def check_stuttering_collection_prefix(content: str, file_path: str) -> list[str]:
    """Flag identifiers stuttering the all_/ALL_ collection prefix (e.g., all_all_users)."""
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_name, each_line_number in _collect_stuttering_name_bindings(tree):
        issues.append(
            f"Line {each_line_number}: Stuttering collection prefix {each_name!r}"
            f" - use a single all_/ALL_ prefix (CODE_RULES §5)"
        )
        if len(issues) >= MAX_STUTTERING_PREFIX_ISSUES:
            break
    return issues


def check_hardcoded_user_paths(content: str, file_path: str) -> list[str]:
    """Flag string literals naming a specific user's home directory.

    Catches non-portable paths like `C:/Users/jon/...`, `/Users/alice/...`,
    and `/home/bob/...` that surface in production code (PR #257 evidence).
    Test files, config/ files, workflow registry files, migration files,
    and hook infrastructure files are exempt. Hook infrastructure exemption
    matches the pattern used by check_library_print and other check
    functions, and prevents the enforcer from self-blocking on its own
    HARDCODED_USER_PATH_PATTERN definition.
    """
    if is_test_file(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    if is_hook_infrastructure(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    docstring_node_ids = _collect_docstring_node_ids(tree)
    issues: list[str] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Constant):
            continue
        if not isinstance(each_node.value, str):
            continue
        if id(each_node) in docstring_node_ids:
            continue
        match = HARDCODED_USER_PATH_PATTERN.search(each_node.value)
        if match is None:
            continue
        issues.append(
            f"Line {each_node.lineno}: hardcoded user path {match.group(0)!r}"
            f" — {HARDCODED_USER_PATH_GUIDANCE}"
        )
        if len(issues) >= MAX_HARDCODED_USER_PATH_ISSUES:
            break
    return issues


def _is_sys_path_insert_call(call_node: ast.Call) -> bool:
    function_reference = call_node.func
    if not isinstance(function_reference, ast.Attribute) or function_reference.attr != "insert":
        return False
    receiver = function_reference.value
    if not isinstance(receiver, ast.Attribute) or receiver.attr != "path":
        return False
    receiver_value = receiver.value
    return isinstance(receiver_value, ast.Name) and receiver_value.id == "sys"


def _is_sys_path_membership_if_test(if_test_expression: ast.AST) -> bool:
    """Return True when `if X not in sys.path:` would guard a then-branch insert.

    Only `ast.NotIn` is accepted: `_scope_has_guard_for_insert` walks the
    then-branch (`each_statement.body`) for the insert, so accepting `ast.In`
    here would silently approve `if X in sys.path: sys.path.insert(0, X)` —
    code that always inserts a duplicate. The else-branch is intentionally not
    inspected; a guard that places the insert in the else-branch of `if X in
    sys.path:` is unconventional and not supported.
    """
    if not isinstance(if_test_expression, ast.Compare):
        return False
    if len(if_test_expression.ops) != 1:
        return False
    if not isinstance(if_test_expression.ops[0], ast.NotIn):
        return False
    membership_target = if_test_expression.comparators[0]
    if not isinstance(membership_target, ast.Attribute) or membership_target.attr != "path":
        return False
    membership_receiver = membership_target.value
    return isinstance(membership_receiver, ast.Name) and membership_receiver.id == "sys"


def _scope_has_guard_for_insert(
    all_scope_statements: list[ast.stmt],
    insert_call_node: ast.Call,
) -> bool:
    for each_statement in all_scope_statements:
        if not isinstance(each_statement, ast.If):
            continue
        membership_test = each_statement.test
        if not isinstance(membership_test, ast.Compare):
            continue
        if not _is_sys_path_membership_if_test(membership_test):
            continue
        for each_inner in each_statement.body:
            if isinstance(each_inner, ast.Expr) and each_inner.value is insert_call_node:
                if len(insert_call_node.args) < 2:
                    return True
                if ast.dump(membership_test.left) == ast.dump(insert_call_node.args[1]):
                    return True
    return False


def _enclosing_scope_body(
    insert_call_node: ast.Call,
    parent_by_node_id: dict[int, ast.AST],
) -> list[ast.stmt]:
    parent = parent_by_node_id.get(id(insert_call_node))
    while parent is not None:
        if isinstance(parent, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            return list(parent.body)
        parent = parent_by_node_id.get(id(parent))
    return []


def check_sys_path_insert_deduplication_guard(content: str, file_path: str) -> list[str]:
    """Flag sys.path.insert calls that lack a `not in sys.path` guard.

    Repeated module reloads can push the same entry onto sys.path multiple
    times when the call is unguarded. The repo convention is to wrap the
    call with `if <path> not in sys.path:`. PR #289 surfaced two scripts
    (grant_project_claude_permissions.py, revoke_project_claude_permissions.py)
    that bypassed the convention.
    """
    if is_test_file(file_path):
        return []
    if is_hook_infrastructure(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    parent_by_node_id = _build_parent_map(tree)
    issues: list[str] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Call):
            continue
        if not _is_sys_path_insert_call(each_node):
            continue
        all_scope_statements = _enclosing_scope_body(each_node, parent_by_node_id)
        if _scope_has_guard_for_insert(all_scope_statements, each_node):
            continue
        issues.append(
            f"Line {each_node.lineno}: unguarded sys.path.insert"
            f" — {SYS_PATH_INSERT_GUIDANCE}"
        )
        if len(issues) >= MAX_SYS_PATH_INSERT_ISSUES:
            break
    return issues


def _import_alias_pairs(
    import_node: ast.Import | ast.ImportFrom,
) -> list[tuple[str, int, int | None]]:
    """Return (binding_name, alias_line, from_keyword_line) for each name introduced.

    The from-keyword line is None for plain `import X` statements; for
    `from X import (...)` it carries the line of the `from` keyword so
    callers can honor a `# noqa` placed on the opening line of a
    multi-line import block.
    """
    bindings: list[tuple[str, int, int | None]] = []
    from_keyword_line = import_node.lineno if isinstance(import_node, ast.ImportFrom) else None
    for each_alias in import_node.names:
        if each_alias.name == "*":
            continue
        binding_name = each_alias.asname if each_alias.asname else each_alias.name.split(".")[0]
        alias_line = each_alias.lineno or import_node.lineno
        bindings.append((binding_name, alias_line, from_keyword_line))
    return bindings


def _import_statement_line_ranges(tree: ast.Module) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for each_node in tree.body:
        if isinstance(each_node, (ast.Import, ast.ImportFrom)):
            start_line = each_node.lineno
            end_line = each_node.end_lineno or each_node.lineno
            ranges.append((start_line, end_line))
    return ranges


def _line_number_falls_in_import_ranges(
    line_number: int,
    all_import_line_ranges: list[tuple[int, int]],
) -> bool:
    for each_start, each_end in all_import_line_ranges:
        if each_start <= line_number <= each_end:
            return True
    return False


def _type_checking_guard_aliases(tree: ast.Module) -> tuple[set[str], set[str]]:
    all_type_checking_names = {TYPE_CHECKING_IDENTIFIER}
    all_type_checking_module_aliases = set(ALL_TYPING_MODULE_NAMES)
    for each_statement in tree.body:
        if isinstance(each_statement, ast.Import):
            for each_alias in each_statement.names:
                if each_alias.name in ALL_TYPING_MODULE_NAMES:
                    all_type_checking_module_aliases.add(
                        each_alias.asname or each_alias.name
                    )
        elif isinstance(each_statement, ast.ImportFrom):
            if each_statement.module not in ALL_TYPING_MODULE_NAMES:
                continue
            for each_alias in each_statement.names:
                if each_alias.name == TYPE_CHECKING_IDENTIFIER:
                    all_type_checking_names.add(each_alias.asname or each_alias.name)
    return all_type_checking_names, all_type_checking_module_aliases


def _expression_guards_type_checking_block(
    test_expression: ast.expr,
    all_type_checking_names: set[str],
    all_type_checking_module_aliases: set[str],
) -> bool:
    if isinstance(test_expression, ast.Name):
        return test_expression.id in all_type_checking_names
    if isinstance(test_expression, ast.Attribute):
        if test_expression.attr != TYPE_CHECKING_IDENTIFIER:
            return False
        receiver = test_expression.value
        return (
            isinstance(receiver, ast.Name)
            and receiver.id in all_type_checking_module_aliases
        )
    return False


def _module_body_declares_type_checking_gate(tree: ast.Module) -> bool:
    (
        all_type_checking_names,
        all_type_checking_module_aliases,
    ) = _type_checking_guard_aliases(tree)
    return any(
        isinstance(each_statement, ast.If)
        and _expression_guards_type_checking_block(
            each_statement.test,
            all_type_checking_names,
            all_type_checking_module_aliases,
        )
        for each_statement in tree.body
    )


def _attribute_root_name_if_loaded(attribute_node: ast.Attribute) -> ast.Name | None:
    current: ast.expr = attribute_node
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name) and isinstance(current.ctx, ast.Load):
        return current
    return None


class _ScopeBindingCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.binding_names: set[str] = set()
        self.global_names: set[str] = set()

    def collect_arguments(self, arguments: ast.arguments) -> None:
        for each_argument in (
            arguments.posonlyargs
            + arguments.args
            + arguments.kwonlyargs
        ):
            self.binding_names.add(each_argument.arg)
        if arguments.vararg is not None:
            self.binding_names.add(arguments.vararg.arg)
        if arguments.kwarg is not None:
            self.binding_names.add(arguments.kwarg.arg)

    def visit_Global(self, node: ast.Global) -> None:
        self.global_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.binding_names.update(node.names)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.binding_names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.binding_names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.binding_names.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return None

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.binding_names.add(node.id)

    def visit_Import(self, node: ast.Import) -> None:
        for each_alias in node.names:
            self.binding_names.add(each_alias.asname or each_alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for each_alias in node.names:
            if each_alias.name != WILDCARD_IMPORT_SENTINEL:
                self.binding_names.add(each_alias.asname or each_alias.name)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        return None

    def visit_SetComp(self, node: ast.SetComp) -> None:
        return None

    def visit_DictComp(self, node: ast.DictComp) -> None:
        return None

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        return None

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            self.binding_names.add(node.name)
        self.generic_visit(node)


def _scope_binding_names(scope_node: ast.AST) -> tuple[set[str], set[str]]:
    collector = _ScopeBindingCollector()
    if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        collector.collect_arguments(scope_node.args)
        for each_statement in scope_node.body:
            collector.visit(each_statement)
    elif isinstance(scope_node, ast.Lambda):
        collector.collect_arguments(scope_node.args)
        collector.visit(scope_node.body)
    elif isinstance(scope_node, ast.ClassDef):
        for each_statement in scope_node.body:
            collector.visit(each_statement)
    return collector.binding_names, collector.global_names


def _load_name_is_shadowed(
    load_node: ast.AST,
    name: str,
    parent_by_node_id: dict[int, ast.AST],
) -> bool:
    current = parent_by_node_id.get(id(load_node))
    has_passed_function_scope = False
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            has_passed_function_scope = True
            binding_names, global_names = _scope_binding_names(current)
            if name in global_names:
                return False
            if name in binding_names:
                return True
        elif isinstance(current, ast.ClassDef) and not has_passed_function_scope:
            # Class body bindings are order-dependent (name resolution is
            # dynamic, unlike function locals). A load before an assignment
            # still resolves to the module-level name, so conservatively
            # skip class-body shadow detection to avoid false positives.
            pass
        current = parent_by_node_id.get(id(current))
    return False


def _names_from_annotation_text(annotation_text: str) -> set[str]:
    try:
        annotation_tree = ast.parse(annotation_text, mode="eval")
    except SyntaxError:
        return set()
    referenced_names: set[str] = set()
    for each_node in ast.walk(annotation_tree):
        if isinstance(each_node, ast.Name):
            referenced_names.add(each_node.id)
        elif isinstance(each_node, ast.Attribute):
            root_name = _attribute_root_name_if_loaded(each_node)
            if root_name is not None:
                referenced_names.add(root_name.id)
    return referenced_names


def _collect_string_annotation_names(tree: ast.Module) -> set[str]:
    referenced_names: set[str] = set()
    for each_node in ast.walk(tree):
        annotation = None
        if isinstance(each_node, ast.arg):
            annotation = each_node.annotation
        elif isinstance(each_node, (ast.AnnAssign, ast.FunctionDef, ast.AsyncFunctionDef)):
            annotation = each_node.annotation if isinstance(each_node, ast.AnnAssign) else each_node.returns
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            referenced_names.update(_names_from_annotation_text(annotation.value))
    return referenced_names


def _collect_load_names_outside_import_ranges(
    tree: ast.Module,
    all_import_line_ranges: list[tuple[int, int]],
) -> set[str]:
    parent_by_node_id = _build_parent_map(tree)
    referenced_names: set[str] = set()
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.Name) and isinstance(each_node.ctx, ast.Load):
            line_number = each_node.lineno
            if line_number is None or _line_number_falls_in_import_ranges(
                line_number,
                all_import_line_ranges,
            ):
                continue
            if _load_name_is_shadowed(each_node, each_node.id, parent_by_node_id):
                continue
            referenced_names.add(each_node.id)
        elif isinstance(each_node, ast.Attribute) and isinstance(
            each_node.ctx, ast.Load
        ):
            line_number = each_node.lineno
            if line_number is None or _line_number_falls_in_import_ranges(
                line_number,
                all_import_line_ranges,
            ):
                continue
            root_name = _attribute_root_name_if_loaded(each_node)
            if root_name is not None and not _load_name_is_shadowed(
                root_name,
                root_name.id,
                parent_by_node_id,
            ):
                referenced_names.add(root_name.id)
    referenced_names.update(_collect_string_annotation_names(tree))
    return referenced_names


def _module_declares_dunder_all(tree: ast.Module) -> bool:
    """Return True when the module body assigns or annotates ``__all__``."""
    return any(
        (
            isinstance(each_node, ast.Assign)
            and any(
                isinstance(each_target, ast.Name) and each_target.id == "__all__"
                for each_target in each_node.targets
            )
        )
        or (
            isinstance(each_node, ast.AnnAssign)
            and isinstance(each_node.target, ast.Name)
            and each_node.target.id == "__all__"
        )
        for each_node in tree.body
    )


def check_unused_module_level_imports(
    content: str,
    file_path: str,
    full_file_content: str | None = None,
) -> list[str]:
    """Flag module-level imports that are never referenced in the rest of the file.

    References are detected from AST ``Name`` / ``Attribute`` loads outside import
    statements so mentions in comments or string literals do not count. Files
    declaring ``__all__`` (including annotated assignments) are skipped. Files
    whose module body includes ``if TYPE_CHECKING:`` (or
    ``typing[._extensions].TYPE_CHECKING``) are skipped. Suppression honors bare
    ``# noqa`` or an explicit ``F401`` code in the noqa list only.

    When ``full_file_content`` is provided, ``content`` is treated as an Edit
    fragment containing the imports being added or replaced, while the
    ``__all__`` / ``TYPE_CHECKING`` gate detection and reference scanning run
    against ``full_file_content`` (the post-edit file as it will look once the
    Edit applies). This prevents false-positive flags on imports added in the
    same Edit as their consumers.
    """
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        fragment_tree = ast.parse(content)
    except SyntaxError:
        return []
    reference_source = full_file_content if full_file_content is not None else content
    try:
        reference_tree = ast.parse(reference_source)
    except SyntaxError:
        return []
    if _module_declares_dunder_all(reference_tree):
        return []
    if _module_body_declares_type_checking_gate(reference_tree):
        return []
    fragment_lines = content.splitlines()
    reference_import_ranges = _import_statement_line_ranges(reference_tree)
    referenced_names = _collect_load_names_outside_import_ranges(
        reference_tree,
        reference_import_ranges,
    )
    import_bindings: list[tuple[str, int, int | None]] = []
    for each_node in fragment_tree.body:
        if isinstance(each_node, (ast.Import, ast.ImportFrom)):
            if isinstance(each_node, ast.ImportFrom) and each_node.module == "__future__":
                continue
            for each_binding in _import_alias_pairs(each_node):
                import_bindings.append(each_binding)
    issues: list[str] = []
    for each_name, each_line_number, each_from_keyword_line in import_bindings:
        if 1 <= each_line_number <= len(fragment_lines):
            if line_suppresses_unused_import_via_noqa(fragment_lines[each_line_number - 1]):
                continue
        if each_from_keyword_line is not None and 1 <= each_from_keyword_line <= len(
            fragment_lines
        ):
            if line_suppresses_unused_import_via_noqa(
                fragment_lines[each_from_keyword_line - 1]
            ):
                continue
        if each_name in referenced_names:
            continue
        issues.append(
            f"Line {each_line_number}: unused module-level import {each_name!r}"
            f" — {UNUSED_IMPORT_GUIDANCE}"
        )
        if len(issues) >= MAX_UNUSED_IMPORT_ISSUES:
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
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function_reference = node.func
        if isinstance(function_reference, ast.Name) and function_reference.id == "print":
            issues.append(
                f"Line {node.lineno}: Library print() - route through logger or accept an explicit stream parameter"
            )
        elif isinstance(function_reference, ast.Attribute) and function_reference.attr == "write":
            value_node = function_reference.value
            if isinstance(value_node, ast.Attribute) and isinstance(value_node.value, ast.Name):
                if value_node.value.id == "sys" and value_node.attr in {"stdout", "stderr"}:
                    issues.append(
                        f"Line {node.lineno}: sys.{value_node.attr}.write - route through logger"
                    )
    return issues




def _is_magic_string_literal(string_value: str) -> bool:
    if not string_value:
        return False
    if ALL_CAPS_WITH_UNDERSCORE_PATTERN.match(string_value):
        return True
    if DOTTED_SEGMENT_PATTERN.match(string_value):
        return True
    return False


def _collect_docstring_node_ids(tree: ast.Module) -> set[int]:
    docstring_ids: set[int] = set()
    docstring_owner_node_types = (
        ast.Module,
        ast.FunctionDef,
        ast.AsyncFunctionDef,
        ast.ClassDef,
    )
    for node in ast.walk(tree):
        if not isinstance(node, docstring_owner_node_types):
            continue
        if not node.body:
            continue
        first_statement = node.body[0]
        if not isinstance(first_statement, ast.Expr):
            continue
        first_value = first_statement.value
        if isinstance(first_value, ast.Constant) and isinstance(first_value.value, str):
            docstring_ids.add(id(first_value))
    return docstring_ids


def _collect_fstring_part_node_ids(tree: ast.Module) -> set[int]:
    fstring_part_ids: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.JoinedStr):
            continue
        for each_value in node.values:
            if isinstance(each_value, ast.Constant) and isinstance(each_value.value, str):
                fstring_part_ids.add(id(each_value))
    return fstring_part_ids


def _walk_skipping_nested_function_defs(start_node: ast.AST) -> Iterator[ast.AST]:
    if isinstance(start_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return
    nodes_to_visit: list[ast.AST] = [start_node]
    while nodes_to_visit:
        current_node = nodes_to_visit.pop()
        yield current_node
        all_child_nodes = list(ast.iter_child_nodes(current_node))
        for each_child_node in reversed(all_child_nodes):
            if isinstance(each_child_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            nodes_to_visit.append(each_child_node)


def check_string_literal_magic(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    docstring_node_ids = _collect_docstring_node_ids(tree)
    fstring_part_node_ids = _collect_fstring_part_node_ids(tree)
    issues: list[str] = []
    flagged_node_ids: set[int] = set()
    for function_node in ast.walk(tree):
        if not isinstance(function_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_body_statement in function_node.body:
            for each_descendant in _walk_skipping_nested_function_defs(each_body_statement):
                if not isinstance(each_descendant, ast.Constant):
                    continue
                if not isinstance(each_descendant.value, str):
                    continue
                if id(each_descendant) in flagged_node_ids:
                    continue
                if id(each_descendant) in docstring_node_ids:
                    continue
                if id(each_descendant) in fstring_part_node_ids:
                    continue
                if not _is_magic_string_literal(each_descendant.value):
                    continue
                flagged_node_ids.add(id(each_descendant))
                issues.append(
                    f"Line {each_descendant.lineno}: string magic value {each_descendant.value!r}"
                    f" - extract to config/"
                )
    return issues


def check_inline_literal_collections(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    flagged_node_ids: set[int] = set()
    for function_node in ast.walk(tree):
        if not isinstance(function_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_body_statement in function_node.body:
            for each_descendant in _walk_skipping_nested_function_defs(each_body_statement):
                if not isinstance(each_descendant, (ast.Set, ast.List)):
                    continue
                if id(each_descendant) in flagged_node_ids:
                    continue
                all_elements = each_descendant.elts
                if len(all_elements) < INLINE_COLLECTION_MIN_LENGTH:
                    continue
                if not all(isinstance(each_element, ast.Constant) for each_element in all_elements):
                    continue
                flagged_node_ids.add(id(each_descendant))
                collection_kind = "set" if isinstance(each_descendant, ast.Set) else "list"
                issues.append(
                    f"Line {each_descendant.lineno}: inline {collection_kind} literal of {len(all_elements)}"
                    f" constants in function body - extract to config/"
                )
    return issues


def check_inline_tuple_string_magic(content: str, file_path: str) -> list[str]:
    """Flag inline two-tuple literals whose first element is a snake_case string.

    Catches the pattern ``("kept", "Unknown status")`` and similar
    column-name/key-value pairs declared inside function bodies. Files under
    ``config/`` and test files are exempt because that is where named
    constants are expected to live.
    """
    if is_test_file(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    snake_case_pattern = re.compile(SNAKE_CASE_LITERAL_PATTERN)
    issues: list[str] = []
    seen_tuple_node_ids: set[int] = set()
    for each_function_node in ast.walk(tree):
        if not isinstance(each_function_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_body_statement in each_function_node.body:
            for each_descendant in _walk_skipping_nested_function_defs(each_body_statement):
                if not isinstance(each_descendant, ast.Tuple):
                    continue
                if id(each_descendant) in seen_tuple_node_ids:
                    continue
                seen_tuple_node_ids.add(id(each_descendant))
                if len(each_descendant.elts) != EXPECTED_TUPLE_PAIR_LENGTH:
                    continue
                first_element = each_descendant.elts[0]
                if not isinstance(first_element, ast.Constant):
                    continue
                if not isinstance(first_element.value, str):
                    continue
                literal_text = first_element.value
                if not snake_case_pattern.match(literal_text):
                    continue
                if literal_text in ALL_SNAKE_CASE_KEYWORD_EXEMPTIONS:
                    continue
                issues.append(
                    f"Line {first_element.lineno}: Column-name string magic "
                    f"{literal_text!r} - {INLINE_TUPLE_STRING_MAGIC_MESSAGE_SUFFIX}"
                )
                if len(issues) >= MAX_INLINE_TUPLE_STRING_MAGIC_ISSUES:
                    return issues
    return issues


def check_loop_variable_naming(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, (ast.For, ast.AsyncFor)):
            continue
        for each_name_node in _collect_target_names(each_node.target):
            target_name = each_name_node.id
            if target_name in ALL_LOOP_INDEX_LETTER_EXEMPTIONS:
                continue
            if target_name == BARE_EACH_TOKEN:
                issues.append(
                    f"Line {each_name_node.lineno}: loop variable 'each' is a bare token without subject"
                    f" - rename to each_<subject> (CODE_RULES §5)"
                )
                continue
            if target_name.startswith(EACH_PREFIX) and len(target_name) > len(EACH_PREFIX):
                continue
            issues.append(
                f"Line {each_name_node.lineno}: loop variable {target_name!r} - prefix with each_ (CODE_RULES §5)"
            )
    return issues


def check_parameter_annotations(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_arg in _collect_annotated_arguments(node):
            if each_arg.arg in ALL_SELF_AND_CLS_PARAMETER_NAMES:
                continue
            if each_arg.annotation is None:
                issues.append(
                    f"Line {each_arg.lineno}: parameter {each_arg.arg!r} on {node.name!r} missing type annotation (CODE_RULES §6)"
                )
    return issues


def check_return_annotations(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.returns is None:
            issues.append(
                f"Line {node.lineno}: function {node.name!r} missing return type annotation (CODE_RULES §6)"
            )
    return issues


def _function_definition_line_span(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int:
    end_lineno = getattr(function_node, "end_lineno", None) or function_node.lineno
    return end_lineno - function_node.lineno + 1


def changed_line_numbers(prior_content: str, post_edit_content: str) -> set[int]:
    """Return the post-edit line numbers an edit added or replaced.

    Runs a line-level diff of *prior_content* against *post_edit_content* and
    collects the 1-indexed line numbers in *post_edit_content* that fall inside
    a ``replace`` or ``insert`` opcode. This mirrors the "added lines" notion
    that ``code_rules_gate.parse_added_line_numbers`` derives from
    ``git diff --unified=0``, so the PreToolUse layer and the gate agree on
    which lines the change touched.

    Args:
        prior_content: The file content before the edit.
        post_edit_content: The reconstructed file content after the edit.

    Returns:
        The set of 1-indexed line numbers in *post_edit_content* that the edit
        added or replaced.
    """
    matcher = difflib.SequenceMatcher(
        a=prior_content.splitlines(),
        b=post_edit_content.splitlines(),
        autojunk=False,
    )
    all_changed_lines: set[int] = set()
    for each_tag, _, _, each_post_start, each_post_end in matcher.get_opcodes():
        if each_tag in ALL_DIFF_CHANGED_OPCODE_TAGS:
            for each_post_index in range(each_post_start, each_post_end):
                all_changed_lines.add(each_post_index + 1)
    return all_changed_lines


def _scope_violations_to_changed_lines(
    all_violations_in_walk_order: list[tuple[range, str]],
    all_changed_lines: set[int] | None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Scope span-tagged violations by diff intersection.

    In-scope violations are always reported; the untouched out-of-scope set is
    surfaced or dropped according to which caller path is active:

    - ``defer_scope_to_caller`` True (the commit/push gate): every violation is
      returned in walk order so the gate's ``split_violations_by_scope`` can
      classify blocking vs advisory by added line. The gate does this scoping,
      so no scoping happens here.
    - ``all_changed_lines`` None (a terminal new-file or full-file write): every
      line was just authored, so every violation is in scope and returned.
    - ``all_changed_lines`` provided (a terminal diff-scoped Edit): only the
      in-scope violations whose span intersects the changed lines are returned;
      the untouched out-of-scope set is dropped, because untouched code must not
      block a single-file edit.

    Args:
        all_violations_in_walk_order: ``(span_range, issue_message)`` pairs in
            ``ast.walk`` traversal order, where ``span_range`` covers the
            violation's source lines.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat every violation as in-scope.
        defer_scope_to_caller: When True, return every violation message in walk
            order so the gate scopes by added line. When False, this enforcer is
            terminal and scopes directly.

    Returns:
        Every violation message when *defer_scope_to_caller* is True or
        *all_changed_lines* is None; otherwise only the in-scope messages whose
        span intersects the changed lines — so an edit that grows a function
        past the threshold always blocks even when many earlier untouched
        functions already exceed it.
    """
    if defer_scope_to_caller:
        return [each_message for _, each_message in all_violations_in_walk_order]
    if all_changed_lines is None:
        return [each_message for _, each_message in all_violations_in_walk_order]
    return [
        each_message
        for each_span, each_message in all_violations_in_walk_order
        if any(each_line in all_changed_lines for each_line in each_span)
    ]


def check_function_length(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag functions whose definition span exceeds cognitive-load thresholds.

    Function definition spans (signature line through last body statement,
    inclusive) at or above ``FUNCTION_LENGTH_BLOCKING_THRESHOLD`` (60
    lines) appear in the returned issues list and block the write at the
    gate. The threshold rests on the small-function guidance in Robert C.
    Martin, *Clean Code* Ch. 3 ("Functions") and the Google Python Style
    Guide's ~40-line function review hint
    (https://google.github.io/styleguide/pyguide.html); this gate blocks on
    body growth that pushes a function past that span. It does not derive
    from CODE_RULES §6.5, which governs advisory file-length signals and
    argues against hard numeric blocks.

    The issue message carries ``Function NAME (defined at line X) is Y lines``
    precisely so the gate's ``function_length_span_range`` can recover the
    function's full declared span (lines ``X`` through ``X + Y - 1``). The
    gate classifies the violation blocking when that span intersects the
    diff's added lines — the body grew this diff — and advisory otherwise — a
    pre-existing, untouched long function in a file the diff happened to
    touch. Anchoring to the span rather than a single ``Line N:`` definition
    line lets body growth on any interior line block correctly even when the
    ``def`` line itself is untouched.

    Exempt: test files (test bodies are sometimes long by necessity), Django
    migrations (auto-generated), workflow registries (registry entries), and
    hook infrastructure.

    Args:
        content: The Python source to analyze.
        file_path: The path of the file being checked.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a violation
            blocks only when the function's declared span intersects the changed
            lines.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate's ``split_violations_by_scope`` can scope by added
            line and report the in-scope set.

    Returns:
        Blocking issues. When *defer_scope_to_caller* is True every violation is
        returned for the gate to scope; otherwise every violation in scope is
        returned.
    """
    if is_test_file(file_path):
        return []
    if is_hook_infrastructure(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    all_violations_in_walk_order: list[tuple[range, str]] = []
    for each_node in ast.walk(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        line_span = _function_definition_line_span(each_node)
        if line_span >= FUNCTION_LENGTH_BLOCKING_THRESHOLD:
            span_range = range(each_node.lineno, each_node.lineno + line_span)
            message = (
                f"Function {each_node.name!r} (defined at line {each_node.lineno}) "
                f"is {line_span} lines - {FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX}"
            )
            all_violations_in_walk_order.append((span_range, message))
    return _scope_violations_to_changed_lines(
        all_violations_in_walk_order,
        all_changed_lines,
        defer_scope_to_caller,
    )


def validate_content(
    content: str,
    file_path: str,
    old_content: str = "",
    full_file_content: str | None = None,
    prior_full_file_content: str = "",
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Run all applicable validators on content.

    Args:
        content: The new content being written. For Edit, this is the
            ``new_string`` fragment; for Write, the entire new file body.
        file_path: Path to the file.
        old_content: Previous content (old_string for Edit, existing file for Write).
            Used to detect comment additions/removals instead of flagging all comments.
        full_file_content: For Edit operations, the reconstructed post-edit
            content of the entire file (existing file with ``old_string`` replaced
            by ``new_string``). Whole-file checks such as the unused-import
            scanner use this to evaluate references across the file rather than
            just within the inserted fragment.
        prior_full_file_content: For Edit operations, the entire file content as
            it existed before the edit applied. Whole-file span checks
            (function length, test isolation) diff this against
            ``full_file_content`` to recover the lines the edit touched, then
            block only on violations whose source span intersects those lines —
            mirroring the gate's span-intersection scoping. Defaults to the
            empty string for Write and for gate invocations, which leaves those
            checks scanning the whole file with no diff scoping.
        defer_scope_to_caller: The explicit signal that a downstream scoper will
            run, used to disambiguate the two callers that supply no changed-line
            set. The commit/push gate passes True: it owns
            ``split_violations_by_scope`` and classifies blocking vs advisory by
            added line, so the function-length, test-isolation, and banned-noun
            checks return their violations unscoped for the gate to classify.
            PreToolUse new-file or full-file writes leave this False: this
            enforcer is terminal, so it marks every violation in scope.
    """
    extension = get_file_extension(file_path)
    all_issues = []
    effective_content = content if full_file_content is None else full_file_content
    all_changed_lines = (
        changed_line_numbers(prior_full_file_content, full_file_content)
        if full_file_content is not None
        else None
    )

    if extension in ALL_PYTHON_EXTENSIONS:
        if not is_test_file(file_path):
            all_issues.extend(check_comment_changes(old_content, content, file_path))
        all_issues.extend(check_imports_at_top(content))
        all_issues.extend(check_logging_fstrings(content))
        all_issues.extend(check_windows_api_none(content))
        all_issues.extend(check_magic_values(content, file_path))
        all_issues.extend(check_fstring_structural_literals(content, file_path))
        all_issues.extend(check_constants_outside_config(content, file_path))
        all_issues.extend(check_constants_outside_config_advisory(content, file_path))
        all_issues.extend(check_file_global_constants_use_count(content, file_path))
        all_issues.extend(check_type_escape_hatches(effective_content, file_path))
        all_issues.extend(check_banned_identifiers(content, file_path))
        all_issues.extend(
            check_banned_noun_word_boundary(
                effective_content,
                file_path,
                all_changed_lines,
                defer_scope_to_caller,
            )
        )
        all_issues.extend(check_banned_prefixes(effective_content, file_path))
        all_issues.extend(check_stub_implementations(effective_content, file_path))
        all_issues.extend(check_typed_dict_encode_decode(effective_content, file_path))
        all_issues.extend(check_test_branching_in_production(effective_content, file_path))
        all_issues.extend(check_bare_except(effective_content, file_path))
        all_issues.extend(check_thin_wrapper_files(effective_content, file_path))
        all_issues.extend(check_boundary_types(effective_content, file_path))
        all_issues.extend(check_docstring_format(effective_content, file_path))
        all_issues.extend(check_docstring_args_match_signature(effective_content, file_path))
        all_issues.extend(
            check_boolean_naming(
                effective_content,
                file_path,
                all_changed_lines,
                defer_scope_to_caller,
            )
        )
        all_issues.extend(
            check_ignored_must_check_return(
                effective_content,
                file_path,
                all_changed_lines,
                defer_scope_to_caller,
            )
        )
        all_issues.extend(check_skip_decorators_in_tests(content, file_path))
        all_issues.extend(
            check_tests_use_isolated_filesystem_paths(
                effective_content,
                file_path,
                all_changed_lines,
                defer_scope_to_caller,
            )
        )
        all_issues.extend(check_existence_check_tests(content, file_path))
        all_issues.extend(check_constant_equality_tests(content, file_path))
        all_issues.extend(check_unused_optional_parameters(content, file_path))
        all_issues.extend(check_collection_prefix(content, file_path))
        all_issues.extend(check_stuttering_collection_prefix(content, file_path))
        all_issues.extend(check_hardcoded_user_paths(content, file_path))
        all_issues.extend(check_sys_path_insert_deduplication_guard(content, file_path))
        all_issues.extend(
            check_unused_module_level_imports(content, file_path, full_file_content)
        )
        all_issues.extend(check_library_print(content, file_path))
        all_issues.extend(check_parameter_annotations(content, file_path))
        all_issues.extend(check_return_annotations(content, file_path))
        all_issues.extend(
            check_function_length(
                effective_content,
                file_path,
                all_changed_lines,
                defer_scope_to_caller,
            )
        )
        all_issues.extend(check_loop_variable_naming(content, file_path))
        all_issues.extend(check_inline_literal_collections(content, file_path))
        all_issues.extend(check_inline_tuple_string_magic(content, file_path))
        all_issues.extend(check_string_literal_magic(content, file_path))
        check_incomplete_mocks(content, file_path)
        check_duplicated_format_patterns(content, file_path)

    elif extension in ALL_JAVASCRIPT_EXTENSIONS:
        if not is_test_file(file_path):
            all_issues.extend(check_comment_changes(old_content, content, file_path))
        all_issues.extend(check_e2e_test_naming(content, file_path))

    if extension in ALL_CODE_EXTENSIONS:
        advise_file_line_count(content, file_path)

    return all_issues


def _read_existing_file_content(file_path: str) -> str | None:
    """Return the on-disk content of *file_path*, or None when it cannot be read."""
    try:
        with open(file_path, "r", encoding="utf-8") as existing_file:
            return existing_file.read()
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None


def prior_and_post_edit_content(
    file_path: str, old_string: str, new_string: str,
) -> tuple[str | None, str | None]:
    """Return the pre-edit and post-edit file content from a single disk read.

    Reads ``file_path`` once and derives both views from that single read so the
    prior and the reconstruction never diverge across two independent reads.
    The post-edit view replaces the first occurrence of ``old_string`` with
    ``new_string``, mirroring how the Edit tool itself applies a single
    replacement.

    Returns ``(None, None)`` when the file cannot be read, ``old_string`` is
    empty, or ``old_string`` is not present in the existing file (the Edit will
    fail or has already been applied — neither case yields a well-defined
    post-edit view). A failed prior read is never coerced to an empty string,
    because an empty prior diffs every line of the reconstruction as changed and
    defeats the diff scoping the scoped checks rely on.

    Args:
        file_path: The path of the file the Edit targets.
        old_string: The Edit's ``old_string`` fragment.
        new_string: The Edit's ``new_string`` fragment.

    Returns:
        A ``(prior_content, post_edit_content)`` pair, or ``(None, None)`` when
        no well-defined post-edit view exists.
    """
    if not old_string:
        return None, None
    existing_content = _read_existing_file_content(file_path)
    if existing_content is None:
        return None, None
    if old_string not in existing_content:
        return None, None
    return existing_content, existing_content.replace(old_string, new_string, 1)


def main() -> None:
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path", "")

    if not file_path:
        sys.exit(0)

    if is_hook_infrastructure(file_path):
        sys.exit(0)

    extension = get_file_extension(file_path)
    if extension not in ALL_CODE_EXTENSIONS:
        sys.exit(0)

    old_content = ""
    prior_full_file_content = ""
    full_file_content_after_edit: str | None = None
    if tool_name == "Edit":
        content = tool_input.get("new_string", "")
        old_content = tool_input.get("old_string", "")
        prior_content, full_file_content_after_edit = prior_and_post_edit_content(
            file_path, old_content, content,
        )
        prior_full_file_content = prior_content or ""
        if full_file_content_after_edit is None:
            full_file_content_after_edit = _read_existing_file_content(file_path)
            if full_file_content_after_edit is None:
                sys.exit(0)
    else:
        content = tool_input.get("content", "") or tool_input.get("new_string", "")
        old_content = _read_existing_file_content(file_path) or ""

        if old_content:
            sys.exit(0)

    if not content:
        sys.exit(0)

    issues = validate_content(
        content,
        file_path,
        old_content,
        full_file_content_after_edit,
        prior_full_file_content,
    )

    if issues:
        issue_list = "; ".join(issues[:10])
        deny_payload = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"BLOCKED: [CODE_RULES] {len(issues)} violation(s): {issue_list}",
            }
        }
        print(json.dumps(deny_payload))
        sys.stdout.flush()

    sys.exit(0)


if __name__ == "__main__":
    main()