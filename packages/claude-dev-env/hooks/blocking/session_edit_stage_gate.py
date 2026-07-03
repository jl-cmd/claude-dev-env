#!/usr/bin/env python3
"""PreToolUse hook: gate a git commit on staged session-edited files.

You edit three files, stage two, and run `git commit` — the third was tracked
but never staged, so the commit leaves it behind and you notice only later. This
hook catches that at commit time. It reads the per-session tracker written by
``session_file_edit_tracker`` and denies the commit when a file this session
edited is tracked yet still unstaged, naming each file and the exact way to
include it.

Deliberate partial commits still pass: a ``-a``/``--all`` commit, a pathspec
commit, and a ``# partial-commit`` marker each pass through untouched. A
``--amend`` does not — an amend drops unstaged edits just as a plain commit does.
A missing tracker file or any git failure allows the commit, so the gate never
blocks on infrastructure trouble.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

_blocking_dir = str(Path(__file__).resolve().parent)
if _blocking_dir not in sys.path:
    sys.path.insert(0, _blocking_dir)
_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from block_main_commit import (  # noqa: E402
    extract_git_working_directory,
    resolve_directory,
)
from precommit_code_rules_gate import (  # noqa: E402
    is_git_commit_invocation,
    resolve_repository_root,
)

from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.pre_tool_use_stdin import (  # noqa: E402
    read_hook_input_dictionary_from_stdin,
)
from hooks_constants.session_edit_stage_gate_constants import (  # noqa: E402
    ALL_COMMAND_SEPARATOR_TOKENS,
    ALL_COMMIT_ALL_FLAGS,
    ALL_COMMIT_VALUE_OPTION_TOKENS,
    ALL_EDITED_FILE_PATHS_KEY,
    ALL_TRACKED_UNSTAGED_FILES_COMMAND,
    COMMIT_ALL_SHORT_FLAG_LETTER,
    COMMIT_SUBCOMMAND_TOKEN,
    DENY_FILE_BULLET_PREFIX,
    GIT_DIFF_OUTPUT_ENCODING,
    GIT_DIFF_TIMEOUT_SECONDS,
    LONG_FLAG_PREFIX,
    PARTIAL_COMMIT_BYPASS_MARKER,
    SESSION_EDIT_DENY_TEMPLATE,
    SESSION_EDIT_FILE_PREFIX,
    SESSION_EDIT_FILE_SUFFIX,
    SESSION_ID_UNSAFE_CHARACTERS_PATTERN,
    SHORT_FLAG_PREFIX,
    STATE_FILE_DEFAULT_SESSION_ID,
)


def _commit_argument_tokens(bash_command: str) -> list[str]:
    """Return the tokens that follow ``commit`` up to the next command separator.

    Args:
        bash_command: The Bash tool command string.

    Returns:
        The argument tokens of the git commit invocation. Empty when the
        command cannot be tokenized or holds no ``commit`` token.
    """
    try:
        all_tokens = shlex.split(bash_command, posix=True)
    except ValueError:
        return []
    if COMMIT_SUBCOMMAND_TOKEN not in all_tokens:
        return []
    commit_index = all_tokens.index(COMMIT_SUBCOMMAND_TOKEN)
    argument_tokens: list[str] = []
    for each_token in all_tokens[commit_index + 1 :]:
        if each_token in ALL_COMMAND_SEPARATOR_TOKENS:
            break
        argument_tokens.append(each_token)
    return argument_tokens


def _is_all_flag_token(token: str) -> bool:
    """Return whether *token* is a ``-a``/``--all`` flag or a cluster holding ``a``.

    Args:
        token: One argument token of a git commit invocation.

    Returns:
        True for ``-a``, ``--all``, or a combined short cluster such as
        ``-am`` that carries the ``a`` letter; False otherwise.
    """
    if token in ALL_COMMIT_ALL_FLAGS:
        return True
    if token.startswith(LONG_FLAG_PREFIX):
        return False
    if not token.startswith(SHORT_FLAG_PREFIX):
        return False
    return COMMIT_ALL_SHORT_FLAG_LETTER in token[1:]


def _has_trailing_bypass_comment(bash_command: str) -> bool:
    """Return whether the command carries the bypass marker as a real comment.

    The ``# partial-commit`` marker opts out only as a trailing shell comment
    the author adds on purpose, so its ``#`` and ``partial-commit`` parts sit
    as adjacent unquoted tokens. The same text inside a quoted commit message
    (``git commit -m "fix # partial-commit"``) tokenizes into one quoted token,
    so it does not match and the gate still runs.

    Args:
        bash_command: The Bash tool command string.

    Returns:
        True when the marker appears as a trailing shell comment; False when
        it appears only inside a quoted argument or the command will not
        tokenize.
    """
    marker_tokens = PARTIAL_COMMIT_BYPASS_MARKER.split()
    try:
        all_tokens = shlex.split(bash_command, posix=True)
    except ValueError:
        return False
    marker_length = len(marker_tokens)
    for each_start_index in range(len(all_tokens) - marker_length + 1):
        if all_tokens[each_start_index : each_start_index + marker_length] == marker_tokens:
            return True
    return False


def _commit_bypasses_stage_check(bash_command: str) -> bool:
    """Return whether the commit intentionally opts out of the stage check.

    A ``# partial-commit`` trailing comment, a ``-a``/``--all`` flag, and a
    pathspec argument (a ``--`` separator or a bare positional path) each mark
    a deliberate partial commit that the gate leaves alone.

    Args:
        bash_command: The Bash tool command string.

    Returns:
        True when the commit opts out of the stage check; False otherwise.
    """
    if _has_trailing_bypass_comment(bash_command):
        return True
    should_skip_next_value = False
    for each_token in _commit_argument_tokens(bash_command):
        if should_skip_next_value:
            should_skip_next_value = False
            continue
        if each_token == LONG_FLAG_PREFIX:
            return True
        if _is_all_flag_token(each_token):
            return True
        if each_token in ALL_COMMIT_VALUE_OPTION_TOKENS:
            should_skip_next_value = True
            continue
        if each_token.startswith(SHORT_FLAG_PREFIX):
            continue
        return True
    return False


def _session_edited_keys(session_id: str) -> set[str]:
    """Return the case-folded resolved paths this session recorded as edited.

    Args:
        session_id: Raw ``session_id`` from the hook payload.

    Returns:
        The case-folded resolved absolute paths from the tracker file, or an
        empty set when the file is absent, unreadable, or malformed.
    """
    sanitized_session_id = SESSION_ID_UNSAFE_CHARACTERS_PATTERN.sub("", session_id)
    effective_session_id = sanitized_session_id or STATE_FILE_DEFAULT_SESSION_ID
    file_name = f"{SESSION_EDIT_FILE_PREFIX}{effective_session_id}{SESSION_EDIT_FILE_SUFFIX}"
    edit_file = Path(tempfile.gettempdir()) / file_name
    try:
        raw_contents = edit_file.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return set()
    try:
        parsed_payload = json.loads(raw_contents)
    except json.JSONDecodeError:
        return set()
    if not isinstance(parsed_payload, dict):
        return set()
    recorded_paths = parsed_payload.get(ALL_EDITED_FILE_PATHS_KEY, [])
    if not isinstance(recorded_paths, list):
        return set()
    edited_keys: set[str] = set()
    for each_path in recorded_paths:
        if not isinstance(each_path, str) or not each_path:
            continue
        try:
            resolved_key = str(Path(each_path).resolve()).casefold()
        except OSError:
            continue
        edited_keys.add(resolved_key)
    return edited_keys


def _tracked_unstaged_paths(repository_root: Path) -> dict[str, str] | None:
    """Return tracked-but-unstaged files keyed by their case-folded resolved path.

    Args:
        repository_root: Repository root used as the git working directory.

    Returns:
        A mapping of case-folded resolved absolute path to repository-relative
        path for each tracked file with unstaged changes. None when the git
        command fails, so the caller can allow the commit rather than block on
        an infrastructure failure.
    """
    try:
        completed_process = subprocess.run(
            list(ALL_TRACKED_UNSTAGED_FILES_COMMAND),
            check=False, capture_output=True,
            text=True,
            encoding=GIT_DIFF_OUTPUT_ENCODING,
            timeout=GIT_DIFF_TIMEOUT_SECONDS,
            cwd=str(repository_root),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if completed_process.returncode != 0:
        return None
    repository_relative_by_key: dict[str, str] = {}
    for each_line in completed_process.stdout.splitlines():
        repository_relative_path = each_line.strip()
        if not repository_relative_path:
            continue
        absolute_key = str((repository_root / repository_relative_path).resolve()).casefold()
        repository_relative_by_key[absolute_key] = repository_relative_path
    return repository_relative_by_key


def _offending_repository_relative_paths(
    all_session_edited_keys: set[str], all_unstaged_paths_by_key: dict[str, str]
) -> list[str]:
    """Return the tracked-unstaged files this session edited, repository-relative.

    Args:
        all_session_edited_keys: Case-folded resolved paths this session edited.
        all_unstaged_paths_by_key: Tracked-unstaged files keyed by their
            case-folded resolved path.

    Returns:
        The sorted repository-relative paths present in both sets.
    """
    all_offending_paths = [
        repository_relative_path
        for absolute_key, repository_relative_path in all_unstaged_paths_by_key.items()
        if absolute_key in all_session_edited_keys
    ]
    return sorted(all_offending_paths)


def _build_denial(all_offending_paths: list[str]) -> dict:
    """Build the PreToolUse deny payload listing the dropped files.

    Args:
        all_offending_paths: The tracked-unstaged files this session edited,
            repository-relative.

    Returns:
        The hookSpecificOutput deny mapping for the PreToolUse protocol.
    """
    file_list = "\n".join(
        f"{DENY_FILE_BULLET_PREFIX}{each_path}"
        for each_path in all_offending_paths
    )
    space_joined_paths = " ".join(all_offending_paths)
    denial_reason = SESSION_EDIT_DENY_TEMPLATE.format(
        file_list=file_list,
        space_joined_paths=space_joined_paths,
        bypass_marker=PARTIAL_COMMIT_BYPASS_MARKER,
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": denial_reason,
        }
    }


def main() -> None:
    """Deny a git commit that would drop a tracked file that was edited yet left unstaged."""
    hook_payload = read_hook_input_dictionary_from_stdin()
    if hook_payload is None:
        sys.exit(0)
    tool_input = hook_payload.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)
    bash_command = tool_input.get("command", "")
    if not isinstance(bash_command, str) or not bash_command:
        sys.exit(0)
    if not is_git_commit_invocation(bash_command):
        sys.exit(0)
    if _commit_bypasses_stage_check(bash_command):
        sys.exit(0)
    session_id = str(hook_payload.get("session_id") or "")
    session_edited_keys = _session_edited_keys(session_id)
    if not session_edited_keys:
        sys.exit(0)
    working_directory = resolve_directory(extract_git_working_directory(bash_command))
    repository_root = resolve_repository_root(working_directory)
    if repository_root is None:
        sys.exit(0)
    repository_relative_by_key = _tracked_unstaged_paths(repository_root)
    if repository_relative_by_key is None:
        sys.exit(0)
    offending_paths = _offending_repository_relative_paths(
        session_edited_keys, repository_relative_by_key
    )
    if not offending_paths:
        sys.exit(0)
    denial = _build_denial(offending_paths)
    log_hook_block(
        calling_hook_name="session_edit_stage_gate.py",
        hook_event="PreToolUse",
        block_reason=denial["hookSpecificOutput"]["permissionDecisionReason"],
        tool_name="Bash",
        offending_input_preview=bash_command,
    )
    print(json.dumps(denial))
    sys.exit(0)


if __name__ == "__main__":
    main()
