"""Tests for the destructive-command-blocker deny mode.

The sandbox runs under ``--dangerously-skip-permissions``, which auto-resolves
an ``ask`` decision, so only a hard ``deny`` contains a destructive command.
Setting ``CLAUDE_DESTRUCTIVE_DENY_MODE`` turns the hook's terminal ``ask`` into
a ``deny`` so the sandbox can be contained.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_BLOCKING_DIRECTORY = Path(__file__).resolve().parent
if str(_BLOCKING_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_BLOCKING_DIRECTORY))

SCRIPT_PATH = _BLOCKING_DIRECTORY / "destructive_command_blocker.py"

import _path_setup  # noqa: E402, F401

from test_hook_subprocess_support import (  # noqa: E402
    build_bash_payload,
    run_hook_as_subprocess,
)


def _run_hook_with_environment(
    command: str,
    environment_update_by_name: dict[str, str],
    temporary_home_directory: Path,
) -> subprocess.CompletedProcess[str]:
    return run_hook_as_subprocess(
        hook_script_path=SCRIPT_PATH,
        payload_text=build_bash_payload(command),
        working_directory=temporary_home_directory,
        home_directory=temporary_home_directory,
        all_environment_names_to_remove=("CLAUDE_DESTRUCTIVE_DENY_MODE",),
        environment_updates_by_name=environment_update_by_name,
    )


def test_rm_rf_denies_when_deny_mode_env_is_set(tmp_path: Path) -> None:
    completed_hook = _run_hook_with_environment(
        "rm -rf /var/log/myapp",
        {"CLAUDE_DESTRUCTIVE_DENY_MODE": "1"},
        tmp_path,
    )
    hook_decision_by_field = json.loads(completed_hook.stdout)

    assert hook_decision_by_field["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "rm -rf" in hook_decision_by_field["hookSpecificOutput"]["permissionDecisionReason"]


def test_rm_rf_asks_when_deny_mode_env_is_absent(tmp_path: Path) -> None:
    completed_hook = _run_hook_with_environment("rm -rf /var/log/myapp", {}, tmp_path)
    hook_decision_by_field = json.loads(completed_hook.stdout)

    assert hook_decision_by_field["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert "rm -rf" in hook_decision_by_field["hookSpecificOutput"]["permissionDecisionReason"]
