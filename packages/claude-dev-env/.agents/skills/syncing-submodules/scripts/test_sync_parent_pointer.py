from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPT_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIRECTORY))

import sync_parent_pointer
from submodule_sync import SyncReport, SyncStatus


def _read_single_json_line(
    capsys: pytest.CaptureFixture[str],
) -> tuple[dict[str, object], str]:
    captured_streams = capsys.readouterr()
    all_stdout_lines = captured_streams.out.splitlines()
    assert len(all_stdout_lines) == 1
    parsed_record = json.loads(all_stdout_lines[0])
    assert isinstance(parsed_record, dict)
    return parsed_record, captured_streams.err


def test_invalid_repository_emits_one_json_record_and_diagnostic(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = sync_parent_pointer.main(["--repository", str(tmp_path / "missing")])

    sync_record, captured_error = _read_single_json_line(capsys)
    assert exit_code == 1
    assert sync_record["status"] == "error"
    assert sync_record["diagnostic"]
    assert "syncing-submodules:" in captured_error


def test_invalid_arguments_emit_one_json_record_and_exit_two(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = sync_parent_pointer.main(["--unknown"])

    sync_record, captured_error = _read_single_json_line(capsys)
    assert exit_code == 2
    assert sync_record["status"] == "error"
    assert "invalid command arguments" in str(sync_record["diagnostic"])
    assert captured_error


def test_success_emits_one_json_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    expected_report = SyncReport(
        status=SyncStatus.NOT_SUBMODULE,
        repository=tmp_path.as_posix(),
    )

    def return_expected_report(repository: Path) -> SyncReport:
        return expected_report

    monkeypatch.setattr(
        sync_parent_pointer,
        "sync_repository",
        return_expected_report,
    )
    exit_code = sync_parent_pointer.main(["--repository", str(tmp_path)])

    sync_record, captured_error = _read_single_json_line(capsys)
    assert exit_code == 0
    assert sync_record["status"] == "not_submodule"
    assert captured_error == ""


def test_native_post_commit_source_and_test_are_removed() -> None:
    hook_directory = Path(__file__).resolve().parents[4] / "hooks" / "git-hooks"

    assert not (hook_directory / "post_commit.py").exists()
    assert not (hook_directory / "test_post_commit.py").exists()
