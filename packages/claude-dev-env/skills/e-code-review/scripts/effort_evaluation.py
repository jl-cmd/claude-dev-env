"""Machine-readable Opus effort evaluation for e-code-review.

Freezes easy / medium / demanding fixtures, validates evaluation rows, and
publishes a recommendation that cites completed rows. Live paid runs are
optional — offline tests feed synthetic rows through the same functions::

    load fixtures → validate rows → recommend lowest effort that holds quality

Thinking stays enabled; effort is the only planned cost and latency lever.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Mapping, MutableMapping, Sequence

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPTS_DIRECTORY / "config") not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY / "config"))
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

from e_code_review_effort_constants import (
    ALL_EFFORT_LEVELS,
    ALL_FIXTURE_BANDS,
    ALL_REQUIRED_ROW_KEYS,
    EVALUATION_SCHEMA_VERSION,
    FIXTURES_DIRECTORY_NAME,
    JSON_SUFFIX,
    LATENCY_MS_ROW_KEY,
    MINIMUM_QUALITY_HOLD_SCORE,
    THINKING_ENABLED_DEFAULT,
    VISIBLE_TOKENS_ROW_KEY,
)

def fixtures_directory() -> Path:
    """Return the frozen fixture directory next to this module.

    Returns:
        Absolute path to the fixtures directory.
    """
    return _SCRIPTS_DIRECTORY / FIXTURES_DIRECTORY_NAME


def load_fixtures() -> list[dict[str, object]]:
    """Load every JSON fixture under the fixtures directory.

    Returns:
        Fixture dicts sorted by band then fixture_id.

    Raises:
        ValueError: When a fixture file is not a JSON object.
        OSError: When a fixture file cannot be read.
        json.JSONDecodeError: When a fixture file is not valid JSON.
    """
    directory = fixtures_directory()
    all_fixtures: list[dict[str, object]] = []
    for each_path in sorted(directory.glob(f"*{JSON_SUFFIX}")):
        loaded = json.loads(each_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            raise ValueError(f"Fixture must be an object: {each_path}")
        all_fixtures.append(loaded)
    all_fixtures.sort(
        key=lambda each_fixture: (
            str(each_fixture.get("band", "")),
            str(each_fixture.get("fixture_id", "")),
        )
    )
    return all_fixtures


def validate_evaluation_row(all_row_fields: Mapping[str, object]) -> list[str]:
    """Return human-readable problems for one evaluation row.

    Args:
        all_row_fields: Candidate evaluation row mapping.

    Returns:
        Problem strings; empty when the row is valid.
    """
    all_problems: list[str] = []
    for each_key in ALL_REQUIRED_ROW_KEYS:
        if each_key not in all_row_fields:
            all_problems.append(f"missing key: {each_key}")
    if all_problems:
        return all_problems
    effort = all_row_fields["effort"]
    if effort not in ALL_EFFORT_LEVELS:
        all_problems.append(f"unknown effort: {effort!r}")
    fixture_band = all_row_fields["fixture_band"]
    if fixture_band not in ALL_FIXTURE_BANDS:
        all_problems.append(f"unknown fixture_band: {fixture_band!r}")
    if all_row_fields["thinking_enabled"] is not True:
        all_problems.append("thinking_enabled must be true on Opus paths")
    for each_score_key in ("quality_score", "finding_recall", "finding_precision"):
        score_amount = all_row_fields[each_score_key]
        if not isinstance(score_amount, (int, float)):
            all_problems.append(f"{each_score_key} must be numeric")
        elif not 0.0 <= float(score_amount) <= 1.0:
            all_problems.append(f"{each_score_key} out of range [0, 1]")
    for each_count_key in (VISIBLE_TOKENS_ROW_KEY, LATENCY_MS_ROW_KEY):
        count_amount = all_row_fields[each_count_key]
        if not isinstance(count_amount, (int, float)) or float(count_amount) < 0:
            all_problems.append(f"{each_count_key} must be a non-negative number")
    return all_problems


def quality_holds(
    all_row_fields: Mapping[str, object],
    minimum_quality: float = MINIMUM_QUALITY_HOLD_SCORE,
) -> bool:
    """Return True when quality, recall, and precision all meet the floor.

    Args:
        all_row_fields: Evaluation row mapping.
        minimum_quality: Floor for quality, recall, and precision.

    Returns:
        Whether the row holds quality at the floor.
    """
    return (
        float(all_row_fields["quality_score"]) >= minimum_quality
        and float(all_row_fields["finding_recall"]) >= minimum_quality
        and float(all_row_fields["finding_precision"]) >= minimum_quality
    )


def _lowest_holding_row(
    all_band_rows: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    all_effort_rank_by_name: Mapping[str, int] = {
        each_effort: each_index
        for each_index, each_effort in enumerate(ALL_EFFORT_LEVELS)
    }
    return sorted(
        all_band_rows,
        key=lambda each_row: all_effort_rank_by_name[str(each_row["effort"])],
    )[0]


def recommend_effort_by_band(
    all_rows: Sequence[Mapping[str, object]],
    minimum_quality: float = MINIMUM_QUALITY_HOLD_SCORE,
) -> dict[str, object]:
    """Pick the lowest effort that holds quality for each fixture band.

    Every recommendation entry cites the evaluation row that justified it.
    Bands with no holding row stay null with an explicit blocker note.

    Args:
        all_rows: Completed evaluation rows (already validated by the caller).
        minimum_quality: Floor for quality, recall, and precision.

    Returns:
        Machine-readable recommendation document.
    """
    recommendation_by_band: MutableMapping[str, object] = {}
    for each_band in ALL_FIXTURE_BANDS:
        all_holding_rows = [
            each_row
            for each_row in all_rows
            if each_row["fixture_band"] == each_band
            and quality_holds(each_row, minimum_quality)
        ]
        if not all_holding_rows:
            recommendation_by_band[each_band] = {
                "recommended_effort": None,
                "cited_row": None,
                "blocker": "no completed row meets the quality floor",
            }
            continue
        chosen_row = _lowest_holding_row(all_holding_rows)
        recommendation_by_band[each_band] = {
            "recommended_effort": chosen_row["effort"],
            "cited_row": dict(chosen_row),
            "blocker": None,
        }
    return {
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "thinking_enabled": THINKING_ENABLED_DEFAULT,
        "cost_latency_lever": "effort",
        "defaults_unchanged": True,
        "minimum_quality": minimum_quality,
        "recommendation_by_band": dict(recommendation_by_band),
    }


def build_synthetic_row(
    fixture_id: str,
    fixture_band: str,
    effort: str,
    quality_score: float,
    finding_recall: float,
    finding_precision: float,
    visible_tokens: int,
    latency_ms: int,
) -> dict[str, object]:
    """Build one evaluation row with thinking enabled.

    Args:
        fixture_id: Fixture identifier.
        fixture_band: Band name (easy / medium / demanding).
        effort: Effort level name.
        quality_score: Overall quality in [0, 1].
        finding_recall: Recall in [0, 1].
        finding_precision: Precision in [0, 1].
        visible_tokens: Visible token count.
        latency_ms: Latency in milliseconds.

    Returns:
        Complete evaluation row mapping.
    """
    return {
        "fixture_id": fixture_id,
        "fixture_band": fixture_band,
        "effort": effort,
        "quality_score": quality_score,
        "finding_recall": finding_recall,
        "finding_precision": finding_precision,
        VISIBLE_TOKENS_ROW_KEY: visible_tokens,
        LATENCY_MS_ROW_KEY: latency_ms,
        "thinking_enabled": THINKING_ENABLED_DEFAULT,
    }
