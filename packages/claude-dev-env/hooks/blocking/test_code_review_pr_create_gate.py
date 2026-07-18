"""Behavioral tests for the PR-create code-review gate.

Each test drives the gate against a real git work tree with a change surface
and a real stamp store under an isolated home, so the deny/allow decision runs
the same hash-and-coverage path the hook runs in production.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_HOOK_DIR = Path(__file__).resolve().parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

GIT_TIMEOUT_SECONDS = 30
XHIGH_EFFORT = "xhigh"
LOW_EFFORT = "low"
SURFACE_SOURCE = "def add(a: int, b: int) -> int:\n    return a + b\n"
SURFACE_CHANGE = "def add(a: int, b: int) -> int:\n    return a - b\n"
MCP_CREATE_PR_TOOL = "mcp__plugin_github_github__create_pull_request"


def _load_module(module_name: str) -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(
        module_name, _HOOK_DIR / f"{module_name}.py"
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


gate_module = _load_module("code_review_pr_create_gate")
store_module = _load_module("code_review_stamp_store")
deny_module = _load_module("code_review_gate_deny")


def _run_git(repository_directory: Path, *git_arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository_directory), *git_arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
    )


def _make_repo_with_change_surface(tmp_path: Path) -> Path:
    origin_directory = tmp_path / "origin.git"
    work_directory = tmp_path / "work"
    work_directory.mkdir()
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(origin_directory)],
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
    )
    _run_git(work_directory, "init", "--initial-branch=main")
    _run_git(work_directory, "config", "user.email", "tests@example.com")
    _run_git(work_directory, "config", "user.name", "Reviewer")
    (work_directory / "app.py").write_text(SURFACE_SOURCE, encoding="utf-8")
    _run_git(work_directory, "add", "-A")
    _run_git(work_directory, "commit", "-m", "base")
    _run_git(work_directory, "remote", "add", "origin", str(origin_directory))
    _run_git(work_directory, "push", "-u", "origin", "main")
    (work_directory / "app.py").write_text(SURFACE_CHANGE, encoding="utf-8")
    return work_directory


def _isolate_home(monkeypatch: pytest.MonkeyPatch, fake_home: Path) -> None:
    home_text = str(fake_home)
    monkeypatch.setenv("HOME", home_text)
    monkeypatch.setenv("USERPROFILE", home_text)
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)


def _prepared_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    return _make_repo_with_change_surface(tmp_path)


def _record_stamp(work_directory: Path, effort: str) -> None:
    surface_hash = store_module.live_surface_hash(str(work_directory))
    assert surface_hash is not None
    store_module.record_clean_stamp(str(work_directory), surface_hash, effort)


def test_command_invokes_gh_pr_create_detects_real_invocation() -> None:
    assert gate_module.command_invokes_gh_pr_create("gh pr create --title T --body-file b.md")


def test_gh_pr_edit_is_not_a_create() -> None:
    assert not gate_module.command_invokes_gh_pr_create("gh pr edit 1 --title T")


def test_echoed_prose_is_not_a_create() -> None:
    assert not gate_module.command_invokes_gh_pr_create('echo "gh pr create"')


def test_is_mcp_create_pull_request_tool_matches_configured_name() -> None:
    assert gate_module.is_mcp_create_pull_request_tool(MCP_CREATE_PR_TOOL)
    assert not gate_module.is_mcp_create_pull_request_tool("Bash")


def test_uncovered_surface_denies_pr_create(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    work_directory = _prepared_repo(monkeypatch, tmp_path)
    deny_reason = gate_module.deny_reason_for_directory(str(work_directory))
    assert deny_reason is not None
    assert "PR_CREATE_GATE" in deny_reason


def test_covering_xhigh_stamp_allows_pr_create(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    work_directory = _prepared_repo(monkeypatch, tmp_path)
    _record_stamp(work_directory, XHIGH_EFFORT)
    assert gate_module.deny_reason_for_directory(str(work_directory)) is None


def test_low_only_stamp_does_not_satisfy_xhigh(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    work_directory = _prepared_repo(monkeypatch, tmp_path)
    _record_stamp(work_directory, LOW_EFFORT)
    deny_reason = gate_module.deny_reason_for_directory(str(work_directory))
    assert deny_reason is not None
    assert "PR_CREATE_GATE" in deny_reason


def test_shell_gh_pr_create_payload_denies_without_stamp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    work_directory = _prepared_repo(monkeypatch, tmp_path)
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "gh pr create --title T --body-file b.md"},
        "cwd": str(work_directory),
    }
    deny_decision = gate_module.decision_for_payload(payload)
    assert deny_decision is not None
    assert deny_decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_mcp_create_pull_request_payload_denies_without_stamp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    work_directory = _prepared_repo(monkeypatch, tmp_path)
    payload = {
        "tool_name": MCP_CREATE_PR_TOOL,
        "tool_input": {"owner": "o", "repo": "r"},
        "cwd": str(work_directory),
    }
    deny_decision = gate_module.decision_for_payload(payload)
    assert deny_decision is not None
    assert deny_decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_gh_pr_edit_payload_is_not_denied(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work_directory = _prepared_repo(monkeypatch, tmp_path)
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "gh pr edit 1 --title T"},
        "cwd": str(work_directory),
    }
    assert gate_module.decision_for_payload(payload) is None


def test_build_deny_payload_shape() -> None:
    deny_payload = deny_module.build_code_review_deny_payload("blocked reason")
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert deny_payload["hookSpecificOutput"]["permissionDecisionReason"] == "blocked reason"
