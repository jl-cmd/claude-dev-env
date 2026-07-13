"""Constants for the model-tier-run validator and CLI / Agent alias map.

They name the parts of a spawn-walk log: the tier ladder (strongest
first), the two host profiles, the spawn-log dict keys, and the tokens
that mark a bind.

::

    attempt = {"tier": "Opus", "result": "spawned"}
                       ^^^^^^           ^^^^^^^^^
                       a ladder tier    SPAWN_SUCCESS_TOKEN
    ok:   "cli" marks a CLI Claude-chain bind (CLI_BIND_SUCCESS_TOKEN)
    flag: any other result token counts as no bind

The alias map turns each tier into its short CLI / Agent name (``opus``,
``grok``), never a dated full model ID.

Host-profile detection (see ``detect_host_profile``):

- ``ADVISOR_HOST_PROFILE=Grok`` or ``=Claude`` — explicit override
- ``GROK_BUILD=1`` (or ``true`` / ``yes``) — Grok Build / xAI harness
- default when neither is set: Claude
"""

from __future__ import annotations

HOST_PROFILE_CLAUDE: str = "Claude"
HOST_PROFILE_GROK: str = "Grok"
ALL_HOST_PROFILES: tuple[str, ...] = (HOST_PROFILE_CLAUDE, HOST_PROFILE_GROK)

ALL_MODEL_TIERS: tuple[str, ...] = ("Fable", "Opus", "Sonnet", "Haiku")
GROK_MODEL_TIER: str = "Grok"
ALL_KNOWN_TIER_NAMES: tuple[str, ...] = (*ALL_MODEL_TIERS, GROK_MODEL_TIER)
GROK_CLI_ADVISOR_FLOOR_TIER: str = "Opus"

ADVISOR_SENDMESSAGE_REPLY_WAIT_SECONDS: int = 120

ALL_CLI_MODEL_ID_BY_TIER: dict[str, str] = {
    "Fable": "fable",
    "Opus": "opus",
    "Sonnet": "sonnet",
    "Haiku": "haiku",
    GROK_MODEL_TIER: "grok",
}

HOST_PROFILE_ENV_VAR: str = "ADVISOR_HOST_PROFILE"
GROK_BUILD_ENV_VAR: str = "GROK_BUILD"
ALL_GROK_BUILD_TRUTHY_VALUES: frozenset[str] = frozenset(
    {"1", "true", "yes", "on"}
)

TIER_KEY: str = "tier"
SPAWN_OUTCOME_KEY: str = "result"
SPAWN_SUCCESS_TOKEN: str = "spawned"
CLI_BIND_SUCCESS_TOKEN: str = "cli"

UNKNOWN_OWN_TIER_MESSAGE: str = "own_tier is not a known model tier"
UNKNOWN_LADDER_NAME_ERROR: str = "ladder name is not a known model tier: {!r}"
UNKNOWN_HOST_PROFILE_ERROR: str = "host profile is not a known profile: {!r}"
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
    "selected_tier does not match the first successful bind (spawned or self)"
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
