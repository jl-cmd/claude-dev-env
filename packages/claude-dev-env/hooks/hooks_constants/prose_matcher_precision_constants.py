"""Thresholds and paths for prose-matcher precision measurement (OP-07B).

::

    labeled count < SAMPLE_FLOOR_PER_MATCHER  -> remain advisory
    precision >= KEEP_PRECISION_FLOOR         -> keep
    precision >= NARROW_PRECISION_FLOOR       -> narrow
    otherwise                                 -> drop

No matcher becomes hard-blocking from historical labels alone; classification
only records keep/narrow/drop/advisory for the observation window.
"""

from __future__ import annotations

ADVISORY_LOG_RELATIVE_PATH = ".claude/logs/prose-matcher-advisory.jsonl"
SAMPLE_FLOOR_PER_MATCHER = 30
KEEP_PRECISION_FLOOR = 0.7
NARROW_PRECISION_FLOOR = 0.4
MATCHER_ID_PLAIN_LANGUAGE_HEAVY_WORD = "plain_language_heavy_word"
MATCHER_ID_HEDGING_WORD = "hedging_word"
ALL_KNOWN_MATCHER_IDS = (
    MATCHER_ID_PLAIN_LANGUAGE_HEAVY_WORD,
    MATCHER_ID_HEDGING_WORD,
)
DECISION_TRUE_POSITIVE = "true_positive"
DECISION_FALSE_POSITIVE = "false_positive"
DECISION_UNLABELED = "unlabeled"
ALL_LABEL_DECISIONS = (
    DECISION_TRUE_POSITIVE,
    DECISION_FALSE_POSITIVE,
    DECISION_UNLABELED,
)
CLASSIFICATION_KEEP = "keep"
CLASSIFICATION_NARROW = "narrow"
CLASSIFICATION_DROP = "drop"
CLASSIFICATION_ADVISORY = "advisory"
CONTEXT_FINGERPRINT_HEX_LENGTH = 16
MAXIMUM_ADVISORY_EMITS_PER_CALL = 5
ADVISORY_CONTEXT_SNIPPET_MAX_CHARS = 120
