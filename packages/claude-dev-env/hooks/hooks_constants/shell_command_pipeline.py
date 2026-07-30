"""Quote-aware shell command pipeline parsing.

Turns one Bash command string into operator-paired simple-command segments after
line-continuation join, comment strip, heredoc body drop, and parenthesis-group
join::

    scannable_command_lines("pytest tests | tee out.log")
        -> ["pytest tests | tee out.log"]
    segments_with_following_operator(["pytest", "tests", "|", "tee", "out.log"])
        -> [(["pytest", "tests"], "|"), (["tee", "out.log"], "")]

No pytest classification and no deny decision live here. Callers that need a
program verdict compose on top of these segments.
"""

from __future__ import annotations

import shlex
from typing import NamedTuple

from hooks_constants.piped_pytest_blocker_constants import (
    ALL_OPERATOR_TOKENS_LONGEST_FIRST,
    ALL_PIPE_OPERATOR_TOKENS,
    ALL_REDIRECTION_SUFFIX_CHARACTERS,
    ALL_SEGMENT_RESET_OPERATOR_TOKENS,
    CLOSED_GROUP_DEPTH,
    COMMAND_LINE_SPLIT_PATTERN,
    COMMENT_START_CHARACTER,
    COMMENT_START_GROUP,
    COMMENT_START_SCAN_PATTERN,
    DISABLED_LEXER_COMMENTERS,
    GROUP_CLOSE_CHARACTER,
    GROUP_OPEN_CHARACTER,
    HEREDOC_OPENER_OPERATOR,
    HEREDOC_OPENER_PATTERN,
    HEREDOC_STRIPPED_INDENT_CHARACTERS,
    HEREDOC_TAB_STRIP_GROUP,
    HEREDOC_TAB_STRIP_MARKER,
    HEREDOC_TERMINATOR_GROUP,
    LINE_CONTINUATION_JOIN,
    LINE_CONTINUATION_PATTERN,
    NO_FOLLOWING_OPERATOR,
    PAREN_GROUP_LINE_JOIN,
    PUNCTUATION_ONLY_TOKEN_PATTERN,
    QUOTED_REGION_PATTERN,
    QUOTED_REGION_REPLACEMENT,
)

__all__ = [
    "PendingHeredoc",
    "all_operator_aware_tokenizations",
    "all_operator_split_tokens",
    "all_punctuation_token_parts",
    "closes_the_heredoc",
    "command_line_without_comment",
    "join_line_continuations",
    "live_command_lines",
    "paren_group_joined_lines",
    "pending_heredoc_opened_by",
    "pipeline_segments_for_command",
    "scannable_command_lines",
    "segments_with_following_operator",
]


class PendingHeredoc(NamedTuple):
    """The word an open heredoc closes on, and how its opener lets that word be indented."""

    terminator: str
    allows_leading_tabs: bool


def join_line_continuations(command: str) -> str:
    """Return the command with backslash line continuations joined.

    ::

        pytest tests \\\\
            | tee out.log     ->  "pytest tests | tee out.log"

    Args:
        command: One Bash command that may carry trailing-backslash continuations.

    Returns:
        The same command with each continuation removed so the next line sits
        on the same physical line.
    """
    return LINE_CONTINUATION_PATTERN.sub(LINE_CONTINUATION_JOIN, command)


def all_operator_aware_tokenizations(command: str) -> list[list[str]]:
    """Return quote-aware tokenizations that carry operators as their own tokens.

    POSIX mode resolves quoting the way Git Bash does; raw mode keeps a Windows
    interpreter path such as ``C:\\Python313\\python.exe`` whole, since POSIX
    mode reads its backslashes as escapes. Both are returned so a caller can
    grade either spelling.

    The lexer's own commenters are cleared, because it cuts at a ``#`` anywhere
    in a word while a shell starts a comment only at a word's start.
    ``command_line_without_comment`` owns comment removal.

    Args:
        command: One logical Bash command line (continuations already joined).

    Returns:
        Zero, one, or two non-empty token lists (POSIX and/or raw).
    """
    all_tokenizations: list[list[str]] = []
    for each_posix_mode in (True, False):
        lexer = shlex.shlex(command, posix=each_posix_mode, punctuation_chars=True)
        lexer.whitespace_split = True
        lexer.commenters = DISABLED_LEXER_COMMENTERS
        try:
            all_tokens = list(lexer)
        except ValueError:
            continue
        if all_tokens:
            all_tokenizations.append(all_tokens)
    return all_tokenizations


def _trailing_operator_token(token: str) -> str | None:
    """Return the longest control operator the token ends with, or None."""
    for each_operator in ALL_OPERATOR_TOKENS_LONGEST_FIRST:
        if token.endswith(each_operator):
            return each_operator
    return None


def all_punctuation_token_parts(token: str) -> list[str]:
    """Split a punctuation-only token into its leading text and trailing operators.

    ::

        )|      [')', '|']
        )||     [')', '||']
        tests   ['tests']

    Args:
        token: One token from an operator-aware tokenization.

    Returns:
        The token's parts in original order — a one-item list when no split is needed.
    """
    if PUNCTUATION_ONLY_TOKEN_PATTERN.fullmatch(token) is None:
        return [token]
    all_peeled_operators: list[str] = []
    remaining_text = token
    while True:
        trailing_operator = _trailing_operator_token(remaining_text)
        if trailing_operator is None or trailing_operator == remaining_text:
            break
        leading_text = remaining_text[: -len(trailing_operator)]
        if leading_text.endswith(ALL_REDIRECTION_SUFFIX_CHARACTERS):
            break
        all_peeled_operators.append(trailing_operator)
        remaining_text = leading_text
    return [remaining_text, *reversed(all_peeled_operators)]


def all_operator_split_tokens(all_command_tokens: list[str]) -> list[str]:
    """Return the tokens with every glued punctuation-and-operator token split apart.

    Args:
        all_command_tokens: Tokens from an operator-aware tokenization.

    Returns:
        Tokens with glued punctuation operators peeled into their own items.
    """
    all_split_tokens: list[str] = []
    for each_token in all_command_tokens:
        all_split_tokens.extend(all_punctuation_token_parts(each_token))
    return all_split_tokens


def segments_with_following_operator(
    all_command_tokens: list[str],
) -> list[tuple[list[str], str]]:
    """Pair each simple-command segment with the control operator that ends it.

    A redirection token stays inside its segment. A close paren stays inside too,
    so a subshell's program survives to the pipe that follows it.

    Args:
        all_command_tokens: Tokens from an operator-aware tokenization.

    Returns:
        ``(segment_tokens, following_operator)`` pairs; the last pair carries
        an empty following operator when the command ends without one.
    """
    all_segments: list[tuple[list[str], str]] = []
    current_segment: list[str] = []
    for each_token in all_operator_split_tokens(all_command_tokens):
        if (
            each_token in ALL_PIPE_OPERATOR_TOKENS
            or each_token in ALL_SEGMENT_RESET_OPERATOR_TOKENS
        ):
            all_segments.append((current_segment, each_token))
            current_segment = []
            continue
        current_segment.append(each_token)
    all_segments.append((current_segment, NO_FOLLOWING_OPERATOR))
    return all_segments


def pending_heredoc_opened_by(command_line: str) -> PendingHeredoc | None:
    """Return the heredoc the line opens, or None when it opens none.

    ::

        cat > run.sh <<EOF     PendingHeredoc('EOF', allows_leading_tabs=False)
        cat > run.sh <<-EOF    PendingHeredoc('EOF', allows_leading_tabs=True)
        cat file <<<word       None
        echo hi                None

    Args:
        command_line: One physical command line.

    Returns:
        The pending heredoc, or None when the line opens none.
    """
    heredoc_opener = HEREDOC_OPENER_PATTERN.search(command_line)
    if heredoc_opener is None:
        return None
    return PendingHeredoc(
        terminator=heredoc_opener.group(HEREDOC_TERMINATOR_GROUP),
        allows_leading_tabs=(
            heredoc_opener.group(HEREDOC_TAB_STRIP_GROUP) == HEREDOC_TAB_STRIP_MARKER
        ),
    )


def closes_the_heredoc(command_line: str, pending_heredoc: PendingHeredoc) -> bool:
    """Return True when the line is the terminator its opener spelled.

    Args:
        command_line: One physical command line inside an open heredoc.
        pending_heredoc: The opener that is still waiting to close.

    Returns:
        True when this line ends the heredoc body.
    """
    if pending_heredoc.allows_leading_tabs:
        return (
            command_line.lstrip(HEREDOC_STRIPPED_INDENT_CHARACTERS)
            == pending_heredoc.terminator
        )
    return command_line == pending_heredoc.terminator


def live_command_lines(all_command_lines: list[str]) -> list[str]:
    """Return the lines the call runs, dropping every heredoc body and terminator.

    Args:
        all_command_lines: The physical lines of one Bash command, in order.

    Returns:
        The lines outside every heredoc body, in their original order.
    """
    all_live_lines: list[str] = []
    pending_heredoc: PendingHeredoc | None = None
    for each_line in all_command_lines:
        if pending_heredoc is not None:
            if closes_the_heredoc(each_line, pending_heredoc):
                pending_heredoc = None
            continue
        all_live_lines.append(each_line)
        pending_heredoc = pending_heredoc_opened_by(each_line)
    return all_live_lines


def command_line_without_comment(command_line: str) -> str:
    """Return the line with a shell comment and everything after it removed.

    ::

        python -m pytest tests  # fast   ->  python -m pytest tests
        pytest -k "a#b"                  ->  unchanged (hash inside quotes)
        tee run#1.log                    ->  unchanged (hash inside a word)

    Args:
        command_line: One physical command line.

    Returns:
        The line up to its comment, or the whole line when it carries none.
    """
    for each_match in COMMENT_START_SCAN_PATTERN.finditer(command_line):
        if each_match.group(COMMENT_START_GROUP) is not None:
            return command_line[: each_match.start(COMMENT_START_GROUP)]
    return command_line


def _comment_free_lines(all_command_lines: list[str]) -> list[str]:
    """Return every line with its shell comment removed.

    Args:
        all_command_lines: The physical lines of one Bash command, in order.

    Returns:
        The comment-free lines, in their original order and count.
    """
    return [command_line_without_comment(each_line) for each_line in all_command_lines]


def _paren_depth_change(command_line: str) -> int:
    """Return how many parenthesis groups the line opens, minus the ones it closes."""
    unquoted_line = QUOTED_REGION_PATTERN.sub(QUOTED_REGION_REPLACEMENT, command_line)
    return unquoted_line.count(GROUP_OPEN_CHARACTER) - unquoted_line.count(
        GROUP_CLOSE_CHARACTER
    )


def paren_group_joined_lines(all_command_lines: list[str]) -> list[str]:
    """Return the lines with each open parenthesis group joined into one logical line.

    Args:
        all_command_lines: Live command lines, comments removed and heredoc bodies dropped.

    Returns:
        One line per closed parenthesis group, and the unchanged line for every other.
    """
    all_joined_lines: list[str] = []
    all_pending_lines: list[str] = []
    open_group_depth = CLOSED_GROUP_DEPTH
    for each_line in all_command_lines:
        all_pending_lines.append(each_line)
        open_group_depth = max(
            open_group_depth + _paren_depth_change(each_line), CLOSED_GROUP_DEPTH
        )
        if open_group_depth > CLOSED_GROUP_DEPTH:
            continue
        all_joined_lines.append(PAREN_GROUP_LINE_JOIN.join(all_pending_lines))
        all_pending_lines = []
    if all_pending_lines:
        all_joined_lines.append(PAREN_GROUP_LINE_JOIN.join(all_pending_lines))
    return all_joined_lines


def scannable_command_lines(joined_command: str) -> list[str]:
    """Return the lines to tokenize, running only the passes the command's text calls for.

    ::

        pytest tests | tee x            split only
        pytest tests  # | tee x         comment pass runs
        (pytest tests) | tee x          parenthesis-group join runs
        cat <<EOF ... EOF               heredoc pass runs

    Args:
        joined_command: One Bash command, its line continuations already joined.

    Returns:
        The command lines ready for tokenization.
    """
    all_command_lines = COMMAND_LINE_SPLIT_PATTERN.split(joined_command)
    if COMMENT_START_CHARACTER in joined_command:
        all_command_lines = _comment_free_lines(all_command_lines)
    if HEREDOC_OPENER_OPERATOR in joined_command:
        all_command_lines = live_command_lines(all_command_lines)
    if GROUP_OPEN_CHARACTER not in joined_command:
        return all_command_lines
    return paren_group_joined_lines(all_command_lines)


def pipeline_segments_for_command(
    command: str,
) -> list[tuple[list[str], str]]:
    """Return every operator-paired segment across every quote-aware tokenization.

    Joins line continuations, builds scannable lines, tokenizes each, and pairs
    segments with the control operator that follows them. Duplicate segment
    pairs from the two tokenizations are kept only once, in first-seen order.

    Args:
        command: One Bash command as the tool would receive it.

    Returns:
        ``(segment_tokens, following_operator)`` pairs ready for a caller to
        grade, with no program classification applied.
    """
    joined_command = join_line_continuations(command)
    all_pairs: list[tuple[list[str], str]] = []
    seen_pair_keys: set[tuple[tuple[str, ...], str]] = set()
    for each_line in scannable_command_lines(joined_command):
        if not each_line.strip():
            continue
        for each_tokenization in all_operator_aware_tokenizations(each_line):
            for each_segment, each_operator in segments_with_following_operator(
                each_tokenization
            ):
                pair_key = (tuple(each_segment), each_operator)
                if pair_key in seen_pair_keys:
                    continue
                seen_pair_keys.add(pair_key)
                all_pairs.append((each_segment, each_operator))
    return all_pairs
