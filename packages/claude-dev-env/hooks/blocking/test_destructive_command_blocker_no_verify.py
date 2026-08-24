"""Tests for --no-verify / --no-gpg-sign blocking in destructive_command_blocker.

git-workflow.md:30-33 marks these as NON-NEGOTIABLE to skip — they bypass
hook signing and verification. The blocker must ASK before allowing them.
"""

import json
import sys
from pathlib import Path

_BLOCKING_DIRECTORY = Path(__file__).resolve().parent
if str(_BLOCKING_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_BLOCKING_DIRECTORY))

import _path_setup  # noqa: E402, F401

from test_hook_subprocess_support import (  # noqa: E402
    build_bash_payload,
    run_hook_as_subprocess,
)

SCRIPT_PATH = _BLOCKING_DIRECTORY / "destructive_command_blocker.py"


def test_asks_on_git_commit_no_verify(tmp_path: Path) -> None:
    result = run_hook_as_subprocess(
        hook_script_path=SCRIPT_PATH,
        payload_text=build_bash_payload('git commit -m "wip" --no-verify'),
        working_directory=tmp_path,
        home_directory=tmp_path,
    )
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask", (
        f"Expected ask for git commit --no-verify, got: {response!r}"
    )
    assert "no-verify" in response["hookSpecificOutput"]["permissionDecisionReason"], (
        f"Reason must mention --no-verify, got: {response!r}"
    )


def test_asks_on_git_push_no_verify(tmp_path: Path) -> None:
    result = run_hook_as_subprocess(
        hook_script_path=SCRIPT_PATH,
        payload_text=build_bash_payload("git push --no-verify origin main"),
        working_directory=tmp_path,
        home_directory=tmp_path,
    )
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask", (
        f"Expected ask for git push --no-verify, got: {response!r}"
    )


def test_asks_on_git_no_gpg_sign(tmp_path: Path) -> None:
    result = run_hook_as_subprocess(
        hook_script_path=SCRIPT_PATH,
        payload_text=build_bash_payload("git commit --no-gpg-sign -m wip"),
        working_directory=tmp_path,
        home_directory=tmp_path,
    )
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask", (
        f"Expected ask for git --no-gpg-sign, got: {response!r}"
    )
    assert (
        "no-gpg-sign" in response["hookSpecificOutput"]["permissionDecisionReason"]
    ), f"Reason must mention --no-gpg-sign, got: {response!r}"


def test_asks_on_git_commit_with_no_gpg_sign_config(tmp_path: Path) -> None:
    result = run_hook_as_subprocess(
        hook_script_path=SCRIPT_PATH,
        payload_text=build_bash_payload("git -c commit.gpgsign=false commit -m wip"),
        working_directory=tmp_path,
        home_directory=tmp_path,
    )
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask", (
        f"Expected ask for -c commit.gpgsign=false, got: {response!r}"
    )


def test_asks_on_quoted_gpgsign_config(tmp_path: Path) -> None:
    result = run_hook_as_subprocess(
        hook_script_path=SCRIPT_PATH,
        payload_text=build_bash_payload("git -c 'commit.gpgsign=false' commit -m wip"),
        working_directory=tmp_path,
        home_directory=tmp_path,
    )
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask", (
        f"Expected ask for quoted -c commit.gpgsign=false, got: {response!r}"
    )


def test_asks_on_value_quoted_gpgsign_config(tmp_path: Path) -> None:
    result = run_hook_as_subprocess(
        hook_script_path=SCRIPT_PATH,
        payload_text=build_bash_payload("git -c commit.gpgsign='false' commit -m wip"),
        working_directory=tmp_path,
        home_directory=tmp_path,
    )
    response = json.loads(result.stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "ask", (
        f"Expected ask for value-quoted -c commit.gpgsign='false', got: {response!r}"
    )


def test_normal_git_commit_passes(tmp_path: Path) -> None:
    result = run_hook_as_subprocess(
        hook_script_path=SCRIPT_PATH,
        payload_text=build_bash_payload('git commit -m "real commit"'),
        working_directory=tmp_path,
        home_directory=tmp_path,
    )
    if not result.stdout.strip():
        return
    response = json.loads(result.stdout)
    decision = response.get("hookSpecificOutput", {}).get("permissionDecision", "allow")
    assert decision != "ask", (
        f"Normal git commit must not be flagged as destructive, got: {response!r}"
    )
