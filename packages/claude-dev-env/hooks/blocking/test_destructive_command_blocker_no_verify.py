"""Tests for --no-verify / --no-gpg-sign blocking in destructive_command_blocker.

git-workflow.md:30-33 marks these as NON-NEGOTIABLE to skip — they bypass
hook signing and verification. The blocker must ASK before allowing them.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).parent / "destructive_command_blocker.py"


def _run_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    child_environment = os.environ.copy()
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
        env=child_environment,
    )


def _make_bash_payload(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def test_asks_on_git_commit_no_verify() -> None:
    payload = _make_bash_payload('git commit -m "wip" --no-verify')
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask", (
        f"Expected ask for git commit --no-verify, got: {response!r}"
    )
    assert "no-verify" in response["hookSpecificOutput"]["permissionDecisionReason"], (
        f"Reason must mention --no-verify, got: {response!r}"
    )


def test_asks_on_git_push_no_verify() -> None:
    payload = _make_bash_payload("git push --no-verify origin main")
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask", (
        f"Expected ask for git push --no-verify, got: {response!r}"
    )


def test_asks_on_git_no_gpg_sign() -> None:
    payload = _make_bash_payload("git commit --no-gpg-sign -m wip")
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask", (
        f"Expected ask for git --no-gpg-sign, got: {response!r}"
    )
    assert (
        "no-gpg-sign" in response["hookSpecificOutput"]["permissionDecisionReason"]
    ), f"Reason must mention --no-gpg-sign, got: {response!r}"


def test_asks_on_git_commit_with_no_gpg_sign_config() -> None:
    payload = _make_bash_payload("git -c commit.gpgsign=false commit -m wip")
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask", (
        f"Expected ask for -c commit.gpgsign=false, got: {response!r}"
    )


def test_asks_on_quoted_gpgsign_config() -> None:
    payload = _make_bash_payload("git -c 'commit.gpgsign=false' commit -m wip")
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask", (
        f"Expected ask for quoted -c commit.gpgsign=false, got: {response!r}"
    )


def test_asks_on_value_quoted_gpgsign_config() -> None:
    payload = _make_bash_payload("git -c commit.gpgsign='false' commit -m wip")
    result = _run_hook(payload)
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask", (
        f"Expected ask for value-quoted -c commit.gpgsign='false', got: {response!r}"
    )


def test_normal_git_commit_passes() -> None:
    payload = _make_bash_payload('git commit -m "real commit"')
    result = _run_hook(payload)
    if not result.stdout.strip():
        return
    response = json.loads(result.stdout)
    decision = response.get("hookSpecificOutput", {}).get("permissionDecision", "allow")
    assert decision != "ask", (
        f"Normal git commit must not be flagged as destructive, got: {response!r}"
    )
