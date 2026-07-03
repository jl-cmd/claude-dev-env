"""Tests for write_handoff: the durable per-run handoff writer."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_write_handoff_module() -> ModuleType:
    module_path = _SCRIPTS_DIR / "write_handoff.py"
    spec = importlib.util.spec_from_file_location("write_handoff", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


write_handoff = _load_write_handoff_module()


_FROZEN_TIMESTAMP = "2026-07-03T12:00:00+00:00"


def _point_base_dir_at(monkeypatch: pytest.MonkeyPatch, base: Path) -> None:
    monkeypatch.setattr(write_handoff, "_handoff_base_dir", lambda: base)
    monkeypatch.setattr(write_handoff, "_now_iso", lambda: _FROZEN_TIMESTAMP)


def test_resolve_handoff_dir_joins_run_name_under_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """resolve_handoff_dir places the run's directory under the durable base."""
    _point_base_dir_at(monkeypatch, tmp_path)
    resolved = write_handoff.resolve_handoff_dir("bugteam-pr-4")
    assert resolved == tmp_path / "bugteam-pr-4"


def test_handoff_base_dir_lives_under_home_runtime_pr_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The durable base sits under the user home, not the OS temp directory."""
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    base = write_handoff._handoff_base_dir()
    assert base == tmp_path / ".claude" / "runtime" / "pr-loop"


def test_write_handoff_records_resume_command_and_phase(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """write_handoff writes handoff.json and HANDOFF.md carrying the resume
    command, phase, run id, completed steps, and a timestamp."""
    _point_base_dir_at(monkeypatch, tmp_path)
    handoff_dir = write_handoff.write_handoff(
        pr_number=4,
        head_ref="feat/pr-loop-durable-handoff",
        phase="tick",
        resume_command="claude --resume /pr-converge",
        run_id="wf_abc123",
        all_completed_steps=["preflight", "audit"],
        note="Copilot wait-gate still open.",
    )
    assert handoff_dir == tmp_path / "bugteam-pr-4"

    payload = json.loads((handoff_dir / "handoff.json").read_text(encoding="utf-8"))
    assert payload["resume_command"] == "claude --resume /pr-converge"
    assert payload["phase"] == "tick"
    assert payload["run_id"] == "wf_abc123"
    assert payload["completed_steps"] == ["preflight", "audit"]
    assert payload["timestamp"] == _FROZEN_TIMESTAMP

    markdown = (handoff_dir / "HANDOFF.md").read_text(encoding="utf-8")
    assert "claude --resume /pr-converge" in markdown
    assert "preflight" in markdown
    assert "Copilot wait-gate still open." in markdown


def test_write_handoff_copies_state_file_when_given(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A supplied --state-file is copied to state-copy.json and the copy path is
    recorded in handoff.json."""
    _point_base_dir_at(monkeypatch, tmp_path)
    source_state = tmp_path / "loop-state.json"
    source_state.write_text('{"loop_count": 3}', encoding="utf-8")

    handoff_dir = write_handoff.write_handoff(
        pr_number=4,
        head_ref="feat/branch",
        phase="teardown",
        resume_command="claude --resume /autoconverge",
        state_file=source_state,
    )

    state_copy = handoff_dir / "state-copy.json"
    assert json.loads(state_copy.read_text(encoding="utf-8")) == {"loop_count": 3}
    payload = json.loads((handoff_dir / "handoff.json").read_text(encoding="utf-8"))
    assert payload["state_file"] == state_copy.as_posix()


def test_write_handoff_omits_state_copy_when_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no --state-file, no state-copy.json is written and state_file is null."""
    _point_base_dir_at(monkeypatch, tmp_path)
    handoff_dir = write_handoff.write_handoff(
        pr_number=4,
        head_ref="feat/branch",
        phase="tick",
        resume_command="claude --resume /pr-converge",
    )
    assert not (handoff_dir / "state-copy.json").exists()
    payload = json.loads((handoff_dir / "handoff.json").read_text(encoding="utf-8"))
    assert payload["state_file"] is None


def test_parse_arguments_reads_completed_steps_value() -> None:
    """The CLI captures the raw comma-separated --completed-steps value."""
    arguments = write_handoff.parse_arguments(
        [
            "--pr-number",
            "4",
            "--head-ref",
            "feat/branch",
            "--phase",
            "tick",
            "--resume-command",
            "claude --resume /pr-converge",
            "--completed-steps",
            "preflight,audit,fix",
        ]
    )
    assert arguments.completed_steps == "preflight,audit,fix"


def test_main_writes_handoff_and_prints_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """main writes the handoff files and prints the durable directory path."""
    _point_base_dir_at(monkeypatch, tmp_path)
    exit_code = write_handoff.main(
        [
            "--pr-number",
            "4",
            "--head-ref",
            "feat/branch",
            "--phase",
            "tick",
            "--resume-command",
            "claude --resume /pr-converge",
            "--completed-steps",
            "preflight,audit",
        ]
    )
    assert exit_code == 0
    printed = capsys.readouterr().out.strip()
    assert "\\" not in printed
    assert printed.endswith("bugteam-pr-4")
    payload = json.loads(
        (tmp_path / "bugteam-pr-4" / "handoff.json").read_text(encoding="utf-8")
    )
    assert payload["completed_steps"] == ["preflight", "audit"]
