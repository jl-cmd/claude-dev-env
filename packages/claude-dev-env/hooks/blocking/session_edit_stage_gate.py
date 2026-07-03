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
    ALL_STAGE_ALL_ADD_FLAG_TOKENS,
    ALL_STAGE_ALL_ADD_PATHSPEC_TOKENS,
    ALL_STAGING_SUBCOMMAND_TOKENS,
    ALL_TRACKED_UNSTAGED_FILES_COMMAND,
    COMMIT_ALL_SHORT_FLAG_LETTER,
    COMMIT_SUBCOMMAND_TOKEN,
    DENY_FILE_BULLET_LINE_SEPARATOR,
    DENY_FILE_BULLET_PREFIX,
    DENY_PATHSPEC_SEPARATOR,
    ENV_ASSIGNMENT_PREFIX_PATTERN,
    GIT_DIFF_OUTPUT_ENCODING,
    GIT_DIFF_TIMEOUT_SECONDS,
    GIT_EXECUTABLE_TOKEN,
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
    """Return the tokens that follow the ``commit`` subcommand of its segment.

    The command is split into shell segments. The segment whose git subcommand
    is ``commit`` supplies its post-subcommand tokens, so a bare ``commit``
    token in an earlier segment (``echo commit && git commit -a``) never stands
    in for the real commit's arguments.

    Args:
        bash_command: The Bash tool command string.

    Returns:
        The argument tokens of the git commit invocation. Empty when the
        command cannot be tokenized or runs no ``git commit`` segment.
    """
    try:
        all_tokens = shlex.split(bash_command, posix=True)
    except ValueError:
        return []
    for each_segment in _split_into_command_segments(all_tokens):
        subcommand_index = _git_subcommand_index(each_segment)
        if subcommand_index is None:
            continue
        if each_segment[subcommand_index] != COMMIT_SUBCOMMAND_TOKEN:
            continue
        return each_segment[subcommand_index + 1 :]
    return []


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
    the author adds on purpose, so its ``#`` and ``partial-commit`` parts are
    the final tokens of the command. The same text earlier in the command — a
    quoted commit message (``git commit -m "fix # partial-commit"``) or an
    earlier ``echo # partial-commit`` segment — does not match, so the gate
    still runs.

    Args:
        bash_command: The Bash tool command string.

    Returns:
        True when the marker is the final tokens of the command; False when it
        appears earlier or the command will not tokenize.
    """
    marker_tokens = PARTIAL_COMMIT_BYPASS_MARKER.split()
    try:
        all_tokens = shlex.split(bash_command, posix=True)
    except ValueError:
        return False
    marker_length = len(marker_tokens)
    if marker_length > len(all_tokens):
        return False
    return all_tokens[-marker_length:] == marker_tokens


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


def _command_token_index(all_segment_tokens: list[str]) -> int | None:
    """Return the index of a segment's command word, past any env assignments.

    A segment may open with ``NAME=value`` assignments before the command it
    runs, as in ``GIT_DIR=x git commit``. This skips those leading assignments
    and returns the first real command token, so ``git`` is read as the command
    only when it holds that position — not when it rides as an argument to
    another command (``echo git commit``).

    Args:
        all_segment_tokens: One command segment's tokens.

    Returns:
        The index of the first non-assignment token, or None for an empty
        segment or one that is only assignments.
    """
    for each_offset, each_token in enumerate(all_segment_tokens):
        if ENV_ASSIGNMENT_PREFIX_PATTERN.match(each_token):
            continue
        return each_offset
    return None


def _git_subcommand_index(all_segment_tokens: list[str]) -> int | None:
    """Return the index of a segment's git subcommand, skipping global options.

    The segment runs ``git`` as its command word — past any leading
    ``NAME=value`` assignments — and ``git`` may carry global options before its
    subcommand: ``-C``/``-c``/``--git-dir`` and their siblings each take a
    value, so ``git -C path add file`` resolves the ``add`` token, not ``path``.

    Args:
        all_segment_tokens: One command segment's tokens.

    Returns:
        The index of the subcommand token following ``git`` and its global
        options, or None when the segment does not run ``git`` as its command.
    """
    command_index = _command_token_index(all_segment_tokens)
    if command_index is None or all_segment_tokens[command_index] != GIT_EXECUTABLE_TOKEN:
        return None
    should_skip_next_value = False
    for each_offset in range(command_index + 1, len(all_segment_tokens)):
        each_token = all_segment_tokens[each_offset]
        if should_skip_next_value:
            should_skip_next_value = False
            continue
        if each_token in ALL_GIT_GLOBAL_VALUE_OPTION_TOKENS:
            should_skip_next_value = True
            continue
        if each_token.startswith(SHORT_FLAG_PREFIX):
            continue
        return each_offset
    return None


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
    subcommand_index = _git_subcommand_index(all_segment_tokens)
    if subcommand_index is None:
        return None
    return all_segment_tokens[subcommand_index]


def _preceding_staging_segments(bash_command: str) -> list[list[str]]:
    """Return the ``git add``/``git stage`` segments that run before the commit.

    The common ``git add widget.py && git commit -m update`` idiom stages a file
    in its own segment right before the commit, so the file is staged by the
    time the commit runs even though it reads as unstaged when the gate inspects
    the index. A staging segment that runs after the commit segment stages
    nothing for that commit and is left out.

    Args:
        bash_command: The Bash tool command string.

    Returns:
        The staging segments (each a token list) that run before the commit
        segment, in command order. Empty when the command will not tokenize,
        runs no commit, or has no such preceding segment.
    """
    try:
        all_tokens = shlex.split(bash_command, posix=True)
    except ValueError:
        return []
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
        return []
    return [
        each_segment
        for each_segment in all_segments[:commit_segment_index]
        if _git_subcommand(each_segment) in ALL_STAGING_SUBCOMMAND_TOKENS
    ]


def _staging_segment_covers_all_paths(all_segment_tokens: list[str]) -> bool:
    """Return whether one staging segment stages every path (a stage-all form).

    ``git add -A``/``--all``/``-u``/``--update`` and ``git add .``/``git add :/``
    each stage the whole working tree, so any file the session edited is staged
    by the time the commit runs. A ``--`` ends option parsing: every token after
    it is a path, so ``git add -- -A`` stages a file named ``-A`` and is not a
    stage-all form.

    Args:
        all_segment_tokens: One ``git add``/``git stage`` segment's tokens.

    Returns:
        True when the segment carries a stage-all flag before any ``--`` or a
        stage-all pathspec; False otherwise.
    """
    subcommand_index = _git_subcommand_index(all_segment_tokens)
    if subcommand_index is None:
        return False
    has_seen_end_of_options = False
    for each_token in all_segment_tokens[subcommand_index + 1 :]:
        if not has_seen_end_of_options and each_token == LONG_FLAG_PREFIX:
            has_seen_end_of_options = True
            continue
        if not has_seen_end_of_options and each_token in ALL_STAGE_ALL_ADD_FLAG_TOKENS:
            return True
        if each_token in ALL_STAGE_ALL_ADD_PATHSPEC_TOKENS:
            return True
    return False


def _staging_covers_all_paths(all_staging_segments: list[list[str]]) -> bool:
    """Return whether any preceding staging segment stages every path.

    Args:
        all_staging_segments: The staging segments that run before the commit.

    Returns:
        True when one of the segments is a stage-all form; False otherwise.
    """
    return any(
        _staging_segment_covers_all_paths(each_segment)
        for each_segment in all_staging_segments
    )


def _staged_positional_path_tokens(all_staging_segments: list[list[str]]) -> list[str]:
    """Return the positional path tokens of the specific-path staging segments.

    A specific-path ``git add README.md`` names the paths it stages as
    positional tokens after the subcommand, so only those paths are staged by
    the time the commit runs. A ``--`` ends option parsing: before it, a
    ``-``-prefixed token is a flag; after it, every token is a path, so
    ``git add -- -weird.py`` stages the file ``-weird.py``.

    Args:
        all_staging_segments: The staging segments that run before the commit.

    Returns:
        Every path token following the staging subcommand, across all segments,
        in command order.
    """
    all_path_tokens: list[str] = []
    for each_segment in all_staging_segments:
        subcommand_index = _git_subcommand_index(each_segment)
        if subcommand_index is None:
            continue
        has_seen_end_of_options = False
        for each_token in each_segment[subcommand_index + 1 :]:
            if not has_seen_end_of_options and each_token == LONG_FLAG_PREFIX:
                has_seen_end_of_options = True
                continue
            if not has_seen_end_of_options and each_token.startswith(SHORT_FLAG_PREFIX):
                continue
            all_path_tokens.append(each_token)
    return all_path_tokens


def _staged_path_keys(
    all_staging_segments: list[list[str]],
    working_directory: str | None,
    repository_root: Path,
) -> set[str]:
    """Return the case-folded resolved keys the specific-path staging segments stage.

    A ``git add`` path token is relative to the command's working directory, so
    it resolves against ``working_directory`` when that is known and against the
    repository root otherwise.

    Args:
        all_staging_segments: The staging segments that run before the commit.
        working_directory: The command's resolved git working directory, or None
            when the command runs in the hook's own working directory.
        repository_root: Repository root used as the base when no working
            directory is known.

    Returns:
        The case-folded resolved absolute paths of every specific staged path
        token, matching the key shape used for session-edited and unstaged paths.
    """
    base_directory = Path(working_directory) if working_directory is not None else repository_root
    staged_keys: set[str] = set()
    for each_token in _staged_positional_path_tokens(all_staging_segments):
        try:
            resolved_key = str((base_directory / each_token).resolve()).casefold()
        except OSError:
            continue
        staged_keys.add(resolved_key)
    return staged_keys


def _invokes_git_commit(bash_command: str) -> bool:
    """Return whether the command runs a real ``git commit`` subcommand.

    A benign command can name the phrase ``git commit`` as plain text, as in
    ``grep -rn "git commit" .``. This check tokenizes the command, splits it at
    each shell separator, and confirms one segment invokes ``git`` with a
    ``commit`` subcommand.

    Args:
        bash_command: The Bash tool command string.

    Returns:
        True when a command segment runs ``git commit``; False when the command
        will not tokenize or names ``commit`` only as text.
    """
    try:
        all_tokens = shlex.split(bash_command, posix=True)
    except ValueError:
        return False
    return any(
        _git_subcommand(each_segment) == COMMIT_SUBCOMMAND_TOKEN
        for each_segment in _split_into_command_segments(all_tokens)
    )


def _commit_bypasses_stage_check(bash_command: str) -> bool:
    """Return whether the commit intentionally opts out of the stage check.

    A ``# partial-commit`` trailing comment, a ``-a``/``--all`` flag, and a
    pathspec argument (a ``--`` separator or a bare positional path) each mark a
    deliberate partial commit that the gate leaves alone.

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
    all_session_edited_keys: set[str],
    all_unstaged_paths_by_key: dict[str, str],
    all_staged_path_keys: set[str],
) -> list[str]:
    """Return the tracked-unstaged files this session edited, repository-relative.

    Args:
        all_session_edited_keys: Case-folded resolved paths this session edited.
        all_unstaged_paths_by_key: Tracked-unstaged files keyed by their
            case-folded resolved path.
        all_staged_path_keys: Case-folded resolved paths a preceding specific
            ``git add`` already staged, excluded from the result.

    Returns:
        The sorted repository-relative paths this session edited that remain
        unstaged and were not staged by a preceding specific ``git add``.
    """
    all_offending_paths = [
        repository_relative_path
        for absolute_key, repository_relative_path in all_unstaged_paths_by_key.items()
        if absolute_key in all_session_edited_keys
        and absolute_key not in all_staged_path_keys
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
    space_joined_paths = DENY_PATHSPEC_SEPARATOR.join(
        shlex.quote(each_path) for each_path in all_offending_paths
    )
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
    if not _invokes_git_commit(bash_command):
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
    preceding_staging_segments = _preceding_staging_segments(bash_command)
    if _staging_covers_all_paths(preceding_staging_segments):
        sys.exit(0)
    repository_relative_by_key = _tracked_unstaged_paths(repository_root)
    if repository_relative_by_key is None:
        sys.exit(0)
    staged_path_keys = _staged_path_keys(
        preceding_staging_segments, working_directory, repository_root
    )
    offending_paths = _offending_repository_relative_paths(
        session_edited_keys, repository_relative_by_key, staged_path_keys
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
