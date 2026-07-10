#!/usr/bin/env python3
"""PreToolUse hook: block writes, durable posts, and commits that carry PII.

Surfaces guarded:

- Write / Edit / MultiEdit — new content about to land on disk
- Bash / PowerShell ``gh`` post subcommands and GitHub MCP post tools — durable
  bodies
- Bash / PowerShell ``git commit`` (including ``git.exe`` and flag forms) —
  staged file contents about to become history. Commit message bodies are out
  of scope; only staged blob text is scanned.

Detection reuses the pure scanners in ``pii_scanner`` and the post-body
extraction helpers already used by ``volatile_path_in_post_blocker``.
"""

from __future__ import annotations

import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from block_main_commit import (  # noqa: E402
    extract_git_working_directory,
    resolve_directory,
)
from pii_scanner import PiiFinding, is_path_exempt_from_pii_scan, scan_text_for_pii  # noqa: E402
from precommit_code_rules_gate import (  # noqa: E402
    resolve_repository_root,
)
from volatile_path_in_post_blocker import (  # noqa: E402
    extract_gh_post_body_texts_for_privacy_gate,
    extract_mcp_body_texts,
)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.multi_edit_reconstruction import edits_for_tool  # noqa: E402
from hooks_constants.pii_prevention_constants import (  # noqa: E402
    ALL_COMMAND_BOUNDARY_NEWLINE_CHARACTERS,
    ALL_GIT_BINARY_BASENAMES,
    ALL_LEADING_SKIPPABLE_COMMAND_TOKENS,
    ALL_SHELL_COMMAND_SEPARATOR_TOKENS,
    ALL_SHELL_INTERPRETER_BASENAMES,
    ALL_SHELL_QUOTE_CHARACTERS,
    ALL_SHELL_TOOL_NAMES,
    ALL_STAGED_BLOB_SHOW_COMMAND_PREFIX,
    ALL_STAGED_FILES_COMMAND,
    ALL_VALUE_TAKING_GIT_OPTIONS,
    ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES,
    BODY_FILE_ENCODING,
    CORRECTIVE_MESSAGE_FOOTER,
    CORRECTIVE_MESSAGE_HEADER,
    DOUBLE_DASH_OPTION_PREFIX,
    EDIT_TOOL_NAME,
    ENVIRONMENT_ASSIGNMENT_PATTERN,
    FINDING_LINE_TEMPLATE,
    GIT_COMMAND_TIMEOUT_SECONDS,
    GIT_COMMIT_SUBCOMMAND,
    GIT_OPTION_WITH_VALUE_STEP,
    HOOK_SCRIPT_BASENAME,
    INLINE_COMMAND_FLAG_CLUSTER_SUFFIX,
    LINE_CONTINUATION_PATTERN,
    MAXIMUM_STAGED_FILE_BYTES,
    MCP_GITHUB_TOOL_PREFIX,
    MESSAGE_LINE_SEPARATOR,
    MULTI_EDIT_TOOL_NAME,
    NULL_BYTE_MARKER,
    OPTION_ATTACHED_VALUE_MARKER,
    POWERSHELL_CALL_OPERATOR,
    POWERSHELL_INLINE_COMMAND_FLAG,
    REPOSITORY_ROOT_UNRESOLVED_REASON,
    SHELL_INLINE_COMMAND_FLAG,
    SINGLE_DASH_OPTION_PREFIX,
    STAGED_BLOB_PREFIX,
    STAGED_BLOB_REASON_DECODE_FAILED,
    STAGED_BLOB_REASON_GIT_SHOW_FAILED,
    STAGED_BLOB_REASON_NULL_BYTES,
    STAGED_BLOB_REASON_OVERSIZED,
    STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE,
    STAGED_LIST_FAILURE_REASON,
    WRITE_TOOL_NAME,
)
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)


def build_deny_reason(all_findings: list[PiiFinding], gate_surface: str) -> str:
    """Return the deny message listing each finding for *gate_surface*.

    Args:
        all_findings: Findings returned by ``scan_text_for_pii``.
        gate_surface: Human-readable surface (write, post body, staged commit).

    Returns:
        Multi-line deny reason for ``permissionDecisionReason``.
    """
    all_lines = [
        CORRECTIVE_MESSAGE_HEADER,
        f"Surface: {gate_surface}",
    ]
    for each_finding in all_findings:
        all_lines.append(
            FINDING_LINE_TEMPLATE.format(
                category=each_finding.category,
                preview=each_finding.preview,
            )
        )
    all_lines.append(CORRECTIVE_MESSAGE_FOOTER)
    message_line_separator = MESSAGE_LINE_SEPARATOR
    return message_line_separator.join(all_lines)


def _collect_write_edit_texts(
    tool_name: str, all_tool_input: dict[str, object]
) -> tuple[str, list[str]]:
    raw_file_path = all_tool_input.get("file_path", "")
    file_path = raw_file_path if isinstance(raw_file_path, str) else ""
    if is_path_exempt_from_pii_scan(file_path):
        return file_path, []
    if tool_name == WRITE_TOOL_NAME:
        write_content = all_tool_input.get("content", "")
        if isinstance(write_content, str) and write_content:
            return file_path, [write_content]
        return file_path, []
    if tool_name in (EDIT_TOOL_NAME, MULTI_EDIT_TOOL_NAME):
        all_texts: list[str] = []
        for each_edit in edits_for_tool(tool_name, all_tool_input):
            if not isinstance(each_edit, dict):
                continue
            new_string = each_edit.get("new_string", "")
            if isinstance(new_string, str) and new_string:
                all_texts.append(new_string)
        return file_path, all_texts
    return file_path, []


def _first_findings_in_texts(all_texts: list[str]) -> list[PiiFinding]:
    for each_text in all_texts:
        all_findings = scan_text_for_pii(each_text)
        if all_findings:
            return all_findings
    return []


def evaluate_write_edit_payload(
    tool_name: str, all_tool_input: dict[str, object]
) -> str | None:
    """Return a deny reason when Write/Edit/MultiEdit content carries PII.

    Args:
        tool_name: The intercepted tool name.
        all_tool_input: The tool input mapping.

    Returns:
        Deny reason text, or None when the write is clean or out of scope.
    """
    if tool_name not in ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES:
        return None
    file_path, all_texts = _collect_write_edit_texts(tool_name, all_tool_input)
    all_findings = _first_findings_in_texts(all_texts)
    if not all_findings:
        return None
    gate_surface = f"file write ({file_path or 'unknown path'})"
    return build_deny_reason(all_findings, gate_surface)


def evaluate_post_body_texts(all_body_texts: list[str]) -> str | None:
    """Return a deny reason when any durable post body carries PII.

    Args:
        all_body_texts: Body strings extracted from a gh or MCP post tool.

    Returns:
        Deny reason text, or None when every body is clean.
    """
    all_findings = _first_findings_in_texts(all_body_texts)
    if not all_findings:
        return None
    return build_deny_reason(all_findings, "durable GitHub post body")


def list_staged_file_paths(
    repository_root: Path,
) -> tuple[list[str] | None, str | None]:
    """List staged non-deleted paths, or report a list failure.

    Args:
        repository_root: Repository root used as the git working directory.

    Returns:
        ``(paths, None)`` on success, or ``(None, deny_reason)`` when the
        staged list cannot be read (fail-closed for commit gating).
    """
    try:
        completed_process = subprocess.run(
            list(ALL_STAGED_FILES_COMMAND),
            capture_output=True,
            text=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=str(repository_root),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None, STAGED_LIST_FAILURE_REASON
    if completed_process.returncode != 0:
        return None, STAGED_LIST_FAILURE_REASON
    all_paths = [
        each_line.strip()
        for each_line in completed_process.stdout.splitlines()
        if each_line.strip()
    ]
    return all_paths, None


def read_staged_file_text(
    repository_root: Path, relative_path: str
) -> tuple[str | None, str | None]:
    """Return staged blob text, or report why the blob is unscannable.

    Args:
        repository_root: Repository root for the git show working directory.
        relative_path: Repository-relative path of the staged file.

    Returns:
        ``(text, None)`` when the blob is scannable UTF-8 text, or
        ``(None, deny_reason)`` when the blob cannot be scanned (fail-closed).
    """
    staged_blob_reference = STAGED_BLOB_PREFIX + relative_path
    try:
        completed_process = subprocess.run(
            list(ALL_STAGED_BLOB_SHOW_COMMAND_PREFIX) + [staged_blob_reference],
            capture_output=True,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
            cwd=str(repository_root),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None, STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE.format(
            relative_path=relative_path,
            reason=STAGED_BLOB_REASON_GIT_SHOW_FAILED,
        )
    if completed_process.returncode != 0:
        return None, STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE.format(
            relative_path=relative_path,
            reason=STAGED_BLOB_REASON_GIT_SHOW_FAILED,
        )
    raw_bytes = completed_process.stdout
    if len(raw_bytes) > MAXIMUM_STAGED_FILE_BYTES:
        return None, STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE.format(
            relative_path=relative_path,
            reason=STAGED_BLOB_REASON_OVERSIZED,
        )
    if NULL_BYTE_MARKER in raw_bytes:
        return None, STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE.format(
            relative_path=relative_path,
            reason=STAGED_BLOB_REASON_NULL_BYTES,
        )
    try:
        return raw_bytes.decode(BODY_FILE_ENCODING), None
    except UnicodeDecodeError:
        return None, STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE.format(
            relative_path=relative_path,
            reason=STAGED_BLOB_REASON_DECODE_FAILED,
        )


def evaluate_staged_commit(
    repository_root: Path,
) -> str | None:
    """Return a deny reason when staged content carries PII or is unscannable.

    Fail-closed: git list/show failures and unscannable blobs deny the commit
    rather than treating unread content as clean.

    Args:
        repository_root: Repository whose index is about to be committed.

    Returns:
        Deny reason text, or None when every scannable staged path is clean.
    """
    all_relative_paths, list_failure_reason = list_staged_file_paths(repository_root)
    if list_failure_reason is not None or all_relative_paths is None:
        return list_failure_reason or STAGED_LIST_FAILURE_REASON
    for each_relative_path in all_relative_paths:
        if is_path_exempt_from_pii_scan(each_relative_path):
            continue
        staged_text, unscannable_reason = read_staged_file_text(
            repository_root, each_relative_path
        )
        if unscannable_reason is not None:
            return unscannable_reason
        if staged_text is None:
            return STAGED_BLOB_UNSCANNABLE_REASON_TEMPLATE.format(
                relative_path=each_relative_path,
                reason=STAGED_BLOB_REASON_GIT_SHOW_FAILED,
            )
        all_findings = scan_text_for_pii(staged_text)
        if all_findings:
            gate_surface = f"staged commit ({each_relative_path})"
            return build_deny_reason(all_findings, gate_surface)
    return None


def _strip_token_edge_quotes(token_text: str) -> str:
    return token_text.strip("\"'")


def _token_basename_lower(token_text: str) -> str:
    stripped_token = _strip_token_edge_quotes(token_text)
    return re.split(r"[\\/]", stripped_token)[-1].lower()


def _token_is_git_binary(token_text: str) -> bool:
    return _token_basename_lower(token_text) in ALL_GIT_BINARY_BASENAMES


def _token_is_shell_interpreter(token_text: str) -> bool:
    return _token_basename_lower(token_text) in ALL_SHELL_INTERPRETER_BASENAMES


def _token_is_skippable_prefix(token_text: str) -> bool:
    if ENVIRONMENT_ASSIGNMENT_PATTERN.match(token_text):
        return True
    if token_text == POWERSHELL_CALL_OPERATOR:
        return True
    return _token_basename_lower(token_text) in ALL_LEADING_SKIPPABLE_COMMAND_TOKENS


def _following_tokens_invoke_commit(all_following_tokens: list[str]) -> bool:
    token_index = 0
    option_with_value_step = GIT_OPTION_WITH_VALUE_STEP
    while token_index < len(all_following_tokens):
        each_token = _strip_token_edge_quotes(all_following_tokens[token_index])
        option_name = each_token
        has_attached_value = False
        if each_token.startswith("--") and "=" in each_token:
            option_name, _, _attached_value = each_token.partition("=")
            has_attached_value = True
        if option_name in ALL_VALUE_TAKING_GIT_OPTIONS:
            if has_attached_value:
                token_index += 1
            else:
                token_index += option_with_value_step
            continue
        if each_token.startswith("-"):
            token_index += 1
            continue
        return each_token.lower() == GIT_COMMIT_SUBCOMMAND
    return False


def _split_shell_command_segments(all_tokens: list[str]) -> list[list[str]]:
    all_segments: list[list[str]] = [[]]
    shell_separators = ALL_SHELL_COMMAND_SEPARATOR_TOKENS
    for each_token in all_tokens:
        if each_token in shell_separators:
            all_segments.append([])
            continue
        all_segments[-1].append(each_token)
    return all_segments


def _tokenize_shell_command(shell_command_piece: str) -> list[str]:
    lexer = shlex.shlex(shell_command_piece, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.escape = ""
    try:
        return list(lexer)
    except ValueError:
        return shell_command_piece.split()


def _split_on_unquoted_newlines(shell_command: str) -> list[str]:
    all_pieces: list[str] = []
    current_characters: list[str] = []
    active_quote_character = ""
    for each_character in shell_command:
        if active_quote_character:
            if each_character == active_quote_character:
                active_quote_character = ""
            current_characters.append(each_character)
            continue
        if each_character in ALL_SHELL_QUOTE_CHARACTERS:
            active_quote_character = each_character
            current_characters.append(each_character)
            continue
        if each_character in ALL_COMMAND_BOUNDARY_NEWLINE_CHARACTERS:
            all_pieces.append("".join(current_characters))
            current_characters = []
            continue
        current_characters.append(each_character)
    all_pieces.append("".join(current_characters))
    return all_pieces


def _all_command_segments(shell_command: str) -> list[list[str]]:
    collapsed_command = LINE_CONTINUATION_PATTERN.sub("", shell_command)
    all_segments: list[list[str]] = []
    for each_piece in _split_on_unquoted_newlines(collapsed_command):
        piece_tokens = _tokenize_shell_command(each_piece)
        all_segments.extend(_split_shell_command_segments(piece_tokens))
    return all_segments


def _token_is_command_option(token_text: str) -> bool:
    stripped_token = _strip_token_edge_quotes(token_text)
    return stripped_token.startswith(SINGLE_DASH_OPTION_PREFIX)


def _wrapper_option_consumes_next_value(
    option_token: str, all_segment_tokens: list[str], value_index: int
) -> bool:
    if value_index >= len(all_segment_tokens):
        return False
    stripped_option = _strip_token_edge_quotes(option_token)
    if stripped_option.startswith(DOUBLE_DASH_OPTION_PREFIX):
        return False
    if OPTION_ATTACHED_VALUE_MARKER in stripped_option:
        return False
    value_token = all_segment_tokens[value_index]
    if _token_is_command_option(value_token):
        return False
    if _token_is_git_binary(value_token):
        return False
    return not _token_is_shell_interpreter(value_token)


def _skip_leading_noop_tokens(all_segment_tokens: list[str]) -> int:
    token_index = 0
    has_skipped_prefix = False
    while token_index < len(all_segment_tokens):
        each_token = all_segment_tokens[token_index]
        if _token_is_skippable_prefix(each_token):
            has_skipped_prefix = True
            token_index += 1
            continue
        if not (has_skipped_prefix and _token_is_command_option(each_token)):
            break
        token_index += 1
        if _wrapper_option_consumes_next_value(
            each_token, all_segment_tokens, token_index
        ):
            token_index += 1
    return token_index


def _token_is_powershell_command_flag_prefix(lowered_token: str) -> bool:
    if lowered_token == SINGLE_DASH_OPTION_PREFIX:
        return False
    return POWERSHELL_INLINE_COMMAND_FLAG.startswith(lowered_token)


def _token_is_interpreter_inline_command_flag(token_text: str) -> bool:
    if not token_text.startswith(SINGLE_DASH_OPTION_PREFIX):
        return False
    if token_text.startswith(DOUBLE_DASH_OPTION_PREFIX):
        return False
    lowered_token = token_text.lower()
    if lowered_token == SHELL_INLINE_COMMAND_FLAG:
        return True
    if _token_is_powershell_command_flag_prefix(lowered_token):
        return True
    return lowered_token.endswith(INLINE_COMMAND_FLAG_CLUSTER_SUFFIX)


def _interpreter_inline_command_invokes_commit(
    all_following_tokens: list[str],
) -> bool:
    token_index = 0
    while token_index < len(all_following_tokens):
        each_token = all_following_tokens[token_index]
        if _token_is_interpreter_inline_command_flag(each_token):
            argument_index = token_index + 1
            if argument_index >= len(all_following_tokens):
                return False
            return is_git_commit_shell_command(all_following_tokens[argument_index])
        token_index += 1
    return False


def _segment_invokes_git_commit(all_segment_tokens: list[str]) -> bool:
    command_index = _skip_leading_noop_tokens(all_segment_tokens)
    if command_index >= len(all_segment_tokens):
        return False
    all_following_tokens = all_segment_tokens[command_index + 1 :]
    if _token_is_shell_interpreter(all_segment_tokens[command_index]):
        return _interpreter_inline_command_invokes_commit(all_following_tokens)
    if not _token_is_git_binary(all_segment_tokens[command_index]):
        return False
    return _following_tokens_invoke_commit(all_following_tokens)


def is_git_commit_shell_command(shell_command: str) -> bool:
    """Report whether *shell_command* invokes git commit (token-aware).

    Each segment is read past its leading noise to the real command word::

        sudo git commit -m x        ->  skip the wrapper, then match commit
        nice -n 10 git commit       ->  skip the wrapper and its flag value
        then git commit -m x        ->  skip the keyword, then match commit
        bash -lc "git commit"       ->  unwrap the combined inline flag
        pwsh -Command "git commit"  ->  unwrap the PowerShell inline argument

    Skipped leading tokens: env-assignments, a PowerShell call operator, shell
    keywords (then, do, else, elif), and wrapper commands (sudo, env, time,
    nice, xargs, command, stdbuf) together with each wrapper's own option
    flags and their values. Segments split on unquoted control separators and
    newlines, and the git binary may be path-prefixed and carry global flags
    (no-verify, config, and working-directory) before its subcommand. A shell
    interpreter (bash, sh, pwsh, powershell) is unwrapped at its inline-command
    flag: bash and sh take an isolated ``-c`` or a combined cluster (``-lc``),
    and PowerShell takes ``-Command`` or ``-c``.

    Args:
        shell_command: Bash or PowerShell tool command string.

    Returns:
        True when a command segment invokes git with a commit subcommand.
    """
    if not shell_command or not shell_command.strip():
        return False
    for each_segment in _all_command_segments(shell_command):
        if _segment_invokes_git_commit(each_segment):
            return True
    return False


def evaluate_bash_command(
    bash_command: str, working_directory: str | None
) -> str | None:
    """Return a deny reason for a shell gh post or git commit with PII.

    Args:
        bash_command: The Bash or PowerShell tool command string.
        working_directory: Directory git should run in, or None for process CWD.

    Returns:
        Deny reason text, or None when the command is clean or out of scope.
    """
    all_post_bodies, body_file_failure_reason = (
        extract_gh_post_body_texts_for_privacy_gate(
            bash_command, working_directory=working_directory
        )
    )
    if body_file_failure_reason is not None:
        return body_file_failure_reason
    post_deny_reason = evaluate_post_body_texts(all_post_bodies)
    if post_deny_reason is not None:
        return post_deny_reason
    if not is_git_commit_shell_command(bash_command):
        return None
    command_directory = extract_git_working_directory(bash_command)
    resolved_directory = resolve_directory(command_directory) or working_directory
    repository_root = resolve_repository_root(resolved_directory)
    if repository_root is None:
        return REPOSITORY_ROOT_UNRESOLVED_REASON
    return evaluate_staged_commit(repository_root)


def evaluate(payload_by_key: dict[str, object]) -> str | None:
    """Decide whether a PreToolUse payload carries high-confidence PII.

    Args:
        payload_by_key: The PreToolUse payload with tool_name and tool_input.

    Returns:
        Deny-reason text when blocked, or None when allowed.
    """
    raw_tool_name = payload_by_key.get("tool_name", "")
    tool_name = raw_tool_name if isinstance(raw_tool_name, str) else ""
    raw_tool_input = payload_by_key.get("tool_input", {})
    all_tool_input = raw_tool_input if isinstance(raw_tool_input, dict) else {}

    if tool_name in ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES:
        return evaluate_write_edit_payload(tool_name, all_tool_input)

    if tool_name in ALL_SHELL_TOOL_NAMES:
        command_value = all_tool_input.get("command", "")
        if not isinstance(command_value, str) or not command_value:
            return None
        working_directory_value = all_tool_input.get("working_directory")
        working_directory = (
            working_directory_value
            if isinstance(working_directory_value, str)
            else None
        )
        if working_directory is None:
            cwd_value = payload_by_key.get("cwd")
            working_directory = cwd_value if isinstance(cwd_value, str) else None
        return evaluate_bash_command(
            command_value, working_directory=working_directory
        )

    if tool_name.startswith(MCP_GITHUB_TOOL_PREFIX):
        return evaluate_post_body_texts(extract_mcp_body_texts(all_tool_input))

    return None


def build_deny_payload(deny_reason: str) -> dict[str, object]:
    """Build the PreToolUse deny payload for *deny_reason*.

    Args:
        deny_reason: The permissionDecisionReason text.

    Returns:
        Deny payload dictionary serialized to stdout by the hook.
    """
    log_hook_block(
        calling_hook_name=HOOK_SCRIPT_BASENAME,
        hook_event="PreToolUse",
        block_reason=deny_reason,
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        }
    }


def main() -> None:
    """Read PreToolUse stdin and deny when high-confidence PII is present."""
    payload_dictionary = read_hook_input_dictionary_from_stdin()
    if payload_dictionary is None:
        sys.exit(0)
    deny_reason = evaluate(payload_dictionary)
    if deny_reason is None:
        sys.exit(0)
    print(json.dumps(build_deny_payload(deny_reason)))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
