"""Behavioral tests for the gate_running parts module."""

from pathlib import Path

import pytest
from code_rules_gate_parts import gate_running


def _clean_validate(_content: str, _path: str, _prior: str = "", **_kwargs: object) -> list[str]:
    return []


def _dirty_validate(_content: str, _path: str, _prior: str = "", **_kwargs: object) -> list[str]:
    return ["Line 1: bad"]


def test_run_gate_reports_inspected_count_for_clean_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module_path = tmp_path / "clean.py"
    module_path.write_text("value = 1\n", encoding="utf-8")

    exit_code = gate_running.run_gate(
        _clean_validate, [module_path], tmp_path, all_added_lines_by_path=None
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "inspected 1 file(s)" in captured.err


def test_run_gate_blocks_when_validate_reports_issue(tmp_path: Path) -> None:
    module_path = tmp_path / "dirty.py"
    module_path.write_text("value = 1\n", encoding="utf-8")

    exit_code = gate_running.run_gate(
        _dirty_validate, [module_path], tmp_path, all_added_lines_by_path=None
    )

    assert exit_code == 1


def test_print_violation_section_groups_by_relative_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module_path = (tmp_path / "module.py").resolve()

    gate_running.print_violation_section("HEADER", {module_path: ["Line 1: issue"]}, tmp_path)

    captured = capsys.readouterr()
    assert "HEADER" in captured.err
    assert "Line 1: issue" in captured.err
