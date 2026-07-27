"""Tests for unscoped_search_blocker hook."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


SCRIPT_PATH = Path(__file__).parent / "unscoped_search_blocker.py"

ALL_DENIED_COMMANDS = [
    "find / -iname code_rules_gate.py",
    "find /c -name '*.py'",
    "find ~ -name README.md",
    "find $HOME -type f",
    "ls -R /",
    "bash -c 'find / -name x'",
]

ALL_ALLOWED_COMMANDS = [
    "find . -iname '*.py'",
    "find packages/claude-dev-env -name code_rules_gate.py",
    "find /c/Users/jon/repo -iname SKILL.md",
    "ls -r /",
    "es.exe path:C:\\dev\\repo ext:py gate",
    "git status --short",
]


def _run_hook(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        check=False,
    )


def _bash_payload(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def _powershell_payload(command: str) -> dict:
    return {"tool_name": "PowerShell", "tool_input": {"command": command}}


@pytest.mark.parametrize("each_command", ALL_DENIED_COMMANDS)
def test_denies_unscoped_root_walk(each_command: str) -> None:
    response = json.loads(_run_hook(_bash_payload(each_command)).stdout)
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


@pytest.mark.parametrize("each_command", ALL_ALLOWED_COMMANDS)
def test_allows_scoped_search(each_command: str) -> None:
    assert _run_hook(_bash_payload(each_command)).stdout == ""


def test_denies_recursive_listing_on_windows_drive_root() -> None:
    response = json.loads(
        _run_hook(_powershell_payload("Get-ChildItem -Path C:\\ -Recurse")).stdout
    )
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_allows_recursive_listing_under_project_directory() -> None:
    assert _run_hook(_powershell_payload("Get-ChildItem -Path .\\src -Recurse")).stdout == ""


def test_allows_recursive_listing_without_recurse_flag() -> None:
    assert _run_hook(_powershell_payload("Get-ChildItem -Path C:\\")).stdout == ""


def test_denies_find_root_in_a_chained_segment() -> None:
    response = json.loads(
        _run_hook(_bash_payload("cd /tmp && find / -name x.py")).stdout
    )
    assert response["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_ignores_unsupported_tool_name() -> None:
    payload = {"tool_name": "Edit", "tool_input": {"command": "find / -name x"}}
    assert _run_hook(payload).stdout == ""


def test_ignores_payload_without_a_command() -> None:
    payload = {"tool_name": "Bash", "tool_input": {}}
    assert _run_hook(payload).stdout == ""


def test_deny_message_names_the_scoped_alternative() -> None:
    response = json.loads(_run_hook(_bash_payload("find / -name x.py")).stdout)
    deny_reason = response["hookSpecificOutput"]["permissionDecisionReason"]
    assert "scope" in deny_reason.lower()
