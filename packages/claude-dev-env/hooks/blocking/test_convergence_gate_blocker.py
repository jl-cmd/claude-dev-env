"""Unit tests for convergence-gate-blocker PreToolUse hook."""

import importlib.util
import io
import json
import pathlib
import subprocess
import sys

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

import re

_GH_PR_READY_PATTERN = re.compile(r"\bgh\s+pr\s+ready\b(?![^&|;\n]*--undo)")

hook_spec = importlib.util.spec_from_file_location(
    "convergence_gate_blocker",
    _HOOK_DIR / "convergence_gate_blocker.py",
)
assert hook_spec is not None
assert hook_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_spec)
hook_spec.loader.exec_module(hook_module)
_resolve_pr_number = hook_module._resolve_pr_number


def test_matches_gh_pr_ready_with_number() -> None:
    assert _GH_PR_READY_PATTERN.search("gh pr ready 418")


def test_matches_gh_pr_ready_without_number() -> None:
    assert _GH_PR_READY_PATTERN.search("gh pr ready")


def test_matches_gh_pr_ready_with_flags() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh pr ready --undo")


def test_does_not_match_gh_pr_create() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh pr create --title T")


def test_does_not_match_gh_pr_view() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh pr view 418")


def test_does_not_match_gh_issue_close() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh issue close 42")


def test_extracts_pr_number_from_command() -> None:
    assert _resolve_pr_number("gh pr ready 418", None) == 418


def test_extracts_pr_number_with_flags() -> None:
    assert _resolve_pr_number("gh pr ready 99 --undo", None) == 99


def test_returns_none_when_no_number_and_no_repo() -> None:
    assert _resolve_pr_number("gh pr ready", "/nonexistent/path") is None


def test_matches_gh_pr_ready_in_compound_command() -> None:
    assert not _GH_PR_READY_PATTERN.search("gh pr ready --undo && gh pr create")


def test_run_convergence_check_forwards_cwd_to_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_cwd: list[object] = []

    def fake_run(*_run_args: object, **run_keywords: object) -> subprocess.CompletedProcess[str]:
        captured_cwd.append(run_keywords.get("cwd"))
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(hook_module.subprocess, "run", fake_run)
    hook_module._run_convergence_check(
        "check_convergence.py", "owner", "repo", 783, "C:/worktrees/pr-783"
    )
    assert captured_cwd == ["C:/worktrees/pr-783"]


def test_run_convergence_check_forwards_none_cwd_as_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_cwd: list[object] = []

    def fake_run(*_run_args: object, **run_keywords: object) -> subprocess.CompletedProcess[str]:
        captured_cwd.append(run_keywords.get("cwd"))
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(hook_module.subprocess, "run", fake_run)
    hook_module._run_convergence_check("check_convergence.py", "owner", "repo", 783, None)
    assert captured_cwd == [None]


def test_main_reads_cwd_from_top_level_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    convergence_script = (
        tmp_path / ".claude" / "skills" / "pr-converge" / "scripts" / "check_convergence.py"
    )
    convergence_script.parent.mkdir(parents=True)
    convergence_script.write_text("")
    monkeypatch.setattr(hook_module.Path, "home", classmethod(lambda _cls: tmp_path))

    worktree_path = str(tmp_path / "worktrees" / "pr-783")
    monkeypatch.setattr(hook_module, "_resolve_owner_repo", lambda _cwd: ("jl-cmd", "repo"))

    captured_cwd: list[object] = []

    def fake_check(
        _script: str, _owner: str, _repo: str, _pr_number: int, cwd: str | None
    ) -> subprocess.CompletedProcess[str]:
        captured_cwd.append(cwd)
        return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    monkeypatch.setattr(hook_module, "_run_convergence_check", fake_check)

    payload = {
        "tool_name": "Bash",
        "cwd": worktree_path,
        "tool_input": {"command": "gh pr ready 783", "cwd": "C:/wrong/session/dir"},
    }
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    with pytest.raises(SystemExit):
        hook_module.main()

    assert captured_cwd == [worktree_path]
