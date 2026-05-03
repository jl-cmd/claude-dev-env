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
from config.banned_identifiers_constants import (  # noqa: E402
    ALL_BANNED_IDENTIFIERS,
    BANNED_IDENTIFIER_MESSAGE_SUFFIX,
    BANNED_IDENTIFIER_SKIP_ADVISORY,
    MAX_BANNED_IDENTIFIER_ISSUES,
)
from config.hardcoded_user_path_constants import (  # noqa: E402
    HARDCODED_USER_PATH_GUIDANCE,
    HARDCODED_USER_PATH_PATTERN,
    MAX_HARDCODED_USER_PATH_ISSUES,
)
from config.stuttering_check_config import (  # noqa: E402
    MAX_STUTTERING_PREFIX_ISSUES,
    STUTTERING_ALL_PREFIX_PATTERN,
)
from config.sys_path_insert_constants import MAX_SYS_PATH_INSERT_ISSUES, SYS_PATH_INSERT_GUIDANCE  # noqa: E402
from config.stuttering_import_binding_constants import (  # noqa: E402
    AST_LINENO_ATTRIBUTE,
    MODULE_PATH_SEPARATOR,
    WILDCARD_IMPORT_SENTINEL,
)

PYTHON_EXTENSIONS = {".py"}
JAVASCRIPT_EXTENSIONS = {".js", ".ts", ".tsx", ".jsx"}
ALL_CODE_EXTENSIONS = PYTHON_EXTENSIONS | JAVASCRIPT_EXTENSIONS

TEST_PATH_PATTERNS = {"test_", "_test.", ".test.", ".spec.", "/tests/", "\\tests\\", "/tests.py", "\\tests.py"}
HOOK_INFRASTRUCTURE_PATTERNS = {"/.claude/hooks/", "\\.claude\\hooks\\", "\\.claude/hooks/", "/packages/claude-dev-env/hooks/", "\\packages\\claude-dev-env\\hooks\\"}
WORKFLOW_REGISTRY_PATTERNS = {"/workflow/", "\\workflow\\", "_tab.py", "/states.py", "\\states.py", "/modules.py", "\\modules.py"}
MIGRATION_PATH_PATTERNS = {"/migrations/", "\\migrations\\"}

ADVISORY_LINE_THRESHOLD_SOFT = 400
ADVISORY_LINE_THRESHOLD_HARD = 1000

BOOLEAN_NAME_PREFIXES: tuple[str, ...] = ("is_", "has_", "should_", "can_")
UPPER_SNAKE_CONSTANT_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


TYPE_CHECKING_BLOCK_PATTERN = re.compile(r"^(?P<indent>\s*)if\s+(typing\.)?TYPE_CHECKING\s*:\s*$")
IMPORT_STATEMENT_PREFIXES: tuple[str, ...] = ("import ", "from ")
NOT_INSIDE_TYPE_CHECKING_BLOCK = -1
FILE_GLOBAL_UPPER_SNAKE_PATTERN = re.compile(r"^_?[A-Z][A-Z0-9_]*$")

COLLECTION_TYPE_NAMES: frozenset[str] = frozenset({
    "list", "tuple", "set", "frozenset", "dict",
    "Iterable", "Sequence", "Mapping", "MutableMapping", "FrozenSet",
})
COLLECTION_BY_NAME_PATTERN: re.Pattern[str] = re.compile(r"^[a-z][a-z0-9]*_by_[a-z][a-z0-9_]*$")
CLI_FILE_PATH_MARKERS: tuple[str, ...] = ("/scripts/", "\\scripts\\", "_cli.py", "/cli.py", "\\cli.py")


def get_file_extension(file_path: str) -> str:
    """Extract lowercase file extension."""
    dot_index = file_path.rfind(".")
    if dot_index == -1:
        return ""
    return file_path[dot_index:].lower()


def is_hook_infrastructure(file_path: str) -> bool:
    """Check if file is a Claude Code hook (standalone infrastructure, not project code)."""
    path_lower = file_path.lower().replace("\\", "/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in HOOK_INFRASTRUCTURE_PATTERNS)


def is_test_file(file_path: str) -> bool:
    """Check if file is a test file."""
    path_lower = file_path.lower()
    basename_lower = path_lower.replace("\\", "/").rsplit("/", 1)[-1]
    if basename_lower == "conftest.py":
        return True
    return any(pattern in path_lower for pattern in TEST_PATH_PATTERNS)


def is_workflow_registry_file(file_path: str) -> bool:
    """Check if file is a workflow state/module registry file.

    Workflow tab files and state/module registry files use UPPER_SNAKE naming
    for StateDefinition and WorkflowModule instances by architectural convention.
    These are module-level singletons, not misplaced literal constants.
    """
    path_lower = file_path.lower().replace("\\", "/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in WORKFLOW_REGISTRY_PATTERNS)


def is_spec_file(file_path: str) -> bool:
    """Check if file is an E2E spec file."""
    return ".spec." in file_path.lower()


def check_comments_python(content: str) -> list[str]:
    """Check for comments in Python code."""
    issues = []
    lines = content.split("\n")

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()

        if not stripped:
            continue

        if stripped.startswith("#!"):
            continue

        if stripped.startswith("# type:"):
            continue

        if stripped.startswith("# noqa"):
            continue

        if stripped.startswith("# pylint:"):
            continue

        if stripped.startswith("# pragma:"):
            continue

        comment_index = line.find("#")
        if comment_index != -1:
            before_comment = line[:comment_index]
            if not before_comment.strip().startswith(("'", '"')):
                in_string = False
                quote_char = None
                for i, char in enumerate(before_comment):
                    if char in ("'", '"') and (i == 0 or before_comment[i - 1] != "\\"):
                        if not in_string:
                            in_string = True
                            quote_char = char
                        elif char == quote_char:
                            in_string = False

                if not in_string:
                    comment_text = line[comment_index + 1 :].strip()
                    if comment_text and not comment_text.startswith(("type:", "noqa", "pylint:", "pragma:")):
                        issues.append(f"Line {line_number}: Comment found - refactor to self-documenting code")

        if len(issues) >= 3:
            break

    return issues


def check_comments_javascript(content: str) -> list[str]:
    """Check for comments in JavaScript/TypeScript code."""
    issues = []
    lines = content.split("\n")
    in_multiline_comment = False

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()

        if not stripped:
            continue

        if in_multiline_comment:
            if "*/" in stripped:
                in_multiline_comment = False
            continue

        if stripped.startswith("/*"):
            in_multiline_comment = "*/" not in stripped
            if not stripped.startswith("/**"):
                issues.append(f"Line {line_number}: Block comment found - refactor to self-documenting code")
            continue

        if stripped.startswith("//"):
            if not stripped.startswith(("// @ts-", "// eslint-", "// prettier-", "/// ")):
                issues.append(f"Line {line_number}: Comment found - refactor to self-documenting code")

        if len(issues) >= 3:
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

    lines = content.split("\n")

    if extension in PYTHON_EXTENSIONS:
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("#"):
                if stripped.startswith(("#!", "# type:", "# noqa", "# pylint:", "# pragma:")):
                    continue
                standalone_comments.add(stripped)
            elif "#" in line:
                comment_index = line.find("#")
                before_comment = line[:comment_index]
                if not before_comment.strip().startswith(("'", '"')):
                    in_string = False
                    quote_char = None
                    for i, char in enumerate(before_comment):
                        if char in ("'", '"') and (i == 0 or before_comment[i - 1] != "\\"):
                            if not in_string:
                                in_string = True
                                quote_char = char
                            elif char == quote_char:
                                in_string = False
                    if not in_string:
                        comment_text = line[comment_index + 1 :].strip()
                        if comment_text and not comment_text.startswith(("type:", "noqa", "pylint:", "pragma:")):
                            inline_comments.add(line[comment_index:].strip())

    elif extension in JAVASCRIPT_EXTENSIONS:
        in_multiline = False
        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue
            if in_multiline:
                if "*/" in stripped:
                    in_multiline = False
                continue
            if stripped.startswith("/*"):
                in_multiline = "*/" not in stripped
                if not stripped.startswith("/**"):
                    standalone_comments.add(stripped)
                continue
            if stripped.startswith("//"):
                if not stripped.startswith(("// @ts-", "// eslint-", "// prettier-", "/// ")):
                    standalone_comments.add(stripped)
            elif "//" in line:
                before_slash = line[:line.index("//")]
                if before_slash.strip():
                    inline_comments.add(stripped[stripped.index("//"):])

    return inline_comments, standalone_comments


def check_comment_changes(old_content: str, new_content: str, file_path: str) -> list[str]:
    """Check for comment additions or removals between old and new content.

    Inline comments (after code on same line): BLOCK when added.
    Standalone comment lines: NUDGE (print advisory) when added.
    Existing comments being removed: BLOCK (comment preservation principle).
    """
    issues: list[str] = []

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
    """
    issues: list[str] = []
    lines = content.split("\n")
    inside_function = False
    function_indent = 0
    type_checking_block_indent = NOT_INSIDE_TYPE_CHECKING_BLOCK

    for line_number, each_line in enumerate(lines, 1):
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
            continue

        function_match = re.match(r"^(\s*)(async\s+)?def\s+\w+", each_line)
        if function_match:
            inside_function = True
            function_indent = len(function_match.group(1)) if function_match.group(1) else 0
            continue

        if inside_function:
            if current_indent <= function_indent and stripped and not stripped.startswith(("#", "@", ")")):
                inside_function = False

        is_inside_type_checking_block = type_checking_block_indent != NOT_INSIDE_TYPE_CHECKING_BLOCK
        if inside_function and not is_inside_type_checking_block:
            if stripped.startswith(IMPORT_STATEMENT_PREFIXES):
                issues.append(f"Line {line_number}: Import inside function - move to top of file")

    return issues


LOGGING_FSTRING_PATTERN = re.compile(
    r'\b(?:log_(?:debug|info|warning|error|critical|exception)'
    r'|(?:logger|logging|log)\.(?:debug|info|warning|error|critical|exception))'
    r'\s*\(\s*(?:[rR][fF]|[fF][rR]?)["\']'
)


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
    inside_function = False

    number_pattern = re.compile(r"(?<![.\w])(\d+\.?\d*)(?![.\w])")
    allowed_numbers = {"0", "1", "-1", "0.0", "1.0"}

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()

        if not stripped:
            continue

        if re.match(r"^(async\s+)?def\s+\w+", stripped):
            inside_function = True
            continue

        if re.match(r"^class\s+\w+", stripped):
            inside_function = False
            continue

        if inside_function:
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
    for each_node in ast.walk(parsed_tree):
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


def _comment_tokens(source: str) -> list[tokenize.TokenInfo]:
    """Return COMMENT tokens from source, or an empty list when tokenization fails."""
    try:
        return [
            each_token
            for each_token in tokenize.generate_tokens(io.StringIO(source).readline)
            if each_token.type == tokenize.COMMENT
        ]
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return []


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


def check_type_escape_hatches(content: str, file_path: str) -> list[str]:
    """Flag Any annotations and unjustified # type: ignore comments."""
    if is_test_file(file_path):
        return []

    issues: list[str] = []

    for each_any_line in _find_any_annotation_lines(content):
        issues.append(f"Line {each_any_line}: Any annotation - replace with explicit type")

    for each_ignore_line in _find_unjustified_type_ignore_lines(content):
        issues.append(
            f"Line {each_ignore_line}: Unjustified # type: ignore - add trailing '# reason' explaining why"
        )

    return issues


def is_migration_file(file_path: str) -> bool:
    """Check if file is a Django migration (must be self-contained)."""
    path_lower = file_path.lower().replace("\\", "/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in MIGRATION_PATH_PATTERNS)


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
    inside_function = False
    inside_class = False

    constant_pattern = re.compile(r"^([A-Z][A-Z0-9_]{2,})(?:\s*:\s*[^=]+)?\s*=\s*[^=]")

    for line_number, line in enumerate(lines, 1):
        stripped = line.strip()

        if not stripped:
            continue

        if re.match(r"^(async\s+)?def\s+\w+", stripped):
            inside_function = True
            continue

        if re.match(r"^class\s+\w+", stripped):
            inside_class = True
            inside_function = False
            continue

        indent = len(line) - len(line.lstrip())
        if indent == 0 and stripped and not stripped.startswith(("#", "@", ")")):
            inside_function = False
            inside_class = False

        if not inside_function and not inside_class:
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


def check_boolean_naming(content: str, file_path: str) -> list[str]:
    """Flag boolean assignments whose target name lacks a required prefix."""
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
    issues: list[str] = []
    for name, line_number, is_in_upper_snake_scope in _collect_boolean_assignments(tree):
        if len(name) == 1:
            continue
        if is_in_upper_snake_scope and UPPER_SNAKE_CONSTANT_PATTERN.match(name):
            continue
        if name.startswith(BOOLEAN_NAME_PREFIXES):
            continue
        issues.append(
            f"Line {line_number}: Boolean {name} - prefix with is_/has_/should_/can_"
        )
    return issues



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
    if get_file_extension(file_path) not in PYTHON_EXTENSIONS:
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


def _is_non_literal_default(value: object) -> bool:
    """Return True when a value is the sentinel for a non-literal default."""
    return value is _NON_LITERAL_DEFAULT_SENTINEL


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


BUILTIN_DICT_METHOD_NAMES: frozenset[str] = frozenset({
    "get", "items", "keys", "values", "update", "pop",
    "setdefault", "copy", "clear",
})


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
                    if each_node.attr in BUILTIN_DICT_METHOD_NAMES:
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


UNION_TYPING_NAMES: frozenset[str] = frozenset({"Optional", "Union"})


def _annotation_names_collection(annotation_node: ast.expr | None) -> bool:
    if annotation_node is None:
        return False
    if isinstance(annotation_node, ast.Name):
        return annotation_node.id in COLLECTION_TYPE_NAMES
    if isinstance(annotation_node, ast.Attribute):
        return annotation_node.attr in COLLECTION_TYPE_NAMES
    if isinstance(annotation_node, ast.BinOp) and isinstance(annotation_node.op, ast.BitOr):
        return (
            _annotation_names_collection(annotation_node.left)
            or _annotation_names_collection(annotation_node.right)
        )
    if isinstance(annotation_node, ast.Subscript):
        outer_value = annotation_node.value
        is_optional_or_union_subscript = (
            (isinstance(outer_value, ast.Name) and outer_value.id in UNION_TYPING_NAMES)
            or (isinstance(outer_value, ast.Attribute) and outer_value.attr in UNION_TYPING_NAMES)
        )
        if is_optional_or_union_subscript:
            slice_node = annotation_node.slice
            if isinstance(slice_node, ast.Tuple):
                return any(
                    _annotation_names_collection(each_element)
                    for each_element in slice_node.elts
                )
            return _annotation_names_collection(slice_node)
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


MAX_UNUSED_IMPORT_ISSUES: int = 25
UNUSED_IMPORT_GUIDANCE: str = (
    "remove unused import; if kept for side effects, mark with `# noqa: F401`"
)


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


def _name_appears_outside_imports(
    content_lines: list[str],
    import_line_numbers: set[int],
    name: str,
) -> bool:
    name_pattern = re.compile(rf"\b{re.escape(name)}\b")
    for each_line_index, each_line in enumerate(content_lines, start=1):
        if each_line_index in import_line_numbers:
            continue
        if name_pattern.search(each_line):
            return True
    return False


def _line_carries_noqa_marker(line_text: str) -> bool:
    return "# noqa" in line_text or "#noqa" in line_text


def check_unused_module_level_imports(content: str, file_path: str) -> list[str]:
    """Flag module-level imports that are never referenced in the rest of the file.

    The rule is intentionally conservative — files declaring __all__ or
    using TYPE_CHECKING are skipped to avoid false positives on
    re-exports and annotation-only imports.
    """
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    file_declares_dunder_all = any(
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
    if file_declares_dunder_all:
        return []
    if "TYPE_CHECKING" in content:
        return []
    content_lines = content.splitlines()
    import_line_numbers: set[int] = set()
    import_bindings: list[tuple[str, int, int | None]] = []
    for each_node in tree.body:
        if isinstance(each_node, (ast.Import, ast.ImportFrom)):
            import_line_numbers.add(each_node.lineno)
            for each_alias in each_node.names:
                import_line_numbers.add(each_alias.lineno or each_node.lineno)
            if isinstance(each_node, ast.ImportFrom) and each_node.module == "__future__":
                continue
            for each_binding in _import_alias_pairs(each_node):
                import_bindings.append(each_binding)
    issues: list[str] = []
    for each_name, each_line_number, each_from_keyword_line in import_bindings:
        if 1 <= each_line_number <= len(content_lines):
            if _line_carries_noqa_marker(content_lines[each_line_number - 1]):
                continue
        if each_from_keyword_line is not None and 1 <= each_from_keyword_line <= len(content_lines):
            if _line_carries_noqa_marker(content_lines[each_from_keyword_line - 1]):
                continue
        if _name_appears_outside_imports(content_lines, import_line_numbers, each_name):
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
    return any(marker.replace("\\", "/") in path_lower for marker in CLI_FILE_PATH_MARKERS)


def check_library_print(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path) or is_config_file(file_path) or is_hook_infrastructure(file_path):
        return []
    if _is_cli_entry_point(file_path):
        return []
    if get_file_extension(file_path) not in PYTHON_EXTENSIONS:
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


SELF_AND_CLS_PARAMETER_NAMES: frozenset[str] = frozenset({"self", "cls"})
LOOP_INDEX_LETTER_EXEMPTIONS: frozenset[str] = frozenset({"i", "j", "k", "_"})
EACH_PREFIX = "each_"
BARE_EACH_TOKEN = "each"
INLINE_COLLECTION_MIN_LENGTH = 3
ALL_CAPS_WITH_UNDERSCORE_PATTERN = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
DOTTED_SEGMENT_PATTERN = re.compile(r"^\.[a-z][a-z0-9_]*$")


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
    for node in ast.walk(tree):
        if not isinstance(node, (ast.For, ast.AsyncFor)):
            continue
        for each_name_node in _collect_target_names(node.target):
            target_name = each_name_node.id
            if target_name in LOOP_INDEX_LETTER_EXEMPTIONS:
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
            if each_arg.arg in SELF_AND_CLS_PARAMETER_NAMES:
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


def validate_content(content: str, file_path: str, old_content: str = "") -> list[str]:
    """Run all applicable validators on content.

    Args:
        content: The new content being written.
        file_path: Path to the file.
        old_content: Previous content (old_string for Edit, existing file for Write).
            Used to detect comment additions/removals instead of flagging all comments.
    """
    extension = get_file_extension(file_path)
    all_issues = []

    if extension in PYTHON_EXTENSIONS:
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
        all_issues.extend(check_type_escape_hatches(content, file_path))
        all_issues.extend(check_banned_identifiers(content, file_path))
        all_issues.extend(check_boolean_naming(content, file_path))
        all_issues.extend(check_skip_decorators_in_tests(content, file_path))
        all_issues.extend(check_existence_check_tests(content, file_path))
        all_issues.extend(check_constant_equality_tests(content, file_path))
        all_issues.extend(check_unused_optional_parameters(content, file_path))
        all_issues.extend(check_collection_prefix(content, file_path))
        all_issues.extend(check_stuttering_collection_prefix(content, file_path))
        all_issues.extend(check_hardcoded_user_paths(content, file_path))
        all_issues.extend(check_sys_path_insert_deduplication_guard(content, file_path))
        all_issues.extend(check_unused_module_level_imports(content, file_path))
        all_issues.extend(check_library_print(content, file_path))
        all_issues.extend(check_parameter_annotations(content, file_path))
        all_issues.extend(check_return_annotations(content, file_path))
        all_issues.extend(check_loop_variable_naming(content, file_path))
        all_issues.extend(check_inline_literal_collections(content, file_path))
        all_issues.extend(check_string_literal_magic(content, file_path))
        check_incomplete_mocks(content, file_path)
        check_duplicated_format_patterns(content, file_path)

    elif extension in JAVASCRIPT_EXTENSIONS:
        if not is_test_file(file_path):
            all_issues.extend(check_comment_changes(old_content, content, file_path))
        all_issues.extend(check_e2e_test_naming(content, file_path))

    if extension in ALL_CODE_EXTENSIONS:
        advise_file_line_count(content, file_path)

    return all_issues


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
    if tool_name == "Edit":
        content = tool_input.get("new_string", "")
        old_content = tool_input.get("old_string", "")
    else:
        content = tool_input.get("content", "") or tool_input.get("new_string", "")
        try:
            with open(file_path, "r", encoding="utf-8") as existing_file:
                old_content = existing_file.read()
        except (FileNotFoundError, OSError, UnicodeDecodeError):
            old_content = ""

        if old_content:
            sys.exit(0)

    if not content:
        sys.exit(0)

    issues = validate_content(content, file_path, old_content)

    if issues:
        issue_list = "; ".join(issues[:10])
        result = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": f"BLOCKED: [CODE_RULES] {len(issues)} violation(s): {issue_list}",
            }
        }
        print(json.dumps(result))
        sys.stdout.flush()

    sys.exit(0)


if __name__ == "__main__":
    main()