"""Behavioral tests for the push code-review gate.

Each test drives the gate against a real git work tree with a change surface
and a real stamp store under an isolated home, so the deny/allow decision runs
the same hash-and-coverage path the hook runs in production.
"""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

_HOOK_DIR = Path(__file__).resolve().parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

GIT_TIMEOUT_SECONDS = 30
LOW_EFFORT = "low"
XHIGH_EFFORT = "xhigh"
CODE_SOURCE = "def add(a: int, b: int) -> int:\n    return a + b\n"
CODE_CHANGE = "def add(a: int, b: int) -> int:\n    return a - b\n"
DOCS_SOURCE = "# Notes\n\nfirst line\n"
DOCS_CHANGE = "# Notes\n\nsecond line\n"
BYPASS_MARKER = "# code-review-skip"


def _load_module(module_name: str) -> ModuleType:
    module_spec = importlib.util.spec_from_file_location(
        module_name, _HOOK_DIR / f"{module_name}.py"
    )
    assert module_spec is not None
    assert module_spec.loader is not None
    loaded_module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


gate_module = _load_module("code_review_push_gate")
store_module = _load_module("code_review_stamp_store")


@pytest.fixture(autouse=True)
def enable_code_review_enforcement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Behavior tests exercise the gates with enforcement on."""
    monkeypatch.setattr(gate_module, "CODE_REVIEW_ENFORCEMENT_ENABLED", True)


def _run_git(repository_directory: Path, *git_arguments: str) -> None:
    subprocess.run(
        ["git", "-C", str(repository_directory), *git_arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SECONDS,
    )


def _init_pushed_repo(tmp_path: Path, tracked_name: str, base_text: str) -> Path:
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
    (work_directory / tracked_name).write_text(base_text, encoding="utf-8")
    _run_git(work_directory, "add", "-A")
    _run_git(work_directory, "commit", "-m", "base")
    _run_git(work_directory, "remote", "add", "origin", str(origin_directory))
    _run_git(work_directory, "push", "-u", "origin", "main")
    return work_directory


def _make_code_surface_repo(tmp_path: Path) -> Path:
    work_directory = _init_pushed_repo(tmp_path, "app.py", CODE_SOURCE)
    (work_directory / "app.py").write_text(CODE_CHANGE, encoding="utf-8")
    return work_directory


def _make_docs_surface_repo(tmp_path: Path) -> Path:
    work_directory = _init_pushed_repo(tmp_path, "notes.md", DOCS_SOURCE)
    (work_directory / "notes.md").write_text(DOCS_CHANGE, encoding="utf-8")
    return work_directory


def _isolate_home(monkeypatch: pytest.MonkeyPatch, fake_home: Path) -> None:
    home_text = str(fake_home)
    monkeypatch.setenv("HOME", home_text)
    monkeypatch.setenv("USERPROFILE", home_text)
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)


def _prepared_code_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    return _make_code_surface_repo(tmp_path)


def _record_stamp(work_directory: Path, effort: str) -> None:
    surface_hash = store_module.live_surface_hash(str(work_directory))
    assert surface_hash is not None
    store_module.record_clean_stamp(str(work_directory), surface_hash, effort)


def _run_main(monkeypatch: pytest.MonkeyPatch, command_text: str, work_directory: Path) -> str:
    payload_text = json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": command_text},
            "cwd": str(work_directory),
        }
    )
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload_text))
    captured_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_stdout)
    gate_module.main()
    return captured_stdout.getvalue()


def test_push_without_low_stamp_denies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work_directory = _prepared_code_repo(monkeypatch, tmp_path)
    deny_reason = gate_module.deny_reason_for_directory(str(work_directory))
    assert deny_reason is not None
    assert "PUSH_GATE" in deny_reason


def test_covering_low_stamp_allows_push(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work_directory = _prepared_code_repo(monkeypatch, tmp_path)
    _record_stamp(work_directory, LOW_EFFORT)
    assert gate_module.deny_reason_for_directory(str(work_directory)) is None


def test_covering_xhigh_stamp_allows_push(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work_directory = _prepared_code_repo(monkeypatch, tmp_path)
    _record_stamp(work_directory, XHIGH_EFFORT)
    assert gate_module.deny_reason_for_directory(str(work_directory)) is None


def test_docs_only_surface_is_exempt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    work_directory = _make_docs_surface_repo(tmp_path)
    assert gate_module.deny_reason_for_directory(str(work_directory)) is None


def test_git_push_payload_denies(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work_directory = _prepared_code_repo(monkeypatch, tmp_path)
    emitted = _run_main(monkeypatch, "git push origin main", work_directory)
    assert "PUSH_GATE" in emitted


def test_git_push_with_leading_flags_denies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    work_directory = _prepared_code_repo(monkeypatch, tmp_path)
    emitted = _run_main(monkeypatch, "git push --force-with-lease origin main", work_directory)
    assert "PUSH_GATE" in emitted


def test_git_commit_is_not_gated_by_push_hook(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    work_directory = _prepared_code_repo(monkeypatch, tmp_path)
    emitted = _run_main(monkeypatch, "git commit -m change", work_directory)
    assert emitted == ""


def test_git_stash_push_is_not_gated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    work_directory = _prepared_code_repo(monkeypatch, tmp_path)
    emitted = _run_main(monkeypatch, "git stash push", work_directory)
    assert emitted == ""


def test_code_review_skip_marker_allows_push(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    work_directory = _prepared_code_repo(monkeypatch, tmp_path)
    emitted = _run_main(monkeypatch, f"git push origin main {BYPASS_MARKER}", work_directory)
    assert emitted == ""


def test_enforcement_off_allows_push_without_stamp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(gate_module, "CODE_REVIEW_ENFORCEMENT_ENABLED", False)
    work_directory = _prepared_code_repo(monkeypatch, tmp_path)
    assert gate_module.deny_reason_for_directory(str(work_directory)) is None
    emitted = _run_main(monkeypatch, "git push origin main", work_directory)
    assert emitted == ""
