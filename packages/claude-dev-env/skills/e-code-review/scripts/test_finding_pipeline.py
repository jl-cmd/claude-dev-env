"""Red fixtures: low-severity findings survive collection; filter is separate."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from config.finding_pipeline_constants import (
    ALL_COLLECTION_SEVERITIES,
    COLLECTION_STAGE_NAME,
    FILTER_STAGE_NAME,
    FINDING_FIELD_CATEGORY,
    FINDING_FIELD_EVIDENCE,
    FINDING_FIELD_FILE,
    FINDING_FIELD_LINE,
    FINDING_FIELD_SEVERITY,
    REPORT_EVERY_FINDING_INSTRUCTION,
    SEVERITY_BLOCKER,
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    SEVERITY_NIT,
)
from finding_pipeline import (
    CollectedFinding,
    FindingCollection,
    collect_findings,
    filter_findings_by_severity,
)


def _seeded_findings() -> list[CollectedFinding]:
    return [
        CollectedFinding(
            file_path="pkg/a.py",
            line_number=10,
            severity=SEVERITY_BLOCKER,
            category="correctness",
            evidence="raises on empty input",
        ),
        CollectedFinding(
            file_path="pkg/b.py",
            line_number=20,
            severity=SEVERITY_HIGH,
            category="security",
            evidence="shell=True with user text",
        ),
        CollectedFinding(
            file_path="pkg/c.py",
            line_number=30,
            severity=SEVERITY_MEDIUM,
            category="api-contracts",
            evidence="return type narrowed",
        ),
        CollectedFinding(
            file_path="pkg/d.py",
            line_number=40,
            severity=SEVERITY_LOW,
            category="simplification",
            evidence="duplicated helper body",
        ),
        CollectedFinding(
            file_path="pkg/e.py",
            line_number=50,
            severity=SEVERITY_NIT,
            category="conventions",
            evidence="typo in comment",
        ),
    ]


def test_collection_retains_every_seeded_severity_including_low_and_nit() -> None:
    all_seeded = _seeded_findings()
    collection = collect_findings(all_seeded)

    assert collection.stage_name == COLLECTION_STAGE_NAME
    all_severities = {
        each.severity for each in collection.all_findings
    }
    assert all_severities == set(ALL_COLLECTION_SEVERITIES)
    assert len(collection.all_findings) == len(all_seeded)
    low_finding = next(
        each for each in collection.all_findings if each.severity == SEVERITY_LOW
    )
    assert low_finding.file_path == "pkg/d.py"
    assert low_finding.line_number == 40
    assert low_finding.evidence == "duplicated helper body"
    assert low_finding.category == "simplification"


def test_each_collected_finding_keeps_file_line_evidence_and_category() -> None:
    collection = collect_findings(_seeded_findings())
    for each_finding in collection.all_findings:
        as_mapping = each_finding.as_mapping()
        assert as_mapping[FINDING_FIELD_FILE]
        assert as_mapping[FINDING_FIELD_LINE] > 0
        assert as_mapping[FINDING_FIELD_EVIDENCE]
        assert as_mapping[FINDING_FIELD_CATEGORY]
        assert as_mapping[FINDING_FIELD_SEVERITY] in ALL_COLLECTION_SEVERITIES


def test_filter_is_explicit_later_stage_and_does_not_mutate_collection() -> None:
    collection = collect_findings(_seeded_findings())
    collected_snapshot = [
        (
            each.file_path,
            each.line_number,
            each.severity,
            each.category,
            each.evidence,
        )
        for each in collection.all_findings
    ]

    filtered = filter_findings_by_severity(
        collection,
        minimum_severity=SEVERITY_MEDIUM,
    )

    assert filtered.stage_name == FILTER_STAGE_NAME
    all_filtered_severities = {each.severity for each in filtered.all_findings}
    assert SEVERITY_LOW not in all_filtered_severities
    assert SEVERITY_NIT not in all_filtered_severities
    assert SEVERITY_MEDIUM in all_filtered_severities
    assert SEVERITY_BLOCKER in all_filtered_severities

    after_filter_snapshot = [
        (
            each.file_path,
            each.line_number,
            each.severity,
            each.category,
            each.evidence,
        )
        for each in collection.all_findings
    ]
    assert after_filter_snapshot == collected_snapshot
    assert len(collection.all_findings) == 5


def test_filter_rejects_unknown_minimum_severity() -> None:
    collection = collect_findings(_seeded_findings())
    with pytest.raises(ValueError, match="unknown minimum severity"):
        filter_findings_by_severity(collection, minimum_severity="P1")


def test_filter_rejects_unknown_finding_severity_with_value_error() -> None:
    collection = FindingCollection(
        stage_name=COLLECTION_STAGE_NAME,
        all_findings=(
            CollectedFinding(
                file_path="pkg/x.py",
                line_number=1,
                severity="P0",
                category="correctness",
                evidence="bypass collect",
            ),
        ),
    )
    with pytest.raises(ValueError, match="unknown collection severity"):
        filter_findings_by_severity(collection, minimum_severity=SEVERITY_LOW)


def test_collect_rejects_finding_missing_required_fields() -> None:
    with pytest.raises(ValueError, match="file"):
        collect_findings(
            [
                CollectedFinding(
                    file_path="",
                    line_number=1,
                    severity=SEVERITY_LOW,
                    category="correctness",
                    evidence="x",
                )
            ]
        )


def test_report_every_finding_instruction_names_all_severities() -> None:
    for each_severity in ALL_COLLECTION_SEVERITIES:
        assert each_severity in REPORT_EVERY_FINDING_INSTRUCTION
    assert "consumer stage" in REPORT_EVERY_FINDING_INSTRUCTION
    assert "Do not drop findings by severity during collection" in (
        REPORT_EVERY_FINDING_INSTRUCTION
    )


def test_collection_record_type_is_immutable() -> None:
    collection = collect_findings(_seeded_findings())
    assert isinstance(collection, FindingCollection)
    assert collection.stage_name == COLLECTION_STAGE_NAME
