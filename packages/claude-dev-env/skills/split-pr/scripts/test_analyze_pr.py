"""Boundary tests for the 199/200/599/600 hand-written line gates."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from analyze_pr import _fetch_pr_files, build_analysis_from_files
from config.split_pr_constants import (
    DEFAULT_SPLIT_HAND_WRITTEN_LINE_THRESHOLD,
    EXIT_CODE_SUCCESS,
    FILE_KEY_ADDITIONS,
    FILE_KEY_DELETIONS,
    FILE_KEY_PATH,
    GH_VIEW,
    PAYLOAD_KEY_ATOMIC_EXCEPTION,
    PAYLOAD_KEY_DEFAULT_SPLIT,
    PAYLOAD_KEY_EXCLUDED_CHURN_LINES,
    PAYLOAD_KEY_FILE_COUNT,
    PAYLOAD_KEY_HAND_WRITTEN_LINES,
    PAYLOAD_KEY_REQUIRES_SPLIT_ANALYSIS,
    SPLIT_ANALYSIS_HAND_WRITTEN_LINE_THRESHOLD,
)


def _records_for_hand_written_lines(line_count: int) -> list[dict[str, object]]:
    return [
        {
            FILE_KEY_PATH: "src/module.py",
            FILE_KEY_ADDITIONS: line_count,
            FILE_KEY_DELETIONS: 0,
        }
    ]


def test_hand_written_199_does_not_require_split_analysis() -> None:
    analysis = build_analysis_from_files(
        _records_for_hand_written_lines(
            SPLIT_ANALYSIS_HAND_WRITTEN_LINE_THRESHOLD - 1
        )
    )
    assert analysis[PAYLOAD_KEY_HAND_WRITTEN_LINES] == 199
    assert analysis[PAYLOAD_KEY_REQUIRES_SPLIT_ANALYSIS] is False
    assert analysis[PAYLOAD_KEY_DEFAULT_SPLIT] is False


def test_hand_written_200_requires_recorded_split_analysis() -> None:
    analysis = build_analysis_from_files(
        _records_for_hand_written_lines(SPLIT_ANALYSIS_HAND_WRITTEN_LINE_THRESHOLD)
    )
    assert analysis[PAYLOAD_KEY_HAND_WRITTEN_LINES] == 200
    assert analysis[PAYLOAD_KEY_REQUIRES_SPLIT_ANALYSIS] is True
    assert analysis[PAYLOAD_KEY_DEFAULT_SPLIT] is False


def test_hand_written_599_requires_analysis_but_not_default_split() -> None:
    analysis = build_analysis_from_files(
        _records_for_hand_written_lines(
            DEFAULT_SPLIT_HAND_WRITTEN_LINE_THRESHOLD - 1
        )
    )
    assert analysis[PAYLOAD_KEY_HAND_WRITTEN_LINES] == 599
    assert analysis[PAYLOAD_KEY_REQUIRES_SPLIT_ANALYSIS] is True
    assert analysis[PAYLOAD_KEY_DEFAULT_SPLIT] is False


def test_hand_written_600_defaults_to_multiple_slices() -> None:
    analysis = build_analysis_from_files(
        _records_for_hand_written_lines(DEFAULT_SPLIT_HAND_WRITTEN_LINE_THRESHOLD)
    )
    assert analysis[PAYLOAD_KEY_HAND_WRITTEN_LINES] == 600
    assert analysis[PAYLOAD_KEY_REQUIRES_SPLIT_ANALYSIS] is True
    assert analysis[PAYLOAD_KEY_DEFAULT_SPLIT] is True


def test_atomic_exception_records_reason_and_fable_verdict() -> None:
    analysis = build_analysis_from_files(
        _records_for_hand_written_lines(DEFAULT_SPLIT_HAND_WRITTEN_LINE_THRESHOLD),
        atomic_exception_reason="single schema migration cannot be sliced",
        fable_verdict="ENDORSE",
    )
    assert analysis[PAYLOAD_KEY_DEFAULT_SPLIT] is False
    atomic = analysis[PAYLOAD_KEY_ATOMIC_EXCEPTION]
    assert isinstance(atomic, dict)
    assert atomic["reason"] == "single schema migration cannot be sliced"
    assert atomic["fable_verdict"] == "ENDORSE"


def test_atomic_exception_without_fable_verdict_is_rejected() -> None:
    with pytest.raises(ValueError, match="Fable verdict"):
        build_analysis_from_files(
            _records_for_hand_written_lines(
                DEFAULT_SPLIT_HAND_WRITTEN_LINE_THRESHOLD
            ),
            atomic_exception_reason="cannot split",
        )


def test_excluded_churn_does_not_inflate_hand_written_threshold() -> None:
    analysis = build_analysis_from_files(
        [
            {
                FILE_KEY_PATH: "src/a.py",
                FILE_KEY_ADDITIONS: 50,
                FILE_KEY_DELETIONS: 0,
            },
            {
                FILE_KEY_PATH: "package-lock.json",
                FILE_KEY_ADDITIONS: 5000,
                FILE_KEY_DELETIONS: 0,
            },
        ]
    )
    assert analysis[PAYLOAD_KEY_HAND_WRITTEN_LINES] == 50
    assert analysis[PAYLOAD_KEY_EXCLUDED_CHURN_LINES] == 5000
    assert analysis[PAYLOAD_KEY_REQUIRES_SPLIT_ANALYSIS] is False
    assert analysis[PAYLOAD_KEY_FILE_COUNT] == 2


def test_file_count_is_reported_but_not_a_hard_gate() -> None:
    analysis = build_analysis_from_files(
        [
            {
                FILE_KEY_PATH: f"src/file_{each_index}.py",
                FILE_KEY_ADDITIONS: 1,
                FILE_KEY_DELETIONS: 0,
            }
            for each_index in range(20)
        ]
    )
    assert analysis[PAYLOAD_KEY_FILE_COUNT] == 20
    assert analysis[PAYLOAD_KEY_HAND_WRITTEN_LINES] == 20
    assert analysis[PAYLOAD_KEY_REQUIRES_SPLIT_ANALYSIS] is False


def test_fetch_pr_files_invokes_gh_pr_view(monkeypatch: pytest.MonkeyPatch) -> None:
    all_captured_commands: list[list[str]] = []

    def _fake_run(all_command: list[str], **_kwargs: object) -> object:
        all_captured_commands.append(list(all_command))

        class _Completed:
            returncode = EXIT_CODE_SUCCESS
            stdout = json.dumps(
                {
                    "files": [
                        {"path": "src/a.py", "additions": 3, "deletions": 1},
                    ]
                }
            )
            stderr = ""

        return _Completed()

    monkeypatch.setattr("analyze_pr.subprocess.run", _fake_run)
    all_records = _fetch_pr_files(898, "jl-cmd/claude-dev-env")
    assert len(all_captured_commands) == 1
    assert GH_VIEW in all_captured_commands[0]
    assert all_captured_commands[0][:3] == ["gh", "pr", "view"]
    assert all_records[0][FILE_KEY_PATH] == "src/a.py"
    assert all_records[0][FILE_KEY_ADDITIONS] == 3
    assert all_records[0][FILE_KEY_DELETIONS] == 1


def test_analyze_pr_cli_files_json(tmp_path: Path) -> None:
    files_path = tmp_path / "files.json"
    files_path.write_text(
        json.dumps(
            [
                {"path": "src/a.py", "additions": 200, "deletions": 0},
                {"path": "yarn.lock", "additions": 900, "deletions": 0},
            ]
        ),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [
            sys.executable,
            str(_SCRIPTS_DIR / "analyze_pr.py"),
            "--files-json",
            str(files_path),
            "--pretty",
        ],
        cwd=str(_SCRIPTS_DIR),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == EXIT_CODE_SUCCESS, completed.stderr
    analysis = json.loads(completed.stdout)
    assert analysis[PAYLOAD_KEY_HAND_WRITTEN_LINES] == 200
    assert analysis[PAYLOAD_KEY_EXCLUDED_CHURN_LINES] == 900
    assert analysis[PAYLOAD_KEY_REQUIRES_SPLIT_ANALYSIS] is True
