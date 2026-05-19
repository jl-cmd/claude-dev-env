#!/usr/bin/env python3
"""PostToolUse hook: restore the prior gh CLI account after `gh pr create` runs.

Companion to ``gh_pr_author_enforcer.py``. When the PreToolUse enforcer
silently swaps the active gh account to ``GITHUB_DEFAULT_ACCOUNT`` and
records the original account in a per-session state file, this hook
reads that state file after the matching Bash invocation finishes and
runs ``gh auth switch --user <original>`` to put the prior account back
in place.

The state file is deleted only when the restore switch succeeds. If
``gh auth switch`` fails the state file is left in place so the
SessionStart cleanup hook (``gh_pr_author_session_cleanup.py``) can
retry on the next session start instead of stranding the user on the
canonical author account.

Behavior:
- No-op when tool_name is not Bash.
- No-op when the command did not invoke ``gh pr create`` (uses the same
  regex as the enforcer so the pair stays in sync).
- No-op when no per-session state file exists — means the enforcer
  never swapped on this command.
- Otherwise reads the state file, runs ``gh auth switch --user <original>``,
  and deletes the state file only when the switch succeeded. Failures
  are logged to stderr; this hook never blocks the workflow.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_hooks_tree_path = str(Path(__file__).absolute().parent.parent)
if _hooks_tree_path not in sys.path:
    sys.path.insert(0, _hooks_tree_path)

from _gh_pr_author_swap_utils import (  # noqa: E402  # sys.path shim above must run first
    _command_invokes_gh_pr_create_in_stripped,
    _delete_state_file,
    _preprocess_command_for_matching,
    _read_original_account,
    _state_file_is_attacker_planted,
    _state_file_path,
    _switch_gh_account,
    _write_line,
)
from config.gh_pr_author_swap_constants import BASH_TOOL_NAME  # noqa: E402  # sys.path shim above must run first


def main() -> None:
    """Read PostToolUse hook input on stdin and restore the prior gh account.

    Exits 0 in every path. Errors are logged to stderr only — this hook
    must never block subsequent commands.
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

    session_id = str(hook_input.get("session_id") or "")
    state_file = _state_file_path(session_id)
    if _state_file_is_attacker_planted(state_file):
        _write_line(
            f"[gh-pr-author-restore] state file at {state_file} has unexpected mode/owner; "
            f"skipping restore and preserving file for inspection",
            sys.stderr,
        )
        sys.exit(0)
    original_account = _read_original_account(state_file)
    if original_account is None:
        if state_file.exists():
            _delete_state_file(state_file)
        sys.exit(0)

    has_restored_account = _switch_gh_account(original_account)
    if has_restored_account:
        _delete_state_file(state_file)
    else:
        _write_line(
            f"[gh-pr-author-restore] failed to restore active gh account to {original_account!r}; "
            f"state file {state_file} left in place so the SessionStart cleanup hook can retry",
            sys.stderr,
        )
    sys.exit(0)


if __name__ == "__main__":
    main()
