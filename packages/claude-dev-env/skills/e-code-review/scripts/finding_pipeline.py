"""Collect every real review finding; filter severity only later.

::

    collection = collect_findings(all_seeded)
        ok: low and nit findings remain in the collection record
    filtered = filter_findings_by_severity(collection, minimum_severity="medium")
        ok: consumer stage drops lower severities; collection is unchanged

Collection never drops a real finding by severity. A later consumer stage
reads the complete collection and may filter for action or display.
"""

from __future__ import annotations

from dataclasses import dataclass

from config.finding_pipeline_constants import (
    ALL_COLLECTION_SEVERITIES,
    COLLECTION_STAGE_NAME,
    FILTER_STAGE_NAME,
    FINDING_FIELD_CATEGORY,
    FINDING_FIELD_EVIDENCE,
    FINDING_FIELD_FILE,
    FINDING_FIELD_LINE,
    FINDING_FIELD_SEVERITY,
    SEVERITY_RANK_BY_TOKEN,
)


@dataclass(frozen=True)
class CollectedFinding:
    """One real finding retained during the collection stage."""

    file_path: str
    line_number: int
    severity: str
    category: str
    evidence: str

    def as_mapping(self) -> dict[str, str | int]:
        """Return the stable field map every retained finding keeps.

        Returns:
            Mapping with file, line, severity, category, and evidence.
        """
        return {
            FINDING_FIELD_FILE: self.file_path,
            FINDING_FIELD_LINE: self.line_number,
            FINDING_FIELD_SEVERITY: self.severity,
            FINDING_FIELD_CATEGORY: self.category,
            FINDING_FIELD_EVIDENCE: self.evidence,
        }


@dataclass(frozen=True)
class FindingCollection:
    """Unfiltered collection record of every real finding."""

    stage_name: str
    all_findings: tuple[CollectedFinding, ...]


@dataclass(frozen=True)
class SeverityFilterView:
    """Severity-filtered view produced by a separate consumer stage."""

    stage_name: str
    minimum_severity: str
    all_findings: tuple[CollectedFinding, ...]


def collect_findings(
    all_findings: list[CollectedFinding] | tuple[CollectedFinding, ...],
) -> FindingCollection:
    """Retain every real finding with its file, line, evidence, and category.

    Args:
        all_findings: Seeded real findings of any legal severity.

    Returns:
        Collection stage record holding every input finding.

    Raises:
        ValueError: When a finding lacks a required field or legal severity.
    """
    all_retained: list[CollectedFinding] = []
    for each_finding in all_findings:
        if not each_finding.file_path:
            raise ValueError("finding requires a non-empty file path")
        if each_finding.line_number < 1:
            raise ValueError("finding requires a positive line number")
        if not each_finding.category:
            raise ValueError("finding requires a non-empty category")
        if not each_finding.evidence:
            raise ValueError("finding requires non-empty evidence")
        if each_finding.severity not in ALL_COLLECTION_SEVERITIES:
            raise ValueError(
                f"unknown collection severity: {each_finding.severity!r}"
            )
        all_retained.append(each_finding)
    return FindingCollection(
        stage_name=COLLECTION_STAGE_NAME,
        all_findings=tuple(all_retained),
    )


def filter_findings_by_severity(
    collection: FindingCollection,
    *,
    minimum_severity: str,
) -> SeverityFilterView:
    """Filter a complete collection by severity in a separate consumer stage.

    Args:
        collection: Unfiltered collection record from ``collect_findings``.
        minimum_severity: Lowest severity to keep (inclusive).

    Returns:
        Filter-stage view. The input collection record is not mutated.

    Raises:
        ValueError: When ``minimum_severity`` is not a known severity token.
    """
    if minimum_severity not in SEVERITY_RANK_BY_TOKEN:
        raise ValueError(f"unknown minimum severity: {minimum_severity!r}")
    minimum_rank = SEVERITY_RANK_BY_TOKEN[minimum_severity]
    all_kept = tuple(
        each_finding
        for each_finding in collection.all_findings
        if SEVERITY_RANK_BY_TOKEN[each_finding.severity] >= minimum_rank
    )
    return SeverityFilterView(
        stage_name=FILTER_STAGE_NAME,
        minimum_severity=minimum_severity,
        all_findings=all_kept,
    )
