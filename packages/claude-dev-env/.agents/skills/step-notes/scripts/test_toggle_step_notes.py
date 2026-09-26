import sys
from pathlib import Path

import pytest

scripts_directory = str(Path(__file__).resolve().parent)
if scripts_directory not in sys.path:
    sys.path.insert(0, scripts_directory)

import toggle_step_notes


@pytest.fixture
def on_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    flag_path = tmp_path / "config" / ".step-notes-on"
    monkeypatch.setattr(toggle_step_notes, "STEP_NOTES_ON_FLAG_PATH", flag_path)
    return flag_path


def run_toggle(monkeypatch: pytest.MonkeyPatch, *all_arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["toggle_step_notes.py", *all_arguments])
    toggle_step_notes.main()


def test_should_create_the_flag_when_turned_on(
    on_flag: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run_toggle(monkeypatch, "on")

    assert on_flag.exists()
    assert capsys.readouterr().out.strip() == toggle_step_notes.ON_REPORT


def test_should_remove_the_flag_when_turned_off(
    on_flag: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    on_flag.parent.mkdir(parents=True)
    on_flag.touch()

    run_toggle(monkeypatch, "off")

    assert not on_flag.exists()
    assert capsys.readouterr().out.strip() == toggle_step_notes.OFF_REPORT


def test_should_flip_off_to_on_and_back_with_no_argument(
    on_flag: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_toggle(monkeypatch)
    was_on_after_first_flip = on_flag.exists()
    run_toggle(monkeypatch)

    assert (was_on_after_first_flip, on_flag.exists()) == (True, False)


def test_should_report_off_by_default_without_changing_the_flag(
    on_flag: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run_toggle(monkeypatch, "status")

    assert not on_flag.exists()
    assert capsys.readouterr().out.strip() == toggle_step_notes.OFF_REPORT
