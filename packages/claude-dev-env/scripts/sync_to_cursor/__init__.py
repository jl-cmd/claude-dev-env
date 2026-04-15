"""Sync Claude ~/.claude rules and docs into Cursor .cursor layout."""

from sync_to_cursor.config import MAX_RULE_BODY_LINES
from sync_to_cursor.canonical_docs import sync_canonical_docs as _sync_canonical_docs
from sync_to_cursor.rules import _limit_lines, merge_code_standards, merge_test_quality

__all__ = [
    "MAX_RULE_BODY_LINES",
    "_limit_lines",
    "_sync_canonical_docs",
    "merge_code_standards",
    "merge_test_quality",
]
