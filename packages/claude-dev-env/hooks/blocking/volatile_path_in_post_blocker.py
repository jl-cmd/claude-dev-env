#!/usr/bin/env python3
"""PreToolUse hook: block durable GitHub posts that reference volatile paths.

Root cause: a background job posted a PR comment citing an artifact under a job
scratch directory. Job tmp dirs, worktrees, and system temp locations are
ephemeral — they are cleaned soon after the run — while a posted comment, PR
body, issue, or review lives forever. A durable post that points at ephemeral
scratch breaks the moment that scratch is removed.

Detection strategy: gather the post body text from the tool call, then scan it
for volatile-path markers. Two tool families carry post bodies: shell ``gh``
post subcommands (``pr create/comment/edit/review``, ``issue
create/comment/edit``) and the GitHub MCP post tools (any
``mcp__plugin_github_github__*`` tool that carries a ``body`` or ``comment``
parameter). For a ``gh`` command the body comes from ``--body``/``-b`` inline
strings and from the file named by ``--body-file``/``-F`` (its contents are read
and scanned, since that content is what gets embedded in the post). The ``gh``
command is tokenized with ``shlex.split`` and the ``gh`` word must be the first
command token, so a ``gh pr comment`` that only appears as quoted data inside
another argument never classifies.
"""

import json
import shlex
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from blocking._gh_body_arg_utils import (  # noqa: E402
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
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.volatile_path_in_post_blocker_constants import (  # noqa: E402
    ALL_GH_POST_SUBCOMMANDS,
    ALL_MCP_BODY_PARAM_NAMES,
    ALL_VOLATILE_PATH_MARKERS,
    BASH_TOOL_NAME,
    BODY_FILE_ENCODING,
    CORRECTIVE_MESSAGE,
    GH_COMMAND_NAME,
    MCP_GITHUB_TOOL_PREFIX,
    MINIMUM_POST_SUBCOMMAND_TOKEN_COUNT,
    TOKEN_JOIN_SEPARATOR,
)


def scan_text_for_volatile_marker(text: str) -> str | None:
    """Return the first volatile-path marker found in text, or None.

    Backslashes normalize to forward slashes and the text lowercases before the
    scan, so a marker matches regardless of slash direction or letter case::

        ok:   "See the log table pasted below."        -> None
        flag: r"C:\\Users\\me\\.claude-editor\\jobs\\x" -> ".claude-editor/jobs/"

    Env-token markers such as ``%TEMP%`` and ``$CLAUDE_JOB_DIR`` match on the
    same lowercased text.

    Args:
        text: The post body text to scan.

    Returns:
        The matched marker string, or None when the text names no volatile path.
    """
    normalized_text = text.replace("\\", "/").lower()
    for each_marker in ALL_VOLATILE_PATH_MARKERS:
        if each_marker in normalized_text:
            return each_marker
    return None


def _is_environment_assignment(token: str) -> bool:
    """Return whether a token is a ``NAME=value`` shell environment assignment."""
    equals_index = token.find("=")
    if equals_index <= 0:
        return False
    name_part = token[:equals_index]
    if not (name_part[0].isalpha() or name_part[0] == "_"):
        return False
    return all(
        each_character.isalnum() or each_character == "_"
        for each_character in name_part
    )


def _tokens_name_gh_post_command(all_command_tokens: list[str]) -> bool:
    """Return whether the tokens start with an affected ``gh`` post subcommand.

    Leading ``NAME=value`` env assignments are skipped, then the next token must
    be the literal ``gh`` command word followed by a post noun and verb. Anchoring
    to the first command word keeps a ``gh pr comment`` mentioned only as quoted
    argument data from classifying.

    Args:
        all_command_tokens: The shlex-split tokens of the logical command line.

    Returns:
        True when the command invokes an affected ``gh`` post subcommand.
    """
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
    post_noun = remaining_tokens[0]
    post_verb = remaining_tokens[1]
    return post_verb in ALL_GH_POST_SUBCOMMANDS.get(post_noun, frozenset())


def _reassemble_split_quoted_value(
    value_token: str, all_following_tokens: list[str]
) -> tuple[str, int]:
    """Rejoin a quoted value that ``shlex.split(posix=False)`` split on spaces.

    ``posix=False`` keeps backslashes intact (so Windows paths survive) but
    splits a quoted value such as ``"dump in %TEMP%"`` into three tokens. This
    rejoins the value token with the follow-on tokens up to the closing quote,
    then strips the surrounding quotes so the full body text can be scanned.

    Args:
        value_token: The first token of the value, following the flag.
        all_following_tokens: The tokens after ``value_token`` on the line.

    Returns:
        A ``(full_value, extra_tokens_consumed)`` pair; ``extra_tokens_consumed``
        counts the follow-on tokens joined into the value.
    """
    extra_tokens = count_extra_tokens_to_skip_for_split_quoted_value(
        all_following_tokens, value_token
    )
    if not extra_tokens:
        return strip_surrounding_quotes(value_token), 0
    joined_value = value_token + TOKEN_JOIN_SEPARATOR + TOKEN_JOIN_SEPARATOR.join(
        all_following_tokens[:extra_tokens]
    )
    return strip_surrounding_quotes(joined_value), extra_tokens


def _extract_flag_value_at(
    all_command_tokens: list[str], token_index: int
) -> tuple[bool, str, int] | None:
    """Return a body/body-file value starting at token_index, or None.

    Args:
        all_command_tokens: The shlex-split tokens of the logical command line.
        token_index: The index of the token to inspect.

    Returns:
        An ``(is_body_file, value, next_index)`` triple when the token opens a
        body or body-file flag, else None. ``next_index`` is where scanning
        resumes after the value's tokens.
    """
    current_token = all_command_tokens[token_index]
    following_tokens = all_command_tokens[token_index + 1:]
    body_equals_prefix = match_body_flag_equals_prefix(current_token)
    if body_equals_prefix is not None:
        value, extra = _reassemble_split_quoted_value(
            current_token[len(body_equals_prefix):], following_tokens
        )
        return False, value, token_index + 1 + extra
    body_file_equals_prefix = match_body_file_equals_prefix(current_token)
    if body_file_equals_prefix is not None:
        value, extra = _reassemble_split_quoted_value(
            current_token[len(body_file_equals_prefix):], following_tokens
        )
        return True, value, token_index + 1 + extra
    if current_token in all_body_flags and following_tokens:
        value, extra = _reassemble_split_quoted_value(following_tokens[0], following_tokens[1:])
        return False, value, token_index + 2 + extra
    if current_token in (body_file_flag, body_file_short_flag) and following_tokens:
        value, extra = _reassemble_split_quoted_value(following_tokens[0], following_tokens[1:])
        return True, value, token_index + 2 + extra
    return None


def _collect_body_flag_values(
    all_command_tokens: list[str],
) -> tuple[list[str], list[str]]:
    """Return inline body strings and body-file paths from the command tokens.

    Args:
        all_command_tokens: The shlex-split tokens of the logical command line.

    Returns:
        A ``(all_inline_bodies, all_body_file_paths)`` pair, each value stripped
        of its surrounding quotes and rejoined across split-quote tokens.
    """
    all_inline_bodies: list[str] = []
    all_body_file_paths: list[str] = []
    token_index = 0
    while token_index < len(all_command_tokens):
        extraction = _extract_flag_value_at(all_command_tokens, token_index)
        if extraction is None:
            token_index += 1
            continue
        is_body_file, value, next_index = extraction
        if is_body_file:
            all_body_file_paths.append(value)
        else:
            all_inline_bodies.append(value)
        token_index = next_index
    return all_inline_bodies, all_body_file_paths


def _read_body_file(
    body_file_path: str, working_directory: str | None = None
) -> str | None:
    """Return the contents of a body-file path, or None when it cannot be read.

    Args:
        body_file_path: The path given to ``--body-file``/``-F``.
        working_directory: Optional base directory for relative body-file paths.

    Returns:
        The file text, or None for an unresolvable shell value (such as ``-`` for
        stdin or a ``$VAR`` path) or an unreadable file.
    """
    if is_unresolvable_shell_value(body_file_path):
        return None
    resolved_path = Path(body_file_path)
    if not resolved_path.is_absolute() and working_directory:
        resolved_path = Path(working_directory) / body_file_path
    try:
        return resolved_path.read_text(encoding=BODY_FILE_ENCODING)
    except OSError:
        return None


def extract_gh_post_body_texts(
    command: str, working_directory: str | None = None
) -> list[str]:
    """Return every post body text an affected ``gh`` command would send.

    Non-post ``gh`` commands and unparseable command lines yield an empty list.
    Body-file contents are read from disk so the embedded text is scanned rather
    than the file path. Relative body-file paths resolve against
    *working_directory* when provided.

    Args:
        command: The raw Bash tool command string.
        working_directory: Optional base directory for relative body-file paths.

    Returns:
        Inline ``--body`` strings plus the contents of each readable body-file.
    """
    logical_line = get_logical_first_line(command)
    if not logical_line:
        return []
    try:
        all_command_tokens = shlex.split(logical_line, posix=False)
    except ValueError:
        return []
    if not _tokens_name_gh_post_command(all_command_tokens):
        return []
    all_inline_bodies, all_body_file_paths = _collect_body_flag_values(
        all_command_tokens
    )
    all_body_texts = list(all_inline_bodies)
    for each_path in all_body_file_paths:
        file_text = _read_body_file(each_path, working_directory=working_directory)
        if file_text is not None:
            all_body_texts.append(file_text)
    return all_body_texts


def extract_gh_post_body_texts_for_privacy_gate(
    command: str, working_directory: str | None = None
) -> tuple[list[str], str | None]:
    """Like ``extract_gh_post_body_texts``, but fail-closed on unreadable body-files.

    Args:
        command: The raw Bash tool command string.
        working_directory: Optional base directory for relative body-file paths.

    Returns:
        ``(all_body_texts, None)`` when every declared body-file was read (or
        none were declared), else ``([], deny_reason)`` when a body-file flag is
        present but its contents could not be loaded for scanning.
    """
    logical_line = get_logical_first_line(command)
    if not logical_line:
        return [], None
    try:
        all_command_tokens = shlex.split(logical_line, posix=False)
    except ValueError:
        return [], None
    if not _tokens_name_gh_post_command(all_command_tokens):
        return [], None
    all_inline_bodies, all_body_file_paths = _collect_body_flag_values(
        all_command_tokens
    )
    all_body_texts = list(all_inline_bodies)
    for each_path in all_body_file_paths:
        file_text = _read_body_file(each_path, working_directory=working_directory)
        if file_text is None:
            return [], (
                "BLOCKED [pii_prevention_blocker]: durable post uses --body-file "
                f"but '{each_path}' could not be read for PII scanning. Use an "
                "absolute path, ensure the file exists, or pass --body text."
            )
        all_body_texts.append(file_text)
    return all_body_texts, None


def extract_mcp_body_texts(all_tool_input: dict[str, object]) -> list[str]:
    """Return the body and comment strings from a GitHub MCP post tool input.

    Args:
        all_tool_input: The MCP tool's input mapping.

    Returns:
        The non-empty string values of the ``body`` and ``comment`` parameters.
    """
    all_body_texts: list[str] = []
    for each_param_name in ALL_MCP_BODY_PARAM_NAMES:
        param_value = all_tool_input.get(each_param_name)
        if isinstance(param_value, str) and param_value:
            all_body_texts.append(param_value)
    return all_body_texts


def _collect_body_texts(tool_name: str, all_tool_input: dict[str, object]) -> list[str]:
    if tool_name == BASH_TOOL_NAME:
        command = all_tool_input.get("command", "")
        if not isinstance(command, str) or not command:
            return []
        return extract_gh_post_body_texts(command)
    if tool_name.startswith(MCP_GITHUB_TOOL_PREFIX):
        return extract_mcp_body_texts(all_tool_input)
    return []


def _first_volatile_marker(all_body_texts: list[str]) -> str | None:
    for each_text in all_body_texts:
        matched_marker = scan_text_for_volatile_marker(each_text)
        if matched_marker is not None:
            return matched_marker
    return None


def _emit_block(tool_name: str, matched_marker: str) -> None:
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": CORRECTIVE_MESSAGE,
        }
    }
    log_hook_block(
        calling_hook_name="volatile_path_in_post_blocker.py",
        hook_event="PreToolUse",
        block_reason=CORRECTIVE_MESSAGE,
        tool_name=tool_name,
        offending_input_preview=matched_marker,
    )
    print(json.dumps(deny_payload))
    sys.stdout.flush()


def main() -> None:
    """Read the PreToolUse payload and block a post that names a volatile path."""
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    if not isinstance(tool_name, str) or not isinstance(tool_input, dict):
        sys.exit(0)

    all_body_texts = _collect_body_texts(tool_name, tool_input)
    matched_marker = _first_volatile_marker(all_body_texts)
    if matched_marker is None:
        sys.exit(0)

    _emit_block(tool_name, matched_marker)
    sys.exit(0)


if __name__ == "__main__":
    main()
