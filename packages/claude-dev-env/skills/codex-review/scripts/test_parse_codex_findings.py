"""Behavioral tests for the Codex findings parser."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import parse_codex_findings as parser  # noqa: E402

FIXTURES_DIRECTORY = SCRIPTS_DIRECTORY / "fixtures"


def _read_fixture(fixture_name: str) -> str:
    return (FIXTURES_DIRECTORY / fixture_name).read_text(encoding="utf-8")


def test_parses_structured_fenced_json_findings() -> None:
    reviewer_text = _read_fixture("structured_findings.txt")

    all_findings = parser.parse_codex_findings(reviewer_text)

    assert len(all_findings) == 1
    finding = all_findings[0]
    assert finding.title == "Restore empty-input handling"
    assert finding.priority == "P1"
    assert finding.file == "src/stats.py"
    assert finding.line_range == "2-2"
    assert "Divides by zero" in finding.body
    assert finding.structured is True


def test_parses_empty_structured_array_as_no_findings() -> None:
    reviewer_text = "Clean review.\n\n```json\n[]\n```\n"

    all_findings = parser.parse_codex_findings(reviewer_text)

    assert all_findings == []


def test_parses_observed_freeform_finding_shape() -> None:
    reviewer_text = _read_fixture("freeform_findings_v0.144.3.txt")

    all_findings = parser.parse_codex_findings(reviewer_text)

    assert len(all_findings) == 1
    finding = all_findings[0]
    assert finding.title == "Restore empty-input handling"
    assert finding.priority == "P1"
    assert finding.file == "src/stats.py"
    assert finding.line_range == "2-2"
    assert "ZeroDivisionError" in finding.body
    assert finding.structured is False


def test_floor_yields_one_unstructured_finding_for_nonempty_text() -> None:
    reviewer_text = "Reviewer noted a concern without bullets or JSON."

    all_findings = parser.parse_codex_findings(reviewer_text)

    assert len(all_findings) == 1
    finding = all_findings[0]
    assert finding.body == reviewer_text
    assert finding.structured is False
    assert finding.title == ""
    assert finding.priority == ""
    assert finding.file == ""
    assert finding.line_range == ""


def test_empty_reviewer_text_yields_no_findings() -> None:
    assert parser.parse_codex_findings("") == []
    assert parser.parse_codex_findings("   \n\t  ") == []


def test_invalid_fenced_json_falls_through_to_floor() -> None:
    reviewer_text = "Partial reply.\n\n```json\n{not-json\n```\n"

    all_findings = parser.parse_codex_findings(reviewer_text)

    assert len(all_findings) == 1
    assert all_findings[0].structured is False
    assert "Partial reply" in all_findings[0].body


def test_fenced_json_array_of_non_dicts_falls_through_to_floor() -> None:
    reviewer_text = 'Garbage payload.\n\n```json\n["not","objects"]\n```\n'

    all_findings = parser.parse_codex_findings(reviewer_text)

    assert len(all_findings) >= 1
    assert all(each_finding.structured is False for each_finding in all_findings)
    assert any("Garbage payload" in each_finding.body for each_finding in all_findings)


def test_fenced_json_array_of_non_dicts_with_freeform_bullet_yields_freeform() -> None:
    reviewer_text = (
        'Intro text.\n\n```json\n["not","objects"]\n```\n\n'
        "- [P1] Restore empty-input handling — src/stats.py:2-2\n"
        "  Divides by zero on empty input.\n"
    )

    all_findings = parser.parse_codex_findings(reviewer_text)

    assert len(all_findings) == 1
    finding = all_findings[0]
    assert finding.structured is False
    assert finding.title == "Restore empty-input handling"
    assert finding.priority == "P1"
    assert finding.file == "src/stats.py"
    assert "Divides by zero" in finding.body
