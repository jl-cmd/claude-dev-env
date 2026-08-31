"""Named constants for Grok medium-review discovery and verification."""

from __future__ import annotations

MEDIUM_REVIEW_SCHEMA_VERSION: str = "1.0.0"
"""Schema version for medium-review run documents."""

MEDIUM_REVIEW_FINDER_COUNT: int = 8
"""Exactly eight finder angles execute per medium review head."""

ALL_MEDIUM_FINDER_ANGLES: tuple[str, ...] = (
    "correctness",
    "security",
    "code_rules",
    "tests",
    "docs",
    "concurrency",
    "api_contracts",
    "regressions",
)
"""Named finder angles for one medium-review discovery batch."""

VERDICT_CONFIRMED: str = "CONFIRMED"
"""Verification retained a concrete failure scenario."""

VERDICT_PLAUSIBLE: str = "PLAUSIBLE"
"""Verification could not refute the finding."""

VERDICT_REFUTED: str = "REFUTED"
"""Verification rejected the finding."""

ALL_VERIFICATION_VERDICTS: frozenset[str] = frozenset(
    {VERDICT_CONFIRMED, VERDICT_PLAUSIBLE, VERDICT_REFUTED}
)
"""Legal verification verdict tokens."""

SEVERITY_BLOCKER: str = "blocker"
SEVERITY_HIGH: str = "high"
SEVERITY_MEDIUM: str = "medium"
SEVERITY_LOW: str = "low"
SEVERITY_NIT: str = "nit"

ALL_SEVERITIES: frozenset[str] = frozenset(
    {
        SEVERITY_BLOCKER,
        SEVERITY_HIGH,
        SEVERITY_MEDIUM,
        SEVERITY_LOW,
        SEVERITY_NIT,
    }
)
"""Legal severity tokens on retained findings."""

UTF8_ENCODING: str = "utf-8"
"""Text encoding for review artifacts."""
