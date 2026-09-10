"""Unit tests for refactor_guard's MultiEdit reconstruction, run in-process.

test_refactor_guard_advisory.py and test_refactor_guard_eligibility.py already
cover this hook end to end through real git fixtures; these tests exercise
``_multi_edit_refactor_advisory_description`` directly against a target path
outside any git repository, where the underlying git commands fail closed and
return no added lines, so a qualifying rename is eligible without fixture setup.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

try:
    _ADVISORY_DIRECTORY = Path(__file__).resolve().parent
    if str(_ADVISORY_DIRECTORY) not in sys.path:
        sys.path.insert(0, str(_ADVISORY_DIRECTORY))

    import refactor_guard
except ImportError as import_error:
    raise ImportError(
        "test_refactor_guard: cannot import its sibling modules; "
        "ensure the advisory directory is importable."
    ) from import_error


WINDOWS_NO_WINDOW_FLAG = 0x08000000
EXPECTED_HIDDEN_WINDOW_FLAGS = WINDOWS_NO_WINDOW_FLAG if sys.platform == "win32" else 0


def _multi_edit_payload(file_path: str, all_edits: list[dict[str, str]]) -> dict[str, object]:
    return {
        "tool_name": "MultiEdit",
        "tool_input": {"file_path": file_path, "edits": all_edits},
    }


def test_multi_edit_reports_the_first_eligible_rename(tmp_path: Path) -> None:
    """A rename in the second edit is reported, even though the first edit is ordinary."""
    target_path = str(tmp_path / "module.py")
    payload = _multi_edit_payload(
        target_path,
        [
            {"old_string": "return amount", "new_string": "return amount + 1"},
            {
                "old_string": "def calculate_total(amount):\n    return amount",
                "new_string": "def compute_total(amount):\n    return amount",
            },
        ],
    )

    result = refactor_guard._multi_edit_refactor_advisory_description(payload)

    assert result is not None
    reported_path, description = result
    assert reported_path == target_path
    assert "calculate_total" in description
    assert "compute_total" in description


def test_multi_edit_scans_past_two_ordinary_edits_to_the_third(tmp_path: Path) -> None:
    """The loop over edit pairs reaches the third pair, not only the first two."""
    target_path = str(tmp_path / "module.py")
    payload = _multi_edit_payload(
        target_path,
        [
            {"old_string": "return amount", "new_string": "return amount + 1"},
            {"old_string": "return amount + 1", "new_string": "return amount + 2"},
            {
                "old_string": "def calculate_total(amount):\n    return amount + 2",
                "new_string": "def compute_total(amount):\n    return amount + 2",
            },
        ],
    )

    result = refactor_guard._multi_edit_refactor_advisory_description(payload)

    assert result is not None
    _reported_path, description = result
    assert "compute_total" in description


def test_multi_edit_returns_none_when_no_edit_qualifies(tmp_path: Path) -> None:
    target_path = str(tmp_path / "module.py")
    payload = _multi_edit_payload(
        target_path,
        [{"old_string": "return amount", "new_string": "return amount + 1"}],
    )

    assert refactor_guard._multi_edit_refactor_advisory_description(payload) is None


def _record_creation_flags(
    monkeypatch: pytest.MonkeyPatch, standard_output: str
) -> dict[str, object]:
    all_recorded_keyword_arguments: dict[str, object] = {}

    def _record(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        del args
        all_recorded_keyword_arguments.update(kwargs)
        return subprocess.CompletedProcess([], 0, stdout=standard_output, stderr="")

    monkeypatch.setattr(refactor_guard.subprocess, "run", _record)
    return all_recorded_keyword_arguments


def test_git_diff_should_start_without_a_console_window(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    all_recorded_keyword_arguments = _record_creation_flags(monkeypatch, "+added line\n")

    refactor_guard.get_git_diff_added_lines(str(tmp_path / "module.py"))

    assert all_recorded_keyword_arguments["creationflags"] == EXPECTED_HIDDEN_WINDOW_FLAGS


def test_untracked_probe_should_start_without_a_console_window(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    all_recorded_keyword_arguments = _record_creation_flags(monkeypatch, "module.py\n")

    assert refactor_guard.is_new_file(str(tmp_path / "module.py")) is True
    assert all_recorded_keyword_arguments["creationflags"] == EXPECTED_HIDDEN_WINDOW_FLAGS
