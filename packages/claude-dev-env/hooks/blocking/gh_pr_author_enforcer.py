#!/usr/bin/env python3
"""PreToolUse hook: auto-switch the active gh CLI account to GITHUB_DEFAULT_ACCOUNT for `gh pr create`.

Pinning every PR to a single canonical author makes the /bugteam and /qbug
follow-up swap deterministic. Those skills refuse to post REQUEST_CHANGES
reviews when the active gh CLI account matches the PR author (the GitHub
API returns HTTP 422 — "cannot review own pull request"). When every PR
has the same author, the swap step before bugteam is the same single
command every time.

Behavior:
- No-op when the bash command does not invoke `gh pr create`.
- No-op when `--web` / `-w` is present, since the browser flow does not
  create the PR via the gh CLI token.
- No-op when GITHUB_DEFAULT_ACCOUNT is unset (other users without this
  workflow are unaffected).
- No-op when the active gh account cannot be determined (gh missing,
  network failure) — defers to gh's own error path rather than blocking
  a command that may already be broken for other reasons.
- No-op when the active gh account already equals GITHUB_DEFAULT_ACCOUNT.
- Otherwise runs `gh auth switch --user <required>` silently and writes
  a per-session state file recording the original account. The PostToolUse
  companion (gh_pr_author_restore.py) reads that state file and swaps
  back after `gh pr create` finishes. On switch failure the hook falls
  back to the deny payload with the manual command.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_hooks_tree_path = str(Path(__file__).absolute().parent.parent)
if _hooks_tree_path not in sys.path:
    sys.path.insert(0, _hooks_tree_path)

from _gh_pr_author_swap_utils import (  # noqa: E402  # sys.path shim above must run first
    _all_gh_pr_create_segments,
    _command_invokes_gh_pr_create_in_stripped,
    _delete_state_file,
    _preprocess_command_for_matching,
    _state_file_path,
    _strip_substitution_bodies,
    _switch_gh_account,
    _write_line,
)
from config.gh_pr_author_swap_constants import (  # noqa: E402  # sys.path shim above must run first
    ALL_GH_API_USER_COMMAND,
    BASH_TOOL_NAME,
    GH_API_USER_TIMEOUT_SECONDS,
    OS_O_NOFOLLOW_ATTRIBUTE_NAME,
    REQUIRED_ACCOUNT_ENV_VAR,
    STATE_FILE_ORIGINAL_ACCOUNT_KEY,
    STATE_FILE_PAYLOAD_TEXT_ENCODING_NAME,
    STATE_FILE_PERMISSION_MODE,
    STATE_FILE_PRIMARY_ACCOUNT_KEY,
    WEB_FLAG_PATTERN,
)


def _active_gh_account() -> str | None:
    """Return the login of the active gh CLI account, or None when undetermined.

    Returns:
        The login string from ``gh api user --jq .login`` on success.
        None when gh is missing, the gh binary lacks executable permission,
        the command fails, times out, or returns an empty value.
        ``OSError`` covers every spawn-time failure
        (``FileNotFoundError`` when gh is absent, ``PermissionError``
        when gh exists but is not executable, and any other
        platform-specific spawn errors) so the hook follows its
        documented "skip the check" failure path rather than crashing.
        The caller treats None as "skip the check."
    """
    try:
        completed_process = subprocess.run(
            list(ALL_GH_API_USER_COMMAND),
            capture_output=True,
            text=True,
            timeout=GH_API_USER_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed_process.returncode != 0:
        return None
    stripped_login = completed_process.stdout.strip()
    return stripped_login or None


def _write_swap_state(
    state_file: Path,
    original_account: str,
    primary_account: str,
) -> bool:
    """Persist the swap-back state for the PostToolUse restore hook.

    The state file is created atomically with ``os.open`` using
    ``O_WRONLY | O_CREAT | O_EXCL`` (plus ``O_NOFOLLOW`` on platforms
    that expose it) so an attacker on a shared POSIX workstation cannot
    pre-create the predictable path as a symlink pointing at an
    arbitrary writable file. The mode bits are set at create time so
    the file is never momentarily world-readable between ``open`` and
    ``chmod``. A defense-in-depth ``chmod`` call follows the write in
    case the platform's umask honored the ``mode`` argument differently
    than expected.

    A stale file left by a crashed prior session can collide with the
    ``O_EXCL`` guard. The function unlinks such a file and retries the
    create exactly once; a second collision is treated as a write
    failure so the caller does not silently overwrite something it did
    not create.

    A failure after a successful write unlinks the partially-written
    file via ``_delete_state_file`` before returning False so the caller
    does not leave a world-readable state file behind for the
    SessionStart cleanup hook to later pick up and trigger an unexpected
    ``gh auth switch``.

    Every ``os.close`` call is guarded by ``try``/``except OSError``
    because delayed-writeback filesystems (NFS, FUSE) can surface a
    write error at close time rather than at write time. On the
    post-successful-write branch, an ``OSError`` from ``os.close`` is
    treated as a write failure: the file is unlinked and False is
    returned so the caller rolls back the gh auth switch. On the
    partial-write failure branch the file is already being unlinked,
    so an ``OSError`` from ``os.close`` is swallowed — re-raising
    would crash the hook mid-rollback.

    Args:
        state_file: Destination path returned by ``_state_file_path``.
        original_account: Login that was active before the swap.
        primary_account: Login swapped to (always ``GITHUB_DEFAULT_ACCOUNT``).

    Returns:
        True when the atomic create, write, and chmod all succeed.
        False on any filesystem failure. A failure at any stage unlinks
        any partially-written file so the caller does not leave a
        world-readable state file behind.
    """
    swap_state = {
        STATE_FILE_ORIGINAL_ACCOUNT_KEY: original_account,
        STATE_FILE_PRIMARY_ACCOUNT_KEY: primary_account,
    }
    serialized_payload = json.dumps(swap_state).encode(STATE_FILE_PAYLOAD_TEXT_ENCODING_NAME)
    open_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, OS_O_NOFOLLOW_ATTRIBUTE_NAME):
        open_flags |= os.O_NOFOLLOW  # type: ignore[attr-defined]  # POSIX-only flag, guarded by hasattr above
    file_descriptor = _open_state_file_with_retry(state_file, open_flags)
    if file_descriptor is None:
        return False
    if not _write_payload_completely(file_descriptor, serialized_payload):
        try:
            os.close(file_descriptor)
        except OSError:
            pass
        _delete_state_file(state_file)
        return False
    try:
        os.close(file_descriptor)
    except OSError:
        _delete_state_file(state_file)
        return False
    try:
        os.chmod(state_file, STATE_FILE_PERMISSION_MODE)
    except OSError:
        _delete_state_file(state_file)
        return False
    return True


def _write_payload_completely(file_descriptor: int, serialized_payload: bytes) -> bool:
    """Write every byte of ``serialized_payload`` to ``file_descriptor``.

    ``os.write`` is documented to potentially write fewer bytes than
    requested, especially on pipes and non-blocking descriptors. The
    state file is opened in blocking mode, but the contract holds — a
    signal arriving mid-write can cut a write short, and partial writes
    have been observed across NFS mounts and FUSE filesystems. Treating
    the first ``os.write`` return value as authoritative would leave a
    truncated JSON state file on disk; the restore hook would then
    parse the truncated file, log "malformed state file", delete it,
    and leave the active gh CLI account stranded on the canonical
    author instead of restoring the original account.

    The loop reissues ``os.write`` against a slice of the payload that
    starts at the byte count already written, until every byte has been
    emitted. A return value of zero from ``os.write`` indicates the
    underlying file descriptor cannot accept any more bytes and is
    treated as a write failure so the caller can roll back rather than
    spin forever.

    Args:
        file_descriptor: Open file descriptor returned by ``os.open``.
            The caller retains ownership and is responsible for closing
            the descriptor whether this function returns True or False.
        serialized_payload: Encoded JSON payload to write. The caller
            encodes via ``STATE_FILE_PAYLOAD_TEXT_ENCODING_NAME`` before
            invoking this helper.

    Returns:
        True when every byte of ``serialized_payload`` was written.
        False on any ``OSError`` raised by ``os.write`` or when
        ``os.write`` returns zero before the payload is complete.
    """
    payload_length = len(serialized_payload)
    bytes_already_written = 0
    while bytes_already_written < payload_length:
        try:
            bytes_just_written = os.write(
                file_descriptor,
                serialized_payload[bytes_already_written:],
            )
        except OSError:
            return False
        if bytes_just_written == 0:
            return False
        bytes_already_written += bytes_just_written
    return True


def _open_state_file_with_retry(state_file: Path, open_flags: int) -> int | None:
    """Open the state file atomically, unlinking a stale collision once.

    The enforcer can race against a state file left behind by a prior
    crashed session at the same predictable path. The first ``O_EXCL``
    open raises ``FileExistsError`` in that case; the function unlinks
    the stale file and retries exactly once. A second ``FileExistsError``
    is treated as a genuine race against a concurrent process and
    surfaces as ``None`` so the caller can fall back to its deny path.

    Args:
        state_file: Destination path returned by ``_state_file_path``.
        open_flags: Bitmask passed to ``os.open`` — must include
            ``O_EXCL`` so this retry logic can distinguish "stale file
            collision" from "wrote a fresh file".

    Returns:
        A file descriptor on success. ``None`` when both the initial
        open and the post-unlink retry fail.
    """
    try:
        return os.open(state_file, open_flags, STATE_FILE_PERMISSION_MODE)
    except FileExistsError:
        try:
            state_file.unlink()
        except OSError:
            return None
    except OSError:
        return None
    try:
        return os.open(state_file, open_flags, STATE_FILE_PERMISSION_MODE)
    except OSError:
        return None


def _build_switch_failure_message(required_account: str, current_account: str) -> str:
    """Build the deny reason emitted when the silent auto-switch fails.

    Args:
        required_account: Value of GITHUB_DEFAULT_ACCOUNT.
        current_account: Login returned by gh before the failed switch.

    Returns:
        A multi-line corrective message naming both accounts and giving
        the exact ``gh auth switch`` command the user should run.
    """
    return (
        f"BLOCKED [gh-pr-author]: tried to auto-switch the active gh CLI "
        f"account from `{current_account}` to `{required_account}` so "
        f"`gh pr create` would author from the canonical account, but "
        f"`gh auth switch` failed.\n\n"
        f"  Current:  {current_account}\n"
        f"  Required: {required_account}  (from ${REQUIRED_ACCOUNT_ENV_VAR})\n\n"
        f"Run first:\n"
        f"  gh auth switch --user {required_account}\n\n"
        f"If you genuinely want to author this PR from a different account "
        f"in this one case, switch to that account and retry. To create the "
        f"PR through the browser instead (uses your browser's GitHub session, "
        f"not the gh CLI token), add `--web`."
    )


def _build_state_write_failure_message(
    required_account: str,
    current_account: str,
    state_file: Path,
    has_rollback_succeeded: bool,
) -> str:
    """Build the deny reason emitted when state-file persistence fails after a successful swap.

    Args:
        required_account: Value of GITHUB_DEFAULT_ACCOUNT (the swap target).
        current_account: Login that was active before the swap (the
            restore target the failed state file should have recorded).
        state_file: Path the enforcer tried and failed to write.
        has_rollback_succeeded: True when the reverse ``gh auth switch``
            back to ``current_account`` returned zero, so the user is
            on the original account again. False when the reverse switch
            also failed and the user is still on ``required_account``.

    Returns:
        A multi-line corrective message explaining the swap and
        rollback outcome. The lead-in sentence describes the actual
        state — "the swap was reversed" when the rollback succeeded,
        "the reverse-switch also failed and you are still on
        ``required_account``" when it did not. The trailing
        ``gh auth status`` / ``gh auth switch`` recovery commands are
        emitted in both branches so the user can verify and recover
        regardless of where the gh CLI ended up.
    """
    if has_rollback_succeeded:
        rollback_outcome_sentence = (
            f"The swap was reversed to put `{current_account}` back in place, "
            f"and `gh pr create` is being denied to prevent leaving the "
            f"workflow in an inconsistent state."
        )
    else:
        rollback_outcome_sentence = (
            f"The reverse `gh auth switch` to put `{current_account}` back "
            f"in place ALSO failed, so the active gh CLI account is still "
            f"`{required_account}`. `gh pr create` is being denied so the "
            f"user can recover the original account before re-running."
        )
    return (
        f"BLOCKED [gh-pr-author]: swapped the active gh CLI account "
        f"from `{current_account}` to `{required_account}` so "
        f"`gh pr create` would author from the canonical account, but "
        f"writing the per-session state file used to restore the prior "
        f"account afterward failed. {rollback_outcome_sentence}\n\n"
        f"  Original:             {current_account}\n"
        f"  Required:             {required_account}  (from ${REQUIRED_ACCOUNT_ENV_VAR})\n"
        f"  State file (failed):  {state_file}\n\n"
        f"Verify the active account and recover manually:\n"
        f"  gh auth status\n"
        f"  gh auth switch --user {current_account}\n\n"
        f"Then re-run `gh pr create` so the enforcer can retry the swap."
    )


def _command_uses_web_flag_in_stripped(preprocessed_command: str) -> bool:
    """Return True when EVERY ``gh pr create`` segment uses ``--web`` / ``-w``.

    The flag is only relevant when it modifies the ``gh pr create``
    invocation itself. A ``-w`` token belonging to an unrelated command
    (for example ``curl -w '%{http_code}'``) before ``gh pr create``, or
    a flag attached to a chained command after a separator like ``&&`` /
    ``||`` / ``;`` / ``|`` / newline, must not flip the enforcer into
    the browser-flow no-op path. A ``-w`` sitting inside a quoted
    argument (for example ``--body "see -w docs"``) likewise must not
    match — the caller blanks those out via
    ``_preprocess_command_for_matching`` before passing the command in
    here.

    A ``--web`` token sitting inside a substitution body (for example
    ``gh pr create --title "$(echo --web)"``) is an argument to the
    subshell command, not a flag on the outer ``gh pr create`` —
    ``_strip_substitution_bodies`` blanks the substitution before the
    segment search so the false-positive does not skip the swap. The
    safety bias is intentional: a substitution that genuinely expands
    to ``--web`` is now treated as a non-web invocation and still
    triggers the account swap, which is harmless because ``gh pr create``
    with both ``--web`` and the canonical author swapped in just runs
    the browser flow.

    When the command chains multiple ``gh pr create`` invocations
    (``gh pr create --web && gh pr create --title T``), the enforcer
    must trigger as long as ANY of them omits the web flag — otherwise
    the second invocation would slip through under the active account.
    A short-circuiting ``all()`` over every segment gives that
    "browser-flow only when EVERY segment opts in" semantics.

    Args:
        preprocessed_command: Output of ``_preprocess_command_for_matching`` —
            the caller is responsible for blanking inert quoted regions
            and bash comments before passing in. ``main()`` computes
            this once and passes it to both this helper and
            ``_command_invokes_gh_pr_create_in_stripped`` so the
            character-walk preprocessing runs exactly once per command.

    Returns:
        True when every ``gh pr create`` segment in the preprocessed
        command carries ``--web`` or ``-w`` as a whole token. False
        when ``gh pr create`` is absent, or when any segment lacks the
        flag (including segments whose only ``--web`` token sat inside
        a substitution body that has now been blanked).
    """
    all_gh_pr_create_segments = _all_gh_pr_create_segments(preprocessed_command)
    if not all_gh_pr_create_segments:
        return False
    return all(
        bool(WEB_FLAG_PATTERN.search(_strip_substitution_bodies(each_segment)))
        for each_segment in all_gh_pr_create_segments
    )


def _emit_deny_payload(reason_text: str) -> None:
    """Write the JSON deny payload to stdout for Claude Code to consume.

    Args:
        reason_text: User-facing explanation displayed by Claude Code.
    """
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason_text,
        }
    }
    _write_line(json.dumps(deny_payload), sys.stdout)


def main() -> None:
    """Read PreToolUse hook input on stdin and auto-switch the gh account when warranted.

    Exits 0 in all paths. On the silent-switch success path no output is
    produced. On switch-failure the JSON deny payload is written to
    stdout. On every no-op condition nothing is written.
    """
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    if hook_input.get("tool_name") != BASH_TOOL_NAME:
        sys.exit(0)

    command = hook_input.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    preprocessed_command = _preprocess_command_for_matching(command)
    if not _command_invokes_gh_pr_create_in_stripped(preprocessed_command):
        sys.exit(0)

    if _command_uses_web_flag_in_stripped(preprocessed_command):
        sys.exit(0)

    required_account = os.environ.get(REQUIRED_ACCOUNT_ENV_VAR, "").strip()
    if not required_account:
        sys.exit(0)

    current_account = _active_gh_account()
    if current_account is None:
        sys.exit(0)
    if current_account.casefold() == required_account.casefold():
        sys.exit(0)

    has_switched_account = _switch_gh_account(required_account)
    if not has_switched_account:
        _emit_deny_payload(
            _build_switch_failure_message(required_account, current_account)
        )
        sys.exit(0)

    session_id = str(hook_input.get("session_id") or "")
    state_file = _state_file_path(session_id)
    has_written_state = _write_swap_state(
        state_file,
        original_account=current_account,
        primary_account=required_account,
    )
    if not has_written_state:
        has_rollback_succeeded = _switch_gh_account(current_account)
        _emit_deny_payload(
            _build_state_write_failure_message(
                required_account,
                current_account,
                state_file,
                has_rollback_succeeded,
            )
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
