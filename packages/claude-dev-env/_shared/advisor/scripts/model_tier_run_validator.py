"""Mechanically validate a model-tier spawn-walk log.

The advisor protocol's Model floor section emits a structured spawn-walk log.
This validator reads that log back and checks its invariants. A run is judged
from data, not inferred from a transcript.

::

    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": "Opus", "result": "spawned"},
        ],
        selected_tier="Opus",
    )
    validate_model_tier_run(run)     # ok: returns None, raises nothing

A run whose selected_tier is not the first spawned tier fails.
On any broken invariant, validate_model_tier_run raises ModelTierRunError.
"""

from __future__ import annotations

from dataclasses import dataclass

from advisor_scripts_constants.model_tier_run_validator_constants import (
    ALL_MODEL_TIERS,
    ATTEMPT_ORDER_MISMATCH_MESSAGE,
    ATTEMPT_TIER_OUT_OF_SLICE_MESSAGE,
    CANDIDATE_TIERS_MISMATCH_MESSAGE,
    MISSING_FALLBACK_REASON_MESSAGE,
    SELECTED_TIER_MISMATCH_MESSAGE,
    SELECTED_TIER_NOT_NULL_MESSAGE,
    SPAWN_OUTCOME_KEY,
    SPAWN_SUCCESS_TOKEN,
    TIER_KEY,
    UNKNOWN_OWN_TIER_MESSAGE,
)


@dataclass(frozen=True)
class ModelTierRun:
    own_tier: str
    candidate_tiers: list[str]
    attempts: list[dict[str, str]]
    selected_tier: str | None
    fallback_reason: str | None = None


class ModelTierRunError(ValueError):
    """Raised when a model-tier spawn-walk log violates an invariant."""


def _expected_candidate_tiers(own_tier: str) -> list[str]:
    if own_tier not in ALL_MODEL_TIERS:
        raise ModelTierRunError(f"{UNKNOWN_OWN_TIER_MESSAGE}: {own_tier!r}")
    floor_index = ALL_MODEL_TIERS.index(own_tier)
    return list(ALL_MODEL_TIERS[: floor_index + 1])


def validate_model_tier_run(run: ModelTierRun) -> None:
    """Check that a spawn-walk log satisfies every ladder invariant.

    The candidate tiers must equal the ladder slice down to the floor. The
    recorded tries must walk that slice in order. The selected tier must be
    the first tier that spawned, or null with a fallback reason when none did.

    Args:
        run: The structured spawn-walk log to check.

    Returns:
        None when every invariant holds.

    Raises:
        ModelTierRunError: When any invariant is violated.
    """
    expected_candidates = _expected_candidate_tiers(run.own_tier)
    if run.candidate_tiers != expected_candidates:
        raise ModelTierRunError(CANDIDATE_TIERS_MISMATCH_MESSAGE)
    attempted_tiers = [each_attempt[TIER_KEY] for each_attempt in run.attempts]
    if any(each_tier not in expected_candidates for each_tier in attempted_tiers):
        raise ModelTierRunError(ATTEMPT_TIER_OUT_OF_SLICE_MESSAGE)
    if attempted_tiers != expected_candidates[: len(attempted_tiers)]:
        raise ModelTierRunError(ATTEMPT_ORDER_MISMATCH_MESSAGE)
    _validate_selected_tier(run)


def _validate_selected_tier(run: ModelTierRun) -> None:
    all_spawned_tiers = [
        each_attempt[TIER_KEY]
        for each_attempt in run.attempts
        if each_attempt[SPAWN_OUTCOME_KEY] == SPAWN_SUCCESS_TOKEN
    ]
    if all_spawned_tiers:
        if run.selected_tier != all_spawned_tiers[0]:
            raise ModelTierRunError(SELECTED_TIER_MISMATCH_MESSAGE)
        return
    if run.selected_tier is not None:
        raise ModelTierRunError(SELECTED_TIER_NOT_NULL_MESSAGE)
    if not run.fallback_reason:
        raise ModelTierRunError(MISSING_FALLBACK_REASON_MESSAGE)
