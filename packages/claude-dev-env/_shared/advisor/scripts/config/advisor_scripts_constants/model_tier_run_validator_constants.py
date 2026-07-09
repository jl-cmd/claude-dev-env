"""Constants for the model-tier-run validator and CLI / Agent alias map.

Groups: the model tier ladder (strongest first), the CLI / Agent short-alias
map (stable names such as ``opus``, not dated full model IDs like
``claude-opus-4-…``), the SendMessage reply wait bound, the spawn-log dict
keys, the token that marks a successful spawn, and the validation
error-message strings.
"""

from __future__ import annotations

ALL_MODEL_TIERS: tuple[str, ...] = ("Fable", "Opus", "Sonnet", "Haiku")

ADVISOR_SENDMESSAGE_REPLY_WAIT_SECONDS: int = 120

ALL_CLI_MODEL_ID_BY_TIER: dict[str, str] = {
    "Fable": "fable",
    "Opus": "opus",
    "Sonnet": "sonnet",
    "Haiku": "haiku",
}

TIER_KEY: str = "tier"
SPAWN_OUTCOME_KEY: str = "result"
SPAWN_SUCCESS_TOKEN: str = "spawned"

UNKNOWN_OWN_TIER_MESSAGE: str = "own_tier is not a known model tier"
UNKNOWN_LADDER_NAME_ERROR: str = "ladder name is not a known model tier: {!r}"
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
INCOMPLETE_FALLBACK_WALK_MESSAGE: str = (
    "selected_tier is null but attempts did not exhaust every candidate tier"
)
CLI_USAGE_MESSAGE: str = (
    "usage: model_tier_run_validator.py <spawn-walk-log.json>"
)
CLI_MISSING_PATH_EXIT_CODE: int = 2
CLI_INVALID_JSON_EXIT_CODE: int = 2
CLI_VALIDATION_FAILURE_EXIT_CODE: int = 1
CLI_SUCCESS_EXIT_CODE: int = 0
