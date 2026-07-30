"""Named constants for the collect-then-filter finding pipeline.

::

    collect_findings([...low-severity finding...])
        ok: collection keeps every seeded severity including low and nit
    filter_findings_by_severity(collection, minimum_severity="medium")
        ok: consumer stage drops lower severities; collection record is unchanged
"""

from __future__ import annotations

COLLECTION_STAGE_NAME: str = "collection"
"""Stage that retains every real finding with its evidence fields."""

FILTER_STAGE_NAME: str = "severity_filter"
"""Later consumer stage that may drop findings by severity for action."""

FINDING_FIELD_FILE: str = "file"
FINDING_FIELD_LINE: str = "line"
FINDING_FIELD_SEVERITY: str = "severity"
FINDING_FIELD_CATEGORY: str = "category"
FINDING_FIELD_EVIDENCE: str = "evidence"

SEVERITY_BLOCKER: str = "blocker"
SEVERITY_HIGH: str = "high"
SEVERITY_MEDIUM: str = "medium"
SEVERITY_LOW: str = "low"
SEVERITY_NIT: str = "nit"

ALL_COLLECTION_SEVERITIES: tuple[str, ...] = (
    SEVERITY_BLOCKER,
    SEVERITY_HIGH,
    SEVERITY_MEDIUM,
    SEVERITY_LOW,
    SEVERITY_NIT,
)
"""Severity tokens collection accepts without dropping any real finding."""

ALL_SEVERITY_RANK_BY_TOKEN: dict[str, int] = {
    SEVERITY_BLOCKER: 5,
    SEVERITY_HIGH: 4,
    SEVERITY_MEDIUM: 3,
    SEVERITY_LOW: 2,
    SEVERITY_NIT: 1,
}
"""Higher rank is more severe; used only by the filter stage."""

REPORT_EVERY_FINDING_INSTRUCTION: str = (
    "Report every real finding. Collection retains all severities "
    f"({', '.join(ALL_COLLECTION_SEVERITIES)}). Do not drop findings "
    "by severity during collection; severity or action filtering is a "
    "separate consumer stage after the collection record is complete."
)
"""Reviewer-prompt instruction that separates collection from filtering."""
