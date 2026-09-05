"""Extract durable GitHub post body text for privacy checks."""

from __future__ import annotations

import shlex
from pathlib import Path

from blocking._gh_body_arg_utils import (
    all_body_flags,
    body_file_flag,
    body_file_short_flag,
    count_extra_tokens_to_skip_for_split_quoted_value,
    get_logical_first_line,
    is_unresolvable_shell_value,
    match_body_file_equals_prefix,
    match_body_flag_equals_prefix,
    strip_surrounding_quotes,
)
from hooks_constants.gh_post_body_texts_constants import (
    ALL_GH_POST_SUBCOMMANDS,
    ALL_MCP_BODY_PARAM_NAMES,
    BODY_FILE_ENCODING,
    BODY_FLAG_WITH_VALUE_STEP,
    GH_COMMAND_NAME,
    MINIMUM_POST_SUBCOMMAND_TOKEN_COUNT,
    TOKEN_JOIN_SEPARATOR,
)


def _is_environment_assignment(token: str) -> bool:
    equals_index = token.find("=")
    if equals_index <= 0:
        return False
    name_part = token[:equals_index]
    if not (name_part[0].isalpha() or name_part[0] == "_"):
        return False
    return all(each_character.isalnum() or each_character == "_" for each_character in name_part)


def _tokens_name_gh_post_command(all_command_tokens: list[str]) -> bool:
    command_index = 0
    while command_index < len(all_command_tokens) and _is_environment_assignment(
        all_command_tokens[command_index]
    ):
        command_index += 1
    if command_index >= len(all_command_tokens):
        return False
    if all_command_tokens[command_index] != GH_COMMAND_NAME:
        return False
    remaining_tokens = all_command_tokens[command_index + 1 :]
    if len(remaining_tokens) < MINIMUM_POST_SUBCOMMAND_TOKEN_COUNT:
        return False
    post_noun, post_verb = remaining_tokens[:MINIMUM_POST_SUBCOMMAND_TOKEN_COUNT]
    return post_verb in ALL_GH_POST_SUBCOMMANDS.get(post_noun, frozenset())


def _reassemble_split_quoted_value(
    value_token: str,
    all_following_tokens: list[str],
) -> tuple[str, int]:
    extra_token_count = count_extra_tokens_to_skip_for_split_quoted_value(
        all_following_tokens, value_token
    )
    if not extra_token_count:
        return strip_surrounding_quotes(value_token), 0
    joined_value = (
        value_token
        + TOKEN_JOIN_SEPARATOR
        + TOKEN_JOIN_SEPARATOR.join(all_following_tokens[:extra_token_count])
    )
    return strip_surrounding_quotes(joined_value), extra_token_count


def _extract_flag_value_at(
    all_command_tokens: list[str],
    token_index: int,
) -> tuple[bool, str, int] | None:
    current_token = all_command_tokens[token_index]
    following_tokens = all_command_tokens[token_index + 1 :]
    body_prefix = match_body_flag_equals_prefix(current_token)
    if body_prefix is not None:
        value, extra_count = _reassemble_split_quoted_value(
            current_token[len(body_prefix) :], following_tokens
        )
        return False, value, token_index + 1 + extra_count
    body_file_prefix = match_body_file_equals_prefix(current_token)
    if body_file_prefix is not None:
        value, extra_count = _reassemble_split_quoted_value(
            current_token[len(body_file_prefix) :], following_tokens
        )
        return True, value, token_index + 1 + extra_count
    if current_token in all_body_flags and following_tokens:
        value, extra_count = _reassemble_split_quoted_value(
            following_tokens[0], following_tokens[1:]
        )
        return False, value, token_index + BODY_FLAG_WITH_VALUE_STEP + extra_count
    if current_token in (body_file_flag, body_file_short_flag) and following_tokens:
        value, extra_count = _reassemble_split_quoted_value(
            following_tokens[0], following_tokens[1:]
        )
        return True, value, token_index + BODY_FLAG_WITH_VALUE_STEP + extra_count
    return None


def _collect_body_flag_values(
    all_command_tokens: list[str],
) -> tuple[list[str], list[str]]:
    all_inline_bodies: list[str] = []
    all_body_file_paths: list[str] = []
    token_index = 0
    while token_index < len(all_command_tokens):
        extraction = _extract_flag_value_at(all_command_tokens, token_index)
        if extraction is None:
            token_index += 1
            continue
        is_body_file, value, token_index = extraction
        if is_body_file:
            all_body_file_paths.append(value)
        else:
            all_inline_bodies.append(value)
    return all_inline_bodies, all_body_file_paths


def _read_body_file(
    body_file_path: str,
    working_directory: str | None,
) -> str | None:
    if is_unresolvable_shell_value(body_file_path):
        return None
    resolved_path = Path(body_file_path)
    if not resolved_path.is_absolute() and working_directory:
        resolved_path = Path(working_directory) / body_file_path
    try:
        return resolved_path.read_text(encoding=BODY_FILE_ENCODING)
    except (OSError, UnicodeError):
        return None


def _body_texts_from_tokens(
    all_command_tokens: list[str],
    working_directory: str | None,
) -> tuple[list[str], str | None]:
    if not _tokens_name_gh_post_command(all_command_tokens):
        return [], None
    all_body_texts, all_body_file_paths = _collect_body_flag_values(all_command_tokens)
    for each_path in all_body_file_paths:
        file_text = _read_body_file(each_path, working_directory)
        if file_text is None:
            return [], (
                "BLOCKED [pii_prevention_blocker]: durable post uses --body-file "
                f"but '{each_path}' could not be read for PII scanning. Use an "
                "absolute path, ensure the file exists, or pass --body text."
            )
        all_body_texts.append(file_text)
    return all_body_texts, None


def extract_gh_post_body_texts_for_privacy_gate(
    command: str,
    working_directory: str | None = None,
) -> tuple[list[str], str | None]:
    """Extract GitHub post text and reject unreadable declared body files.

    Args:
        command: Raw GitHub CLI command.
        working_directory: Base directory for relative body-file paths.

    Returns:
        Body texts and no error, or no texts and a safe rejection message.
    """
    logical_line = get_logical_first_line(command)
    if not logical_line:
        return [], None
    try:
        all_command_tokens = shlex.split(logical_line, posix=False)
    except ValueError:
        return [], None
    return _body_texts_from_tokens(all_command_tokens, working_directory)


def extract_mcp_body_texts(all_tool_input: dict[str, object]) -> list[str]:
    """Extract body and comment strings from a GitHub tool request.

    Args:
        all_tool_input: GitHub tool input mapping.

    Returns:
        Nonempty body and comment values.
    """
    all_body_texts: list[str] = []
    for each_name in ALL_MCP_BODY_PARAM_NAMES:
        candidate_text = all_tool_input.get(each_name)
        if isinstance(candidate_text, str) and candidate_text:
            all_body_texts.append(candidate_text)
    return all_body_texts
