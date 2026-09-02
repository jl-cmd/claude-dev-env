"""Production-subprocess coverage for destructive command patterns."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

_BLOCKING_DIRECTORY = Path(__file__).resolve().parent
if str(_BLOCKING_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_BLOCKING_DIRECTORY))

import _path_setup  # noqa: E402, F401

from hooks_constants.destructive_command_environment_constants import (  # noqa: E402
    DESTRUCTIVE_DENY_MODE_ENV_VAR,
    EPHEMERAL_AUTO_ALLOW_DISABLE_ENV_VAR,
)
from test_hook_subprocess_support import (  # noqa: E402
    build_bash_payload,
    run_hook_as_subprocess,
)

SCRIPT_PATH = _BLOCKING_DIRECTORY / "destructive_command_blocker.py"
ALL_DESTRUCTIVE_ENVIRONMENT_NAMES = (
    DESTRUCTIVE_DENY_MODE_ENV_VAR,
    EPHEMERAL_AUTO_ALLOW_DISABLE_ENV_VAR,
)


def _run_hook(
    command: str,
    working_directory: Path,
    home_directory: Path,
) -> subprocess.CompletedProcess[str]:
    return run_hook_as_subprocess(
        hook_script_path=SCRIPT_PATH,
        payload_text=build_bash_payload(command),
        working_directory=working_directory,
        home_directory=home_directory,
        all_environment_names_to_remove=ALL_DESTRUCTIVE_ENVIRONMENT_NAMES,
    )


@pytest.mark.parametrize(
    ("command", "reason_fragment"),
    [
        ("rm -rf /var/log/myapp", "rm -rf"),
        ("rm --recursive --force /var/log/myapp", "rm --recursive --force"),
        ("rm -r /", "rm -r on broad path"),
        ("mkfs.ext4 /dev/sda1", "mkfs"),
        ("dd if=/tmp/disk.img of=/dev/sda", "dd raw disk write"),
        ("git reset --hard HEAD~1", "git reset --hard"),
        ("git push --force origin main", "git push --force"),
        ("git push -f origin main", "git push -f"),
        ("git clean -fd", "git clean -fd"),
        ("git clean -f", "git clean -f"),
        ("psql -c 'DROP TABLE users'", "DROP TABLE"),
        ("psql -c 'DROP DATABASE app'", "DROP DATABASE"),
        ("psql -c 'TRUNCATE TABLE users'", "TRUNCATE TABLE"),
        ("git commit --no-verify", "git --no-verify"),
        ("git commit --no-gpg-sign", "git --no-gpg-sign"),
        ("git -c commit.gpgsign=false commit", "commit.gpgsign=false"),
    ],
)
def test_protected_command_asks_for_approval(
    command: str,
    reason_fragment: str,
    tmp_path: Path,
) -> None:
    filesystem_root = Path(Path.cwd().anchor)
    completed_hook = _run_hook(command, filesystem_root, tmp_path)

    hook_decision_payload = json.loads(completed_hook.stdout)
    assert completed_hook.returncode == 0
    assert completed_hook.stderr == ""
    assert hook_decision_payload["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert hook_decision_payload["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert reason_fragment in hook_decision_payload["hookSpecificOutput"][
        "permissionDecisionReason"
    ]


@pytest.mark.parametrize(
    "command",
    [
        "git status --short",
        "rm -rf /tmp/destructive-command-blocker/build",
        "rm -rf /project/worktrees/feature/build",
        "git push --force origin claude/fix-hook-test",
    ],
)
def test_permitted_command_exits_silently(command: str, tmp_path: Path) -> None:
    completed_hook = _run_hook(command, tmp_path, tmp_path)

    assert completed_hook.returncode == 0
    assert completed_hook.stdout == ""
    assert completed_hook.stderr == ""


def test_ephemeral_rm_exits_silently_when_parent_disables_auto_allow(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(EPHEMERAL_AUTO_ALLOW_DISABLE_ENV_VAR, "1")

    with tempfile.TemporaryDirectory(
        dir=tmp_path,
        prefix="destructive command blocker ",
    ) as ephemeral_directory_path:
        completed_hook = _run_hook(
            f'rm -rf "{ephemeral_directory_path}"',
            tmp_path,
            tmp_path,
        )

        assert completed_hook.returncode == 0
        assert completed_hook.stdout == ""
        assert completed_hook.stderr == ""


def test_git_reset_hard_in_ephemeral_project_exits_silently(
    tmp_path: Path,
) -> None:
    completed_hook = _run_hook("git reset --hard HEAD~1", tmp_path, tmp_path)

    assert completed_hook.returncode == 0
    assert completed_hook.stdout == ""
    assert completed_hook.stderr == ""
