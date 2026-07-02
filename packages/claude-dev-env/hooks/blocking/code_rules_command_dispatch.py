"""Meta-gate flagging an unanchored multi-word command pattern in a blocker.

A hook that classifies a shell command reads the command text and matches it
against a regex. When that regex names a multi-word command such as
``gh\\s+pr\\s+(create|edit)`` and is matched with a bare ``re.search`` — no
start anchor and no first-word tokenization — the pattern matches the command
as a substring anywhere in the string. A benign command like
``echo gh pr create --title x`` then trips the gate. This check flags that shape
at write time on files under ``hooks/blocking/`` so a new blocker anchors its
command match to the start of the command or tokenizes the first word.
"""

import ast
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_shared import (  # noqa: E402
    _scope_violations_to_changed_lines,
    is_test_file,
)

from hooks_constants.command_dispatch_constants import (  # noqa: E402
    ALL_REGEX_START_ANCHOR_TOKENS,
    COMMAND_DISPATCH_LITERAL_PATTERN,
    COMMAND_DISPATCH_MESSAGE_SUFFIX,
    COMMAND_DISPATCH_PATH_MARKER,
    COMMAND_KEY_ACCESS_PATTERN,
    FIRST_TOKEN_TOKENIZATION_PATTERN,
    MAX_COMMAND_DISPATCH_ISSUES,
)


def _is_under_hooks_blocking(file_path: str) -> bool:
    """Return whether the path sits under the ``hooks/blocking`` directory."""
    return COMMAND_DISPATCH_PATH_MARKER in file_path.replace("\\", "/")


def _command_literal_is_anchored(literal_value: str, match_start: int) -> bool:
    """Return whether a start anchor precedes the command word in the pattern.

    Args:
        literal_value: The regex string literal the command word appears in.
        match_start: The index where the command word match begins.

    Returns:
        True when a ``^`` or ``\\A`` anchor appears before the command word, so
        the pattern binds the command to the start of the string.
    """
    prefix = literal_value[:match_start]
    return any(each_anchor in prefix for each_anchor in ALL_REGEX_START_ANCHOR_TOKENS)


def _unanchored_command_literals(
    parsed_tree: ast.AST,
) -> list[tuple[range, str]]:
    """Return one span-tagged violation per unanchored command-regex literal.

    Args:
        parsed_tree: The parsed module to scan for string-constant nodes.

    Returns:
        ``(line_range, message)`` pairs in source order.
    """
    all_violations: list[tuple[range, str]] = []
    for each_node in ast.walk(parsed_tree):
        if not isinstance(each_node, ast.Constant) or not isinstance(
            each_node.value, str
        ):
            continue
        literal_match = COMMAND_DISPATCH_LITERAL_PATTERN.search(each_node.value)
        if literal_match is None:
            continue
        if _command_literal_is_anchored(each_node.value, literal_match.start()):
            continue
        end_line = each_node.end_lineno or each_node.lineno
        message = (
            f"Line {each_node.lineno}: command pattern {each_node.value!r} "
            f"{COMMAND_DISPATCH_MESSAGE_SUFFIX}"
        )
        all_violations.append((range(each_node.lineno, end_line + 1), message))
    return all_violations


def check_unanchored_command_dispatch(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag an unanchored multi-word command regex in a hooks/blocking file.

    The check fires only on a file under ``hooks/blocking/`` that reads a
    ``command`` key (a shell-command classifier) and does not tokenize the
    command's first word (no ``shlex.split`` or ``.split(`` nearby). Under those
    conditions, a regex string literal naming a known command word followed by
    ``\\s+`` without a leading ``^``/``\\A`` anchor is flagged. Findings scope to
    *all_changed_lines* so a pre-existing pattern on an untouched line does not
    block an edit while a newly written one does.

    Args:
        content: The source text to inspect — the reconstructed full file on an
            Edit so the parse succeeds.
        file_path: The path the source will be written to, used for scoping to
            ``hooks/blocking`` and skipping test files.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope.
        defer_scope_to_caller: When True, return every violation so a downstream
            scoper classifies by added line.

    Returns:
        One issue per unanchored command-regex literal, scoped to the changed
        lines unless *defer_scope_to_caller* is True or *all_changed_lines* is
        None, capped at the module limit.
    """
    if is_test_file(file_path) or not _is_under_hooks_blocking(file_path):
        return []
    if COMMAND_KEY_ACCESS_PATTERN.search(content) is None:
        return []
    if FIRST_TOKEN_TOKENIZATION_PATTERN.search(content) is not None:
        return []
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []
    all_violations_in_source_order = _unanchored_command_literals(parsed_tree)
    scoped_issues = _scope_violations_to_changed_lines(
        all_violations_in_source_order,
        all_changed_lines,
        defer_scope_to_caller,
    )
    if defer_scope_to_caller:
        return scoped_issues
    return scoped_issues[:MAX_COMMAND_DISPATCH_ISSUES]
