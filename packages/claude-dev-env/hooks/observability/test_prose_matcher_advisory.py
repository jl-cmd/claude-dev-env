"""Tests for prose matcher advisory telemetry and precision classification."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.prose_matcher_precision_constants import (  # noqa: E402
    CLASSIFICATION_ADVISORY,
    CLASSIFICATION_DROP,
    CLASSIFICATION_KEEP,
    CLASSIFICATION_NARROW,
    DECISION_FALSE_POSITIVE,
    DECISION_TRUE_POSITIVE,
    DECISION_UNLABELED,
    MATCHER_ID_HEDGING_WORD,
    MATCHER_ID_PLAIN_LANGUAGE_HEAVY_WORD,
    SAMPLE_FLOOR_PER_MATCHER,
)
from observability.prose_matcher_advisory import (  # noqa: E402
    build_candidate_record,
    classify_all_known_matchers,
    classify_matcher,
    context_fingerprint,
    emit_advisory_candidate,
)


def test_context_fingerprint_is_stable_and_not_raw_text() -> None:
    fingerprint = context_fingerprint("utilize the cache layer now")
    assert fingerprint == context_fingerprint("utilize the cache layer now")
    assert "utilize" not in fingerprint
    assert len(fingerprint) == 16


def test_build_candidate_record_rejects_unknown_matcher() -> None:
    with pytest.raises(ValueError, match="unknown matcher"):
        build_candidate_record("unknown", "Write", "snippet")


def test_emit_advisory_candidate_writes_privacy_safe_jsonl(tmp_path: Path) -> None:
    record = emit_advisory_candidate(
        MATCHER_ID_PLAIN_LANGUAGE_HEAVY_WORD,
        "Write",
        "Please utilize the cache",
        home_directory=tmp_path,
    )
    assert record["matcher_id"] == MATCHER_ID_PLAIN_LANGUAGE_HEAVY_WORD
    assert record["surface"] == "Write"
    assert "utilize" not in json.dumps(record)
    log_path = tmp_path / ".claude" / "logs" / "prose-matcher-advisory.jsonl"
    assert log_path.is_file()
    logged = json.loads(log_path.read_text(encoding="utf-8").strip())
    assert logged["context_fingerprint"] == record["context_fingerprint"]
    assert logged["decision"] == DECISION_UNLABELED


def test_below_sample_floor_remains_advisory() -> None:
    all_candidates = [
        {
            "matcher_id": MATCHER_ID_HEDGING_WORD,
            "decision": DECISION_TRUE_POSITIVE,
        }
        for _ in range(SAMPLE_FLOOR_PER_MATCHER - 1)
    ]
    classification = classify_matcher(all_candidates)
    assert classification["status"] == CLASSIFICATION_ADVISORY
    assert classification["restart_observation_window"] is False


def test_keep_when_precision_meets_floor() -> None:
    all_candidates = [
        {"decision": DECISION_TRUE_POSITIVE}
        for _ in range(SAMPLE_FLOOR_PER_MATCHER)
    ]
    classification = classify_matcher(all_candidates)
    assert classification["status"] == CLASSIFICATION_KEEP
    assert classification["precision"] == 1.0
    assert classification["restart_observation_window"] is False


def test_narrow_restarts_observation_window() -> None:
    all_candidates = (
        [{"decision": DECISION_TRUE_POSITIVE} for _ in range(15)]
        + [{"decision": DECISION_FALSE_POSITIVE} for _ in range(15)]
    )
    classification = classify_matcher(all_candidates)
    assert classification["status"] == CLASSIFICATION_NARROW
    assert classification["restart_observation_window"] is True


def test_drop_when_precision_below_narrow_floor() -> None:
    all_candidates = (
        [{"decision": DECISION_TRUE_POSITIVE} for _ in range(5)]
        + [{"decision": DECISION_FALSE_POSITIVE} for _ in range(25)]
    )
    classification = classify_matcher(all_candidates)
    assert classification["status"] == CLASSIFICATION_DROP
    assert classification["restart_observation_window"] is False


def test_classify_all_known_matchers_covers_each_matcher() -> None:
    all_candidates = [
        {
            "matcher_id": MATCHER_ID_PLAIN_LANGUAGE_HEAVY_WORD,
            "decision": DECISION_TRUE_POSITIVE,
        }
    ]
    classification_by_matcher = classify_all_known_matchers(all_candidates)
    assert set(classification_by_matcher) == {
        MATCHER_ID_PLAIN_LANGUAGE_HEAVY_WORD,
        MATCHER_ID_HEDGING_WORD,
    }
    assert (
        classification_by_matcher[MATCHER_ID_PLAIN_LANGUAGE_HEAVY_WORD]["status"]
        == CLASSIFICATION_ADVISORY
    )
    assert (
        classification_by_matcher[MATCHER_ID_HEDGING_WORD]["status"]
        == CLASSIFICATION_ADVISORY
    )


def test_classification_never_returns_hard_block_status() -> None:
    all_candidates = [
        {"decision": DECISION_TRUE_POSITIVE}
        for _ in range(SAMPLE_FLOOR_PER_MATCHER)
    ]
    classification = classify_matcher(all_candidates)
    assert classification["status"] in {
        CLASSIFICATION_KEEP,
        CLASSIFICATION_NARROW,
        CLASSIFICATION_DROP,
        CLASSIFICATION_ADVISORY,
    }
    assert "block" not in str(classification["status"]).lower()
