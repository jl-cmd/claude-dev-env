"""Privacy-safe advisory telemetry and precision classification for prose matchers.

Emits candidate records with matcher id, surface, hashed context fingerprint,
and optional human label. Classifies each matcher as keep, narrow, drop, or
remain advisory when the labeled sample floor is unmet. Never hard-blocks from
historical labels alone.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

from hooks_constants.prose_matcher_precision_constants import (
    ADVISORY_LOG_RELATIVE_PATH,
    ALL_KNOWN_MATCHER_IDS,
    ALL_LABEL_DECISIONS,
    CLASSIFICATION_ADVISORY,
    CLASSIFICATION_DROP,
    CLASSIFICATION_KEEP,
    CLASSIFICATION_NARROW,
    CONTEXT_FINGERPRINT_HEX_LENGTH,
    DECISION_FALSE_POSITIVE,
    DECISION_TRUE_POSITIVE,
    DECISION_UNLABELED,
    KEEP_PRECISION_FLOOR,
    NARROW_PRECISION_FLOOR,
    SAMPLE_FLOOR_PER_MATCHER,
)


def context_fingerprint(context_text: str) -> str:
    """Return a short hex fingerprint of context text (never the raw prose).

    Args:
        context_text: Snippet around a matcher hit.

    Returns:
        Lowercase hex digest truncated for log size.
    """
    digest = hashlib.sha256(context_text.encode("utf-8")).hexdigest()
    return digest[:CONTEXT_FINGERPRINT_HEX_LENGTH]


def build_candidate_record(
    matcher_id: str,
    surface: str,
    context_text: str,
    decision: str = DECISION_UNLABELED,
) -> dict[str, object]:
    """Build one privacy-safe advisory candidate record.

    Args:
        matcher_id: Known matcher identifier.
        surface: Tool or reply surface name.
        context_text: Local snippet used only for hashing.
        decision: Label decision (true_positive / false_positive / unlabeled).

    Returns:
        Record ready to append to the advisory JSONL log.

    Raises:
        ValueError: When matcher_id or decision is unknown.
    """
    if matcher_id not in ALL_KNOWN_MATCHER_IDS:
        raise ValueError(f"unknown matcher_id: {matcher_id!r}")
    if decision not in ALL_LABEL_DECISIONS:
        raise ValueError(f"unknown decision: {decision!r}")
    return {
        "matcher_id": matcher_id,
        "surface": surface,
        "context_fingerprint": context_fingerprint(context_text),
        "decision": decision,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }


def advisory_log_path(home_directory: Path | None = None) -> Path:
    """Return the advisory log path under the user home.

    Args:
        home_directory: Optional home override for tests.

    Returns:
        Absolute path to the JSONL log file.
    """
    home_root = home_directory if home_directory is not None else Path.home()
    return home_root / ADVISORY_LOG_RELATIVE_PATH


def emit_advisory_candidate(
    matcher_id: str,
    surface: str,
    context_text: str,
    decision: str = DECISION_UNLABELED,
    home_directory: Path | None = None,
) -> dict[str, object]:
    """Append one advisory candidate and return the record.

    Args:
        matcher_id: Known matcher identifier.
        surface: Tool or reply surface name.
        context_text: Snippet hashed into the fingerprint.
        decision: Optional label decision.
        home_directory: Optional home override for tests.

    Returns:
        The written candidate record.
    """
    candidate_record = build_candidate_record(
        matcher_id, surface, context_text, decision
    )
    log_path = advisory_log_path(home_directory)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(json.dumps(candidate_record) + "\n")
    return candidate_record


def precision_for_labeled_candidates(
    all_candidates: Sequence[Mapping[str, object]],
) -> float | None:
    """Return precision among labeled candidates, or None when none are labeled.

    Args:
        all_candidates: Candidate records for one matcher.

    Returns:
        true_positive / (true_positive + false_positive), or None when no labels.
    """
    true_positive_count = 0
    false_positive_count = 0
    for each_candidate in all_candidates:
        decision = each_candidate.get("decision")
        if decision == DECISION_TRUE_POSITIVE:
            true_positive_count += 1
        elif decision == DECISION_FALSE_POSITIVE:
            false_positive_count += 1
    labeled_count = true_positive_count + false_positive_count
    if labeled_count == 0:
        return None
    return true_positive_count / labeled_count


def classify_matcher(
    all_candidates: Sequence[Mapping[str, object]],
    sample_floor: int = SAMPLE_FLOOR_PER_MATCHER,
    keep_precision_floor: float = KEEP_PRECISION_FLOOR,
    narrow_precision_floor: float = NARROW_PRECISION_FLOOR,
) -> dict[str, object]:
    """Classify a matcher from labeled evidence.

    Args:
        all_candidates: Candidate records for one matcher.
        sample_floor: Minimum labeled count before leave advisory.
        keep_precision_floor: Precision required to keep.
        narrow_precision_floor: Precision required to narrow instead of drop.

    Returns:
        Classification record with status, labeled_count, precision, and
        whether the production observation window must restart.
    """
    labeled_count = sum(
        1
        for each_candidate in all_candidates
        if each_candidate.get("decision")
        in (DECISION_TRUE_POSITIVE, DECISION_FALSE_POSITIVE)
    )
    precision = precision_for_labeled_candidates(all_candidates)
    if labeled_count < sample_floor:
        return {
            "status": CLASSIFICATION_ADVISORY,
            "labeled_count": labeled_count,
            "precision": precision,
            "restart_observation_window": False,
            "reason": "below sample floor",
        }
    assert precision is not None
    if precision >= keep_precision_floor:
        return {
            "status": CLASSIFICATION_KEEP,
            "labeled_count": labeled_count,
            "precision": precision,
            "restart_observation_window": False,
            "reason": "meets keep precision floor",
        }
    if precision >= narrow_precision_floor:
        return {
            "status": CLASSIFICATION_NARROW,
            "labeled_count": labeled_count,
            "precision": precision,
            "restart_observation_window": True,
            "reason": "meets narrow floor; restart observation window",
        }
    return {
        "status": CLASSIFICATION_DROP,
        "labeled_count": labeled_count,
        "precision": precision,
        "restart_observation_window": False,
        "reason": "below narrow precision floor",
    }


def classify_all_known_matchers(
    all_candidates: Sequence[Mapping[str, object]],
    sample_floor: int = SAMPLE_FLOOR_PER_MATCHER,
    keep_precision_floor: float = KEEP_PRECISION_FLOOR,
    narrow_precision_floor: float = NARROW_PRECISION_FLOOR,
) -> dict[str, dict[str, object]]:
    """Classify every known matcher; missing matchers stay advisory.

    Args:
        all_candidates: Mixed candidates across matchers.
        sample_floor: Minimum labeled count before leave advisory.
        keep_precision_floor: Precision required to keep.
        narrow_precision_floor: Precision required to narrow instead of drop.

    Returns:
        Mapping of matcher_id to classification record.
    """
    classification_by_matcher: dict[str, dict[str, object]] = {}
    for each_matcher_id in ALL_KNOWN_MATCHER_IDS:
        all_matcher_candidates = [
            each_candidate
            for each_candidate in all_candidates
            if each_candidate.get("matcher_id") == each_matcher_id
        ]
        classification_by_matcher[each_matcher_id] = classify_matcher(
            all_matcher_candidates,
            sample_floor=sample_floor,
            keep_precision_floor=keep_precision_floor,
            narrow_precision_floor=narrow_precision_floor,
        )
    return classification_by_matcher
