"""Map ladder tier names to Claude Code CLI / Agent model aliases.

::

    resolve_cli_model_id("Opus")   # ok: "opus"
    resolve_cli_model_id("fable")  # ok: "fable" (any letter case)
    resolve_cli_model_id("Titan")  # flag: ValueError

The map lives in ``advisor_scripts_constants`` so protocol text, skills, and
tests share one source of truth for the short aliases the Agent tool and CLI
``--model`` flag already accept.

Args and returns for the public helper are documented on the function itself.
"""

from __future__ import annotations

from advisor_scripts_constants.model_tier_run_validator_constants import (
    ALL_CLI_MODEL_ID_BY_TIER,
    ALL_MODEL_TIERS,
    UNKNOWN_LADDER_NAME_ERROR,
)


def _canonical_tier_name(tier_name: str) -> str | None:
    tier_by_lower_name = {
        each_tier.lower(): each_tier for each_tier in ALL_MODEL_TIERS
    }
    return tier_by_lower_name.get(tier_name.lower())


def resolve_cli_model_id(tier: str) -> str:
    """Return the CLI / Agent ``model`` alias for a ladder tier name.

    ::

        resolve_cli_model_id("Sonnet")  # ok: "sonnet"
        resolve_cli_model_id("HAIKU")   # ok: "haiku"
        resolve_cli_model_id("Titan")   # flag: ValueError

    Accepts any letter case. The returned string is the short alias used by
    the Agent tool ``model:`` field and the CLI ``--model`` flag.

    Args:
        tier: Ladder tier name (``Fable``, ``Opus``, ``Sonnet``, or ``Haiku``).

    Returns:
        The short model alias for that tier (for example ``"opus"``).

    Raises:
        ValueError: When ``tier`` is not a known ladder tier.
    """
    maybe_canonical_tier = _canonical_tier_name(tier)
    if maybe_canonical_tier is None:
        raise ValueError(UNKNOWN_LADDER_NAME_ERROR.format(tier))
    return ALL_CLI_MODEL_ID_BY_TIER[maybe_canonical_tier]
