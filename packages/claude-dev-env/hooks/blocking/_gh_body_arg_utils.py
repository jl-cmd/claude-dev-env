"""Shared shell-token and gh body-arg parsing utilities for blocking hooks."""

from __future__ import annotations

import shlex
from typing import Iterator

body_file_flag: str = "--body-file"
body_file_flag_prefix: str = "--body-file="
body_file_short_flag: str = "-F"
body_file_short_flag_prefix: str = "-F="

all_body_flags: frozenset[str] = frozenset({"--body", "-b"})
all_body_flag_prefixes: tuple[str, ...] = ("--body=", "-b=")
all_value_flags: frozenset[str] = frozenset(
    {
        "--title",
        "-t",
        "--reviewer",
        "-r",
        "--assignee",
        "-a",
        "--label",
        "-l",
        "--milestone",
        "-m",
        "--project",
        "-p",
        "--base",
        "-B",
        "--head",
        "-H",
        "--repo",
        "-R",
        "--template",
        "-T",
        "--recover",
        body_file_flag,
        body_file_short_flag,
    }
)

all_value_flag_equals_prefixes: tuple[str, ...] = tuple(
    sorted((f"{each_flag}=" for each_flag in all_value_flags), key=len, reverse=True)
)

_all_equals_prefixes_for_skip: tuple[str, ...] = tuple(
    sorted(
        set(all_value_flag_equals_prefixes) | set(all_body_flag_prefixes),
        key=len,
        reverse=True,
    )
)

bash_continuation_marker: str = "\\"
powershell_continuation_marker: str = "`"

shell_variable_sigil: str = "$"
all_quote_characters: frozenset[str] = frozenset({'"', "'"})
minimum_meaningful_token_length: int = 2

non_body_value_flags: frozenset[str] = all_value_flags - {body_file_flag, body_file_short_flag}

_non_body_value_flag_equals_prefixes: tuple[str, ...] = tuple(
    sorted((f"{each_flag}=" for each_flag in non_body_value_flags), key=len, reverse=True)
)


def is_flag_shaped_token(token: str) -> bool:
    """Report whether a token is flag-shaped for body/PR-number extraction.

    Treats any token whose second character is "-" as flag-shaped, so bare
    "--" and "--<digit>" tokens both count as flags. `_is_flag_shaped` applies
    a stricter rule for token-stream scanning.
    """
    if len(token) < minimum_meaningful_token_length:
        return False
    if not token.startswith("-"):
        return False
    return token[1] == "-" or token[1].isalpha()


def strip_surrounding_quotes(token: str) -> str:
    if len(token) < minimum_meaningful_token_length:
        return token
    first_character = token[0]
    last_character = token[-1]
    if first_character in all_quote_characters and first_character == last_character:
        return token[1:-1]
    return token


def is_unresolvable_shell_value(token: str) -> bool:
    return token.startswith(shell_variable_sigil)


def _match_prefix(token: str, all_prefixes: tuple[str, ...]) -> str | None:
    for each_prefix in all_prefixes:
        if token.startswith(each_prefix):
            return each_prefix
    return None


def match_body_flag_equals_prefix(token: str) -> str | None:
    return _match_prefix(token, all_body_flag_prefixes)


def match_body_file_equals_prefix(token: str) -> str | None:
    return _match_prefix(token, (body_file_flag_prefix, body_file_short_flag_prefix))


def match_non_body_value_flag_equals_prefix(token: str) -> str | None:
    return _match_prefix(token, _non_body_value_flag_equals_prefixes)


def _count_trailing_run(text: str, marker_character: str) -> int:
    trailing_run_length = 0
    for each_character in reversed(text):
        if each_character != marker_character:
            break
        trailing_run_length += 1
    return trailing_run_length


def _is_bash_continuation(stripped_line: str) -> bool:
    return _count_trailing_run(stripped_line, bash_continuation_marker) == 1


def _is_powershell_continuation(stripped_line: str) -> bool:
    if _count_trailing_run(stripped_line, powershell_continuation_marker) != 1:
        return False
    if len(stripped_line) < 2:
        return False
    character_before_marker = stripped_line[-2]
    return character_before_marker.isspace()


def get_logical_first_line(command: str) -> str:
    logical_line = ""
    for each_line in command.splitlines():
        stripped_line = each_line.rstrip()
        if _is_bash_continuation(stripped_line) or _is_powershell_continuation(stripped_line):
            logical_line += stripped_line[:-1].rstrip() + " "
            continue
        logical_line += each_line
        break
    return logical_line.strip()


def _is_flag_shaped(token: str) -> bool:
    """Report whether a token is flag-shaped for token-stream scanning.

    Requires an alphabetic character after "--", so bare "--" and "--<digit>"
    tokens are not flag-shaped. `is_flag_shaped_token` applies a looser rule
    for body/PR-number extraction.
    """
    if len(token) < minimum_meaningful_token_length:
        return False
    if not token.startswith("-"):
        return False
    second_character = token[1]
    if second_character == "-":
        return len(token) > 2 and token[2].isalpha()
    return second_character.isalpha()


def _quoted_value_starts_split(value_token: str) -> bool:
    if len(value_token) < minimum_meaningful_token_length:
        return False
    first_character = value_token[0]
    if first_character not in {'"', "'"}:
        return False
    inside_quote = True
    for each_character in value_token[1:]:
        if each_character == first_character:
            inside_quote = not inside_quote
    return inside_quote


def count_extra_tokens_to_skip_for_split_quoted_value(
    remaining_tokens: list[str],
    value_token: str,
) -> int | None:
    if not _quoted_value_starts_split(value_token):
        return 0
    opening_quote = value_token[0]
    extra_tokens_consumed = 0
    for each_remaining_token in remaining_tokens:
        extra_tokens_consumed += 1
        if each_remaining_token.count(opening_quote) % 2 == 1:
            return extra_tokens_consumed
    return None


def iter_significant_tokens(
    command: str,
    pre_tokenized: tuple[str, list[str]] | None = None,
) -> Iterator[tuple[str, list[str]]]:
    """Yield (token, remaining_tokens) for every flag/positional after continuation join.

    Joins bash/PowerShell continuations, tokenizes with shlex.split(posix=False),
    then yields each flag and positional along with the remaining tokens. Values
    of value-taking flags (including quoted values split across multiple
    posix=False tokens) are SKIPPED from yield so that --body embedded in a
    quoted --title value is never seen as a standalone flag. Equals-form value
    flags whose quoted value may span multiple posix=False tokens are yielded
    as-is and any trailing split-quote continuation tokens are skipped. A
    value-taking flag whose next token is itself flag-shaped is treated as
    value-missing: the flag is yielded but the flag-shaped follower is NOT
    skipped (so a malformed --body-file --body "x" still yields --body).

    When count_extra_tokens_to_skip_for_split_quoted_value returns None (opening
    quote never closed among remaining tokens), raises ValueError so callers can
    conservatively block -- the token stream is irrecoverably malformed.

    If pre_tokenized is provided as (logical_line, raw_tokens), reuses those
    instead of recomputing from command. The command argument is still required
    for the public signature but is unused when pre_tokenized is given.

    Raises ValueError if the logical line is unparseable by shlex, or if an
    unclosed quoted value is detected in a value-taking flag.
    """
    if pre_tokenized is not None:
        logical_line, all_tokens = pre_tokenized
    else:
        logical_line = get_logical_first_line(command)
        if not logical_line:
            return
        all_tokens = shlex.split(logical_line, posix=False)
    token_index = 0
    while token_index < len(all_tokens):
        current_token = all_tokens[token_index]
        remaining_tokens = all_tokens[token_index + 1:]
        matched_equals_prefix = _match_prefix(current_token, _all_equals_prefixes_for_skip)
        if matched_equals_prefix is not None:
            value_token = current_token[len(matched_equals_prefix):]
            split_value_extra_tokens = count_extra_tokens_to_skip_for_split_quoted_value(
                remaining_tokens,
                value_token,
            )
            if split_value_extra_tokens is None:
                raise ValueError("unclosed quoted value in equals-form flag")
            yield current_token, remaining_tokens
            token_index += 1 + split_value_extra_tokens
            continue
        if current_token in all_value_flags:
            if not remaining_tokens or _is_flag_shaped(remaining_tokens[0]):
                yield current_token, remaining_tokens
                token_index += 1
                continue
            value_token = remaining_tokens[0]
            split_value_extra_tokens = count_extra_tokens_to_skip_for_split_quoted_value(
                remaining_tokens[1:],
                value_token,
            )
            if split_value_extra_tokens is None:
                raise ValueError("unclosed quoted value in space-form flag")
            yield current_token, remaining_tokens[1 + split_value_extra_tokens:]
            token_index += 1 + 1 + split_value_extra_tokens
            continue
        yield current_token, remaining_tokens
        token_index += 1
