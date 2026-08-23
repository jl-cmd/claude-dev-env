"""Constants for the model-tier-run validator and CLI / Agent alias map.

They name the parts of a spawn-walk log: the tier ladder (strongest
first), the two host profiles, and the validation messages. Shared log
keys and bind-result tokens live in ``advisor_route_constants``.

::

The alias map turns each tier into its short CLI / Agent name (``opus``,
``third-party``), never a dated full model ID.

Host-profile detection (see ``detect_host_profile``):

- ``ADVISOR_HOST_PROFILE=ThirdParty`` or ``=Claude`` — explicit override
- ``THIRD_PARTY=1`` (or ``true`` / ``yes``) — a third-party (non-Claude) harness
- default when neither is set: Claude
"""

from __future__ import annotations

from advisor_scripts_constants.advisor_route_constants import (
    ADVISOR_FALLBACK_TIER,
    ADVISOR_MODEL_TIER,
)

HOST_PROFILE_CLAUDE: str = "Claude"
HOST_PROFILE_THIRD_PARTY: str = "ThirdParty"
ALL_HOST_PROFILES: tuple[str, ...] = (
    HOST_PROFILE_CLAUDE,
    HOST_PROFILE_THIRD_PARTY,
)

ALL_MODEL_TIERS: tuple[str, ...] = (
    ADVISOR_FALLBACK_TIER,
    "Opus",
    "Sonnet",
    "Haiku",
)
THIRD_PARTY_MODEL_TIER: str = "ThirdParty"
ALL_KNOWN_TIER_NAMES: tuple[str, ...] = (
    ADVISOR_MODEL_TIER,
    *ALL_MODEL_TIERS,
    THIRD_PARTY_MODEL_TIER,
)

ADVISOR_SENDMESSAGE_REPLY_WAIT_SECONDS: int = 120

ALL_CLI_MODEL_ID_BY_TIER: dict[str, str] = {
    ADVISOR_FALLBACK_TIER: "fable",
    "Opus": "opus",
    "Sonnet": "sonnet",
    "Haiku": "haiku",
    THIRD_PARTY_MODEL_TIER: "third-party",
}
HOST_PROFILE_ENV_VAR: str = "ADVISOR_HOST_PROFILE"
THIRD_PARTY_ENV_VAR: str = "THIRD_PARTY"
ALL_THIRD_PARTY_TRUTHY_VALUES: frozenset[str] = frozenset(
    {"1", "true", "yes", "on"}
)

UNKNOWN_OWN_TIER_MESSAGE: str = "own_tier is not a known model tier"
UNKNOWN_LADDER_NAME_ERROR: str = "ladder name is not a known model tier: {!r}"
UNKNOWN_HOST_PROFILE_ERROR: str = "host profile is not a known profile: {!r}"
CANDIDATE_TIERS_MISMATCH_MESSAGE: str = (
    "candidate_tiers does not match the Fable then Sol advisor walk"
)
ATTEMPT_TIER_OUT_OF_SLICE_MESSAGE: str = (
    "a spawn try names a tier outside the candidate slice"
)
ATTEMPT_ORDER_MISMATCH_MESSAGE: str = (
    "spawn tries do not walk the candidate tiers in ladder order"
)
SELECTED_TIER_MISMATCH_MESSAGE: str = (
    "selected_tier does not match the first successful bind (spawned or cli)"
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
