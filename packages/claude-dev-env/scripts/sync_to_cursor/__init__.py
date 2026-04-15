"""Sync Claude ~/.claude rules and docs into Cursor .cursor layout."""

from sync_to_cursor.constants import (
    CANONICAL_DOC_FILES,
    GENERATOR_VERSION,
    HEADER,
    MAX_RULE_BODY_LINES,
    TEST_GLOBS,
)
from sync_to_cursor.canonical_docs import sync_canonical_docs as _sync_canonical_docs
from sync_to_cursor.rules import _limit_lines, merge_code_standards, merge_test_quality

__all__ = [
    "CANONICAL_DOC_FILES",
    "GENERATOR_VERSION",
    "HEADER",
    "MAX_RULE_BODY_LINES",
    "TEST_GLOBS",
    "_limit_lines",
    "_sync_canonical_docs",
    "merge_code_standards",
    "merge_test_quality",
]
