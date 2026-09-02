"""Repository-root exemption tests for code_rules_enforcer and the classifier.

A path inside the session's repository root is never ephemeral, whatever
directory the repository itself is checked out under. These tests cover the
classifier directly and the enforcer's real PreToolUse Write path, plus the
guard cases a too-broad fix could break: an absent cwd, a cwd that covers no
repository, and an unrelated sibling worktree that merely shares a name
prefix under /tmp.
"""

from __future__ import annotations

import json

from blocking import _path_setup  # noqa: F401  (pins this checkout ahead of sibling worktrees)
from blocking.code_rules_enforcer import main as enforcer_main
from blocking.code_rules_shared import is_ephemeral_script_path
from code_rules_enforcer_test_support import run_serialized_payload_entrypoint

_VIOLATING_PRODUCTION_SOURCE = "def process_data(payload: str) -> None:\n    print(payload)\n"


def _build_write_payload_with_cwd(file_path: str, content: str, cwd: str) -> str:
    """Build the JSON payload for a Write tool call that also carries a cwd."""
    return json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": file_path, "content": content},
            "cwd": cwd,
        }
    )


def _run_main_with_write_payload_and_cwd(
    file_path: str,
    content: str,
    cwd: str,
) -> tuple[str, int]:
    """Drive enforcer_main through its stdin entry point for a Write payload carrying cwd."""
    captured_stdout, exit_code = run_serialized_payload_entrypoint(
        enforcer_main, _build_write_payload_with_cwd(file_path, content, cwd)
    )
    return captured_stdout, int(exit_code or 0)


def test_should_return_false_for_file_inside_repository_root_under_tmp() -> None:
    """R1: a path inside repository_root is never ephemeral, even under /tmp."""
    repository_root = "/tmp/pr-alpha"
    file_path = "/tmp/pr-alpha/hooks/blocking/orders.py"
    assert is_ephemeral_script_path(file_path, repository_root) is False


def test_should_return_true_for_sibling_directory_outside_repository_root() -> None:
    """R2: a /tmp sibling that merely shares repository_root's name prefix stays ephemeral."""
    repository_root = "/tmp/pr-alpha"
    sibling_file_path = "/tmp/pr-alpha-sibling/hooks/orders.py"
    assert is_ephemeral_script_path(sibling_file_path, repository_root) is True


def test_should_return_true_when_repository_root_does_not_cover_target() -> None:
    """R3: an unrelated cwd must not blanket-exempt a /tmp target outside it."""
    unrelated_repository_root = "/tmp/scratch-workspace"
    scratch_target = "/tmp/scratch-elsewhere/notes.py"
    assert is_ephemeral_script_path(scratch_target, unrelated_repository_root) is True


def test_should_deny_pretooluse_target_inside_repository_root_under_tmp() -> None:
    """B22: a production file inside a repository checked out under /tmp is gated for real."""
    repository_root = "/tmp/pr-alpha"
    file_path = f"{repository_root}/hooks/blocking/orders.py"
    captured_stdout, exit_code = _run_main_with_write_payload_and_cwd(
        file_path,
        _VIOLATING_PRODUCTION_SOURCE,
        repository_root,
    )
    assert "deny" in captured_stdout.lower(), (
        f"enforcer must gate a repository file under /tmp, got exit_code={exit_code}, "
        f"stdout={captured_stdout!r}"
    )


def test_should_stay_exempt_for_scratch_outside_repository_root() -> None:
    """B23: a genuine scratch file outside the repository stays exempt."""
    repository_root = "/tmp/pr-alpha"
    scratch_target = "/tmp/scratch/one_off.py"
    captured_stdout, exit_code = _run_main_with_write_payload_and_cwd(
        scratch_target,
        _VIOLATING_PRODUCTION_SOURCE,
        repository_root,
    )
    assert exit_code == 0
    assert "deny" not in captured_stdout.lower()


def test_should_stay_exempt_when_working_directory_covers_no_repository() -> None:
    """B24: a cwd that covers no repository must not exempt an unrelated /tmp target."""
    unrelated_working_directory = "/tmp/scratch-workspace"
    scratch_target = "/tmp/scratch-elsewhere/notes.py"
    captured_stdout, exit_code = _run_main_with_write_payload_and_cwd(
        scratch_target,
        _VIOLATING_PRODUCTION_SOURCE,
        unrelated_working_directory,
    )
    assert exit_code == 0
    assert "deny" not in captured_stdout.lower()


def test_should_stay_exempt_for_unrelated_worktree_sibling_under_tmp() -> None:
    """B25: a sibling worktree sharing repository_root's name prefix stays exempt."""
    repository_root = "/tmp/pr-alpha"
    unrelated_sibling_target = "/tmp/pr-alpha-sibling/hooks/orders.py"
    captured_stdout, exit_code = _run_main_with_write_payload_and_cwd(
        unrelated_sibling_target,
        _VIOLATING_PRODUCTION_SOURCE,
        repository_root,
    )
    assert exit_code == 0
    assert "deny" not in captured_stdout.lower()
