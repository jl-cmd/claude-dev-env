import sys
from pathlib import Path

import pytest

scripts_directory = str(Path(__file__).resolve().parent)
if scripts_directory not in sys.path:
    sys.path.insert(0, scripts_directory)

import toggle_step_notes


@pytest.fixture
def on_flag(monkeypatch, tmp_path):
    flag_path = tmp_path / "config" / ".step-notes-on"
    monkeypatch.setattr(toggle_step_notes, "STEP_NOTES_ON_FLAG_PATH", flag_path)
    return flag_path


def test_should_create_the_flag_when_turned_on(on_flag, capsys):
    toggle_step_notes.main(["on"])

    assert on_flag.exists()
    assert capsys.readouterr().out.strip() == toggle_step_notes.ON_REPORT


def test_should_remove_the_flag_when_turned_off(on_flag, capsys):
    on_flag.parent.mkdir(parents=True)
    on_flag.touch()

    toggle_step_notes.main(["off"])

    assert not on_flag.exists()
    assert capsys.readouterr().out.strip() == toggle_step_notes.OFF_REPORT


def test_should_flip_off_to_on_and_back_with_no_argument(on_flag):
    toggle_step_notes.main([])
    was_on_after_first_flip = on_flag.exists()
    toggle_step_notes.main([])

    assert (was_on_after_first_flip, on_flag.exists()) == (True, False)


def test_should_report_off_by_default_without_changing_the_flag(on_flag, capsys):
    toggle_step_notes.main(["status"])

    assert not on_flag.exists()
    assert capsys.readouterr().out.strip() == toggle_step_notes.OFF_REPORT
