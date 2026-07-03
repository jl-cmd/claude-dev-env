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
    ALL_COMMIT_VALUE_OPTION_SHORT_LETTERS,
    ALL_COMMIT_VALUE_OPTION_TOKENS,
    ALL_EDITED_FILE_PATHS_KEY,
    ALL_GIT_GLOBAL_VALUE_OPTION_TOKENS,
    ALL_STAGING_SUBCOMMAND_TOKENS,
    ALL_TRACKED_UNSTAGED_FILES_COMMAND,
    COMMIT_ALL_SHORT_FLAG_LETTER,
    COMMIT_SUBCOMMAND_TOKEN,
    GIT_EXECUTABLE_TOKEN,
    DENY_FILE_BULLET_LINE_SEPARATOR,
    DENY_FILE_BULLET_PREFIX,
    DENY_PATHSPEC_SEPARATOR,
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

    A short-flag cluster is read left to right. The scan stops at the first
    value-taking option letter (``m``/``F``/``C``/``c``), whose remainder is
    that option's argument rather than more clustered flags — so
    ``git commit -m"add feature"`` tokenizes to ``-madd feature`` and does not
    count as an ``-a`` cluster even though its message carries an ``a``.

    Args:
        token: One argument token of a git commit invocation.

    Returns:
        True for ``-a``, ``--all``, or a combined short cluster such as
        ``-am`` that carries the ``a`` letter before any value-taking option;
        False otherwise.
    """
    if token in ALL_COMMIT_ALL_FLAGS:
        return True
    if token.startswith(LONG_FLAG_PREFIX):
        return False
    if not token.startswith(SHORT_FLAG_PREFIX):
        return False
    for each_letter in token[1:]:
        if each_letter == COMMIT_ALL_SHORT_FLAG_LETTER:
            return True
        if each_letter in ALL_COMMIT_VALUE_OPTION_SHORT_LETTERS:
            return False
    return False


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


def _split_into_command_segments(all_tokens: list[str]) -> list[list[str]]:
    """Split a token list into segments at each shell command separator.

    Args:
        all_tokens: The tokens of the whole Bash command.

    Returns:
        One token list per command segment, in command order. A ``&&``, ``||``,
        ``;``, ``|``, or ``&`` separator ends the current segment and starts the
        next.
    """
    all_segments: list[list[str]] = []
    current_segment: list[str] = []
    for each_token in all_tokens:
        if each_token in ALL_COMMAND_SEPARATOR_TOKENS:
            all_segments.append(current_segment)
            current_segment = []
            continue
        current_segment.append(each_token)
    all_segments.append(current_segment)
    return all_segments


def _git_subcommand(all_segment_tokens: list[str]) -> str | None:
    """Return the git subcommand of a segment, skipping git's global options.

    A leading ``git`` may carry global options before its subcommand, and
    ``-C``/``-c``/``--git-dir`` and their siblings each take a value — so
    ``git -C path add file`` resolves to the ``add`` subcommand, not ``path``.

    Args:
        all_segment_tokens: One command segment's tokens.

    Returns:
        The subcommand token following ``git`` and its global options, or None
        when the segment invokes no ``git`` subcommand.
    """
    if GIT_EXECUTABLE_TOKEN not in all_segment_tokens:
        return None
    git_index = all_segment_tokens.index(GIT_EXECUTABLE_TOKEN)
    should_skip_next_value = False
    for each_token in all_segment_tokens[git_index + 1 :]:
        if should_skip_next_value:
            should_skip_next_value = False
            continue
        if each_token in ALL_GIT_GLOBAL_VALUE_OPTION_TOKENS:
            should_skip_next_value = True
            continue
        if each_token.startswith(SHORT_FLAG_PREFIX):
            continue
        return each_token
    return None


def _stages_paths_before_commit(bash_command: str) -> bool:
    """Return whether a ``git add``/``git stage`` segment precedes the commit.

    The common ``git add widget.py && git commit -m update`` idiom stages the
    edited file in its own segment right before the commit, so the file is
    staged by the time the commit runs even though it reads as unstaged when the
    gate inspects the index. A staging segment that runs after the commit
    segment stages nothing for that commit and does not count.

    Args:
        bash_command: The Bash tool command string.

    Returns:
        True when a ``git add`` or ``git stage`` segment runs before the commit
        segment; False when the command will not tokenize or holds no such
        segment.
    """
    try:
        all_tokens = shlex.split(bash_command, posix=True)
    except ValueError:
        return False
    all_segments = _split_into_command_segments(all_tokens)
    commit_segment_index = next(
        (
            each_index
            for each_index, each_segment in enumerate(all_segments)
            if _git_subcommand(each_segment) == COMMIT_SUBCOMMAND_TOKEN
        ),
        None,
    )
    if commit_segment_index is None:
        return False
    return any(
        _git_subcommand(each_segment) in ALL_STAGING_SUBCOMMAND_TOKENS
        for each_segment in all_segments[:commit_segment_index]
    )


def _commit_bypasses_stage_check(bash_command: str) -> bool:
    """Return whether the commit intentionally opts out of the stage check.

    A ``# partial-commit`` trailing comment, a ``-a``/``--all`` flag, a pathspec
    argument (a ``--`` separator or a bare positional path), and a preceding
    ``git add``/``git stage`` segment in the same compound command each mark a
    deliberate partial commit that the gate leaves alone.

    Args:
        bash_command: The Bash tool command string.

    Returns:
        True when the commit opts out of the stage check; False otherwise.
    """
    if _has_trailing_bypass_comment(bash_command):
        return True
    if _stages_paths_before_commit(bash_command):
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
    file_list = DENY_FILE_BULLET_LINE_SEPARATOR.join(
        f"{DENY_FILE_BULLET_PREFIX}{each_path}"
        for each_path in all_offending_paths
    )
    space_joined_paths = DENY_PATHSPEC_SEPARATOR.join(all_offending_paths)
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
