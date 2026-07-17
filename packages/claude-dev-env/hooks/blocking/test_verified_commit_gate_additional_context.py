"""The verified-commit gate's deny payload teaches the verify-skip policy.

A blocked commit prints a PreToolUse ``hookSpecificOutput`` deny whose
``additionalContext`` carries the ``# verify-skip`` usage rule, so the agent
learns at the moment of the block when the marker is legitimate.
"""

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

gate_spec = importlib.util.spec_from_file_location(
    "verified_commit_gate",
    _HOOK_DIR / "verified_commit_gate.py",
)
assert gate_spec is not None
assert gate_spec.loader is not None
gate_module = importlib.util.module_from_spec(gate_spec)
gate_spec.loader.exec_module(gate_module)
gate_main = gate_module.main

PRODUCTION_SOURCE = "def add(left: int, right: int) -> int:\n    return left + right\n"
CHANGED_SOURCE = "def add(left: int, right: int) -> int:\n    return left - right\n"


def _run_git(work_dir: pathlib.Path, *git_arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(work_dir), *git_arguments],
        check=True,
        capture_output=True,
        text=True,
    )


def _make_gated_repo(tmp_path: pathlib.Path) -> pathlib.Path:
    origin_dir = tmp_path / "origin.git"
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    subprocess.run(
        ["git", "init", "--bare", "--initial-branch=main", str(origin_dir)],
        check=True,
        capture_output=True,
        text=True,
    )
    _run_git(work_dir, "init", "--initial-branch=main")
    _run_git(work_dir, "config", "user.email", "tests@example.com")
    _run_git(work_dir, "config", "user.name", "Gate Tests")
    (work_dir / "app.py").write_text(PRODUCTION_SOURCE, encoding="utf-8")
    _run_git(work_dir, "add", "-A")
    _run_git(work_dir, "commit", "-m", "base")
    _run_git(work_dir, "remote", "add", "origin", str(origin_dir))
    _run_git(work_dir, "push", "-u", "origin", "main")
    (work_dir / "app.py").write_text(CHANGED_SOURCE, encoding="utf-8")
    return work_dir


def _isolate_home(monkeypatch: pytest.MonkeyPatch, fake_home: pathlib.Path) -> None:
    home_text = str(fake_home)
    monkeypatch.setenv("HOME", home_text)
    monkeypatch.setenv("USERPROFILE", home_text)
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)


def _run_gate_main(
    monkeypatch: pytest.MonkeyPatch, command_text: str, work_dir: pathlib.Path
) -> None:
    payload_text = json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": command_text},
            "cwd": str(work_dir),
            "transcript_path": "",
        }
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload_text))
    gate_main()


def test_deny_payload_carries_verify_skip_additional_context(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: pathlib.Path,
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    work_dir = _make_gated_repo(tmp_path)
    _run_gate_main(monkeypatch, "git commit -m x", work_dir)
    deny_payload = json.loads(capsys.readouterr().out)
    hook_specific_output = deny_payload["hookSpecificOutput"]
    assert hook_specific_output["permissionDecision"] == "deny"
    additional_context = hook_specific_output["additionalContext"]
    assert "# verify-skip" in additional_context
    assert "already passed clean" in additional_context
    assert "fresh verification" in additional_context


def test_marker_inside_a_quoted_message_still_denies(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: pathlib.Path,
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    work_dir = _make_gated_repo(tmp_path)
    quoted_marker_command = 'git commit -m "docs: explain the # verify-skip escape hatch"'
    _run_gate_main(monkeypatch, quoted_marker_command, work_dir)
    deny_payload = json.loads(capsys.readouterr().out)
    assert deny_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_marker_as_a_trailing_comment_bypasses(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: pathlib.Path,
) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    work_dir = _make_gated_repo(tmp_path)
    trailing_marker_command = 'git commit -m "wire up feature" # verify-skip'
    _run_gate_main(monkeypatch, trailing_marker_command, work_dir)
    assert capsys.readouterr().out == ""
