"""Behavior tests for the non-breaking-finding follow-up ledger."""

import json
import sys
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from followup_ledger import (
    FollowupFinding,
    all_recorded_findings,
    followup_ledger_path,
    record_followup_finding,
)


def test_record_followup_finding_appends_one_readable_record(tmp_path: Path) -> None:
    finding = FollowupFinding(
        rule_id="instruction-filename",
        file_path="docs/Claude.md",
        message="Use the canonical filename: docs/Claude.md",
    )

    record_followup_finding(tmp_path, finding)

    assert all_recorded_findings(tmp_path) == (finding,)


def test_record_followup_finding_keeps_distinct_findings_apart(tmp_path: Path) -> None:
    first = FollowupFinding("instruction-filename", "docs/Claude.md", "wrong name")
    second = FollowupFinding("instruction-mode", "docs/AGENTS.md", "wrong mode")

    record_followup_finding(tmp_path, first)
    record_followup_finding(tmp_path, second)

    assert all_recorded_findings(tmp_path) == (first, second)


def test_record_followup_finding_records_a_repeat_once(tmp_path: Path) -> None:
    finding = FollowupFinding("instruction-mode", "docs/AGENTS.md", "wrong mode")

    record_followup_finding(tmp_path, finding)
    record_followup_finding(tmp_path, finding)

    assert all_recorded_findings(tmp_path) == (finding,)


def test_all_recorded_findings_is_empty_without_a_ledger(tmp_path: Path) -> None:
    assert all_recorded_findings(tmp_path) == ()


def test_all_recorded_findings_skips_an_unreadable_line(tmp_path: Path) -> None:
    finding = FollowupFinding("instruction-mode", "docs/AGENTS.md", "wrong mode")
    record_followup_finding(tmp_path, finding)
    ledger_path = followup_ledger_path(tmp_path)
    with ledger_path.open("a", encoding="utf-8") as ledger_file:
        ledger_file.write("{ not json\n")

    assert all_recorded_findings(tmp_path) == (finding,)


def test_record_followup_finding_writes_one_json_object_per_line(tmp_path: Path) -> None:
    record_followup_finding(
        tmp_path, FollowupFinding("instruction-mode", "docs/AGENTS.md", "wrong mode")
    )

    all_lines = followup_ledger_path(tmp_path).read_text(encoding="utf-8").splitlines()

    assert len(all_lines) == 1
    assert json.loads(all_lines[0])["rule_id"] == "instruction-mode"


def test_record_followup_finding_swallows_a_write_failure(tmp_path: Path) -> None:
    blocking_file = tmp_path / ".claude"
    blocking_file.write_text("not a directory", encoding="utf-8")

    record_followup_finding(
        tmp_path, FollowupFinding("instruction-mode", "docs/AGENTS.md", "wrong mode")
    )

    assert all_recorded_findings(tmp_path) == ()
