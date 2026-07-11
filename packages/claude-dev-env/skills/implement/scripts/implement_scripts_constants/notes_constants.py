"""Configuration for the implementation-notes append script."""

from __future__ import annotations

HEADING_BY_SLUG: dict[str, str] = {
    "decisions": "Design decisions",
    "deviations": "Deviations",
    "tradeoffs": "Tradeoffs",
    "questions": "Open questions",
}

DEFAULT_NOTES_FILENAME = "implementation-notes.html"
