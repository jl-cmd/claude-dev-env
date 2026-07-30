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
    ALL_EFFORT_RANK_BY_NAME,
    ALL_FIXTURE_BANDS,
    ALL_REQUIRED_ROW_KEYS,
    ALL_SCORE_ROW_KEYS,
    ALL_SKILL_EFFORT_FOR_EVALUATION_EFFORT,
    ALL_SKILL_EFFORT_LEVELS,
    COST_LATENCY_LEVER,
    EVALUATION_EVIDENCE_FILENAME,
    EVALUATION_SCHEMA_VERSION,
    FIXTURES_DIRECTORY_NAME,
    JSON_SUFFIX,
    LATENCY_MS_ROW_KEY,
    MINIMUM_QUALITY_HOLD_SCORE,
    THINKING_ENABLED_DEFAULT,
    VISIBLE_TOKENS_ROW_KEY,
    WORKFLOW_FAMILY_E_CODE_REVIEW,
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
    for each_score_key in ALL_SCORE_ROW_KEYS:
        score_amount = all_row_fields[each_score_key]
        if isinstance(score_amount, bool) or not isinstance(score_amount, (int, float)):
            all_problems.append(f"{each_score_key} must be numeric")
        elif not 0.0 <= float(score_amount) <= 1.0:
            all_problems.append(f"{each_score_key} out of range [0, 1]")
    for each_count_key in (VISIBLE_TOKENS_ROW_KEY, LATENCY_MS_ROW_KEY):
        count_amount = all_row_fields[each_count_key]
        if (
            isinstance(count_amount, bool)
            or not isinstance(count_amount, (int, float))
            or float(count_amount) < 0
        ):
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
    return all(
        float(all_row_fields[each_score_key]) >= minimum_quality
        for each_score_key in ALL_SCORE_ROW_KEYS
    )


def _lowest_holding_row(
    all_band_rows: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    return min(
        all_band_rows,
        key=lambda each_row: ALL_EFFORT_RANK_BY_NAME[str(each_row["effort"])],
    )


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
        "cost_latency_lever": COST_LATENCY_LEVER,
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


def evaluation_evidence_path() -> Path:
    """Return the committed evaluation evidence file path.

    Returns:
        Path to ``effort_defaults_evidence.json`` beside this module.
    """
    return _SCRIPTS_DIRECTORY / EVALUATION_EVIDENCE_FILENAME


def load_evaluation_evidence() -> dict[str, object]:
    """Load the committed evaluation evidence document.

    Returns:
        Parsed evidence mapping (rows, recommendation, skill defaults).

    Raises:
        OSError: When the evidence file cannot be read.
        json.JSONDecodeError: When the evidence file is not valid JSON.
    """
    return json.loads(evaluation_evidence_path().read_text(encoding="utf-8"))


def map_evaluation_effort_to_skill_level(evaluation_effort: str) -> str:
    """Map a full evaluation effort name to an e-code-review skill level.

    Args:
        evaluation_effort: One of low / medium / high / xhigh / max.

    Returns:
        One of low / medium / xhigh.

    Raises:
        ValueError: When the evaluation effort is unknown.
    """
    skill_effort = ALL_SKILL_EFFORT_FOR_EVALUATION_EFFORT.get(evaluation_effort)
    if skill_effort is None:
        raise ValueError(f"unknown evaluation effort: {evaluation_effort!r}")
    return skill_effort


def skill_defaults_from_recommendation(
    all_recommendation_fields: Mapping[str, object],
) -> dict[str, object]:
    """Build e-code-review skill defaults that each cite a recommendation row.

    Args:
        all_recommendation_fields: Output of ``recommend_effort_by_band``.

    Returns:
        Skill-family defaults document with cited rows per band.

    Raises:
        TypeError: When recommendation structure is not mapping-shaped.
        ValueError: When a mapped skill effort leaves the skill surface.
    """
    recommendation_by_band = all_recommendation_fields["recommendation_by_band"]
    if not isinstance(recommendation_by_band, Mapping):
        raise TypeError("recommendation_by_band must be a mapping")
    default_by_band: MutableMapping[str, object] = {}
    for each_band in ALL_FIXTURE_BANDS:
        band_entry = recommendation_by_band[each_band]
        if not isinstance(band_entry, Mapping):
            raise TypeError(f"band entry for {each_band} must be a mapping")
        evaluation_effort = band_entry.get("recommended_effort")
        cited_row = band_entry.get("cited_row")
        if evaluation_effort is None or cited_row is None:
            default_by_band[each_band] = {
                "skill_effort": None,
                "cited_row": None,
                "blocker": band_entry.get("blocker"),
            }
            continue
        skill_effort = map_evaluation_effort_to_skill_level(str(evaluation_effort))
        if skill_effort not in ALL_SKILL_EFFORT_LEVELS:
            raise ValueError(f"skill effort out of surface: {skill_effort!r}")
        default_by_band[each_band] = {
            "skill_effort": skill_effort,
            "evaluation_effort": evaluation_effort,
            "cited_row": dict(cited_row) if isinstance(cited_row, Mapping) else cited_row,
            "blocker": None,
        }
    return {
        "workflow_family": WORKFLOW_FAMILY_E_CODE_REVIEW,
        "thinking_enabled": THINKING_ENABLED_DEFAULT,
        "cost_latency_lever": COST_LATENCY_LEVER,
        "skill_levels": list(ALL_SKILL_EFFORT_LEVELS),
        "default_by_band": dict(default_by_band),
    }


def resolve_skill_effort_for_band(fixture_band: str) -> str:
    """Return the evaluation-backed skill effort for one fixture band.

    Args:
        fixture_band: easy / medium / demanding.

    Returns:
        Skill effort level (low / medium / xhigh).

    Raises:
        ValueError: When the band is unknown or has no holding recommendation.
        KeyError: When the evidence document lacks the band.
    """
    if fixture_band not in ALL_FIXTURE_BANDS:
        raise ValueError(f"unknown fixture band: {fixture_band!r}")
    evidence = load_evaluation_evidence()
    skill_defaults = evidence["skill_defaults"]
    if not isinstance(skill_defaults, Mapping):
        raise TypeError("skill_defaults must be a mapping")
    default_by_band = skill_defaults["default_by_band"]
    if not isinstance(default_by_band, Mapping):
        raise TypeError("default_by_band must be a mapping")
    band_default = default_by_band[fixture_band]
    if not isinstance(band_default, Mapping):
        raise TypeError(f"default for {fixture_band} must be a mapping")
    skill_effort = band_default.get("skill_effort")
    if skill_effort is None:
        raise ValueError(
            f"no evaluation-backed skill effort for band {fixture_band!r}: "
            f"{band_default.get('blocker')}"
        )
    return str(skill_effort)
