"""Repository-root exemption tests for the TDD enforcer hook.

A path inside the session's repository root is never ephemeral scratch,
whatever directory the repository itself is checked out under, so a
production file inside a repository checked out under /tmp still needs a
paired test.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).parent / "tdd_enforcer.py"

_BEHAVIOR_BEARING_CONTENT = "def fulfill_order(order: str) -> str:\n    return order\n"


def _run_hook_with_payload(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=os.environ,
    )


def _make_write_payload_with_cwd(file_path: str, content: str, cwd: str) -> dict:
    return {
        "tool_name": "Write",
        "tool_input": {"file_path": file_path, "content": content},
        "cwd": cwd,
    }


def _decision_from(completed: subprocess.CompletedProcess[str]) -> str | None:
    if not completed.stdout:
        return None
    hook_output = json.loads(completed.stdout).get("hookSpecificOutput", {})
    return hook_output.get("permissionDecision")


def test_should_deny_production_file_inside_repository_root_under_tmp() -> None:
    """A production file inside a repository under /tmp still needs a test."""
    repository_root = "/tmp/pr-alpha"
    file_path = f"{repository_root}/hooks/blocking/orders.py"
    payload = _make_write_payload_with_cwd(file_path, _BEHAVIOR_BEARING_CONTENT, repository_root)
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) == "deny", (
        f"TDD enforcer must gate a repository file under /tmp, got: {completed.stdout!r}"
    )


def test_should_stay_exempt_for_scratch_outside_repository_root() -> None:
    """A genuine scratch file outside the repository stays exempt."""
    repository_root = "/tmp/pr-alpha"
    scratch_target = "/tmp/scratch/one_off.py"
    payload = _make_write_payload_with_cwd(
        scratch_target, _BEHAVIOR_BEARING_CONTENT, repository_root
    )
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) != "deny", (
        f"TDD enforcer must not deny scratch outside the repository, got: {completed.stdout!r}"
    )


def test_should_stay_exempt_for_unrelated_worktree_sibling_under_tmp() -> None:
    """A sibling worktree sharing repository_root's name prefix stays exempt."""
    repository_root = "/tmp/pr-alpha"
    unrelated_sibling_target = "/tmp/pr-alpha-sibling/hooks/orders.py"
    payload = _make_write_payload_with_cwd(
        unrelated_sibling_target, _BEHAVIOR_BEARING_CONTENT, repository_root
    )
    completed = _run_hook_with_payload(payload)
    assert _decision_from(completed) != "deny", (
        f"TDD enforcer must not deny an unrelated sibling worktree, got: {completed.stdout!r}"
    )
