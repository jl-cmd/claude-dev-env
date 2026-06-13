"""Magic-number and f-string structural-literal checks for function bodies."""

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
    _extract_fstring_literal_parts,
    is_test_file,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_ALLOWED_MAGIC_NUMBER_LITERALS,
    ALL_NON_MAGIC_FSTRING_STRIPPED_VALUES,
    MAX_FSTRING_STRUCTURAL_LITERAL_ISSUES,
    MAX_MAGIC_VALUE_ISSUES,
    MINIMUM_FSTRING_LITERAL_LENGTH,
    STRING_LITERAL_QUOTE_PAIR_LENGTH,
)


def _mask_string_literals_preserving_length(source_line: str) -> str:
    """Replace every string literal with an equal-length neutral placeholder.

    Matching tests live in
    ``test_code_rules_enforcer_magic_string_masking.py``, one of the
    ``test_code_rules_enforcer_<suffix>.py`` family files the
    ``tdd_enforcer.py`` hook accepts as test candidates for the
    ``code_rules_*`` module family.
    """

    string_literal_pattern = re.compile(
        r"(\"(?:\\.|[^\"\\])*\")|('(?:\\.|[^'\\])*')",
    )

    def _replace_string_literal(match: re.Match[str]) -> str:
        matched_literal = match.group(0)
        opening_quote = matched_literal[0]
        closing_quote = matched_literal[-1]
        inner_length = max(len(matched_literal) - STRING_LITERAL_QUOTE_PAIR_LENGTH, 0)
        return f"{opening_quote}{'_' * inner_length}{closing_quote}"

    return string_literal_pattern.sub(_replace_string_literal, source_line)


def _carries_top_level_slice_colon(bracket_body: str) -> bool:
    """Return True when ``bracket_body`` holds a slice colon at its own level.

    The body is the text between one ``[...]`` pair. A slice colon is a ``:``
    that sits at the body's top level — not nested inside any ``(``, ``[``,
    or ``{`` opened within the body — and is not the ``:=`` walrus operator.
    A slice writes ``[:N]`` or ``[1:N]``; a plain subscript (``[K]``), a
    walrus subscript (``[(n := M)]``), and a lambda subscript
    (``[(lambda: V)()]``) carry no such colon.
    """
    nesting_depth = 0
    for each_position, each_character in enumerate(bracket_body):
        if each_character in "([{":
            nesting_depth += 1
            continue
        if each_character in ")]}":
            nesting_depth -= 1
            continue
        if each_character == ":" and nesting_depth == 0:
            next_position = each_position + 1
            character_after_colon = bracket_body[next_position : next_position + 1]
            follows_walrus = character_after_colon == "="
            if not follows_walrus:
                return True
    return False


def _innermost_bracket_body_around(masked_line: str, occurrence_position: int) -> str | None:
    """Return the body of the innermost ``[...]`` pair enclosing a position.

    Walks the line tracking open-bracket positions on a stack. The bracket
    pair directly enclosing ``occurrence_position`` is the one whose ``[``
    is on top of the stack when that position is reached; its body runs from
    just after that ``[`` to its matching ``]``. Returns ``None`` when the
    position lies outside every ``[...]`` pair.
    """
    open_bracket_positions: list[int] = []
    enclosing_open_position = -1
    for each_position, each_character in enumerate(masked_line):
        if each_position == occurrence_position:
            enclosing_open_position = open_bracket_positions[-1] if open_bracket_positions else -1
        if each_character == "[":
            open_bracket_positions.append(each_position)
            continue
        if each_character == "]" and open_bracket_positions:
            open_bracket_positions.pop()

    if enclosing_open_position == -1:
        return None

    closing_position = _matching_close_bracket_position(masked_line, enclosing_open_position)
    if closing_position == -1:
        return None
    return masked_line[enclosing_open_position + 1 : closing_position]


def _matching_close_bracket_position(masked_line: str, open_position: int) -> int:
    """Return the index of the ``]`` that closes the ``[`` at ``open_position``.

    Returns ``-1`` when the opening bracket has no matching close on the line.
    """
    depth = 0
    for each_position in range(open_position, len(masked_line)):
        each_character = masked_line[each_position]
        if each_character == "[":
            depth += 1
            continue
        if each_character == "]":
            depth -= 1
            if depth == 0:
                return each_position
    return -1


def _is_magic_number_inside_slice_bound(masked_line: str, number_text: str) -> bool:
    """Return True when ``number_text`` appears as a slice bound on the line.

    For each standalone-token occurrence of ``number_text``, the innermost
    ``[...]`` pair directly enclosing it is located. The number is a slice
    bound only when that innermost pair carries a top-level slice colon
    (``sha[:N]``, ``ts[1:N]``). A plain subscript index (``items[K]``), the
    inner index of a nested subscript (``a[b[I]:N]`` — the inner index sits
    inside the plain inner pair), a walrus subscript (``arr[(n := M)]``), and
    a lambda subscript (``seq[(lambda: V)()]``) are not slice bounds.
    """
    token_boundary_pattern = r"(?<![.\w])" + re.escape(number_text) + r"(?![.\w])"
    for each_match in re.finditer(token_boundary_pattern, masked_line):
        bracket_body = _innermost_bracket_body_around(masked_line, each_match.start())
        if bracket_body is None:
            continue
        if _carries_top_level_slice_colon(bracket_body):
            return True
    return False


def check_magic_values(content: str, file_path: str) -> list[str]:
    """Check for magic values in function bodies."""
    if is_config_file(file_path) or is_test_file(file_path):
        return []

    issues = []
    lines = content.split("\n")
    is_inside_function = False

    number_pattern = re.compile(r"(?<![.\w])(\d+\.?\d*)(?![.\w])")
    allowed_numbers = ALL_ALLOWED_MAGIC_NUMBER_LITERALS

    for each_line_number, each_line in enumerate(lines, 1):
        stripped = each_line.strip()

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
            for each_number in numbers_found:
                if each_number not in allowed_numbers:
                    if "range(" in stripped_without_string_literals or "enumerate(" in stripped_without_string_literals:
                        continue
                    if _is_magic_number_inside_slice_bound(stripped_without_string_literals, each_number):
                        issues.append(f"Line {each_line_number}: Magic value {each_number} - extract to named constant")
                        break
                    if "[" in stripped_without_string_literals and "]" in stripped_without_string_literals:
                        continue
                    issues.append(f"Line {each_line_number}: Magic value {each_number} - extract to named constant")
                    break

        if len(issues) >= MAX_MAGIC_VALUE_ISSUES:
            break

    return issues


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

    minimum_literal_length = MINIMUM_FSTRING_LITERAL_LENGTH
    maximum_issues_before_stop = MAX_FSTRING_STRUCTURAL_LITERAL_ISSUES
    non_magic_stripped_values = ALL_NON_MAGIC_FSTRING_STRIPPED_VALUES

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
