"""Constants for the model-tier-run validator.

Groups: the model tier ladder (strongest first), the spawn-log dict keys, the
token that marks a successful spawn, and the validation error-message strings.
"""

from __future__ import annotations

ALL_MODEL_TIERS: tuple[str, ...] = ("Fable", "Opus", "Sonnet", "Haiku")

TIER_KEY: str = "tier"
SPAWN_OUTCOME_KEY: str = "result"
SPAWN_SUCCESS_TOKEN: str = "spawned"

UNKNOWN_OWN_TIER_MESSAGE: str = "own_tier is not a known model tier"
CANDIDATE_TIERS_MISMATCH_MESSAGE: str = (
    "candidate_tiers does not match the ladder slice down to own_tier"
)
ATTEMPT_TIER_OUT_OF_SLICE_MESSAGE: str = (
    "a spawn try names a tier outside the candidate slice"
)
ATTEMPT_ORDER_MISMATCH_MESSAGE: str = (
    "spawn tries do not walk the candidate tiers in ladder order"
)
SELECTED_TIER_MISMATCH_MESSAGE: str = (
    "selected_tier does not match the first spawned tier"
)
SELECTED_TIER_NOT_NULL_MESSAGE: str = (
    "selected_tier must be null when no spawn try succeeded"
)
MISSING_FALLBACK_REASON_MESSAGE: str = (
    "fallback_reason is required when no spawn try succeeded"
)
