"""Map ladder tier names to Claude Code CLI / Agent short model aliases.

::

    resolve_cli_model_id("Opus")   # ok: "opus"
    resolve_cli_model_id("fable")  # ok: "fable" (any letter case)
    resolve_cli_model_id(" Opus ") # ok: "opus" (leading/trailing whitespace)
    resolve_cli_model_id("Titan")  # flag: ValueError

Values are stable short aliases (``opus``, ``sonnet``), not dated full model
IDs such as ``claude-opus-4-…``. The map lives in ``advisor_scripts_constants``
so protocol text, skills, and tests share one source of truth for the aliases
the Agent tool ``model:`` field and CLI ``--model`` flag already accept.

Args and returns for the public helper are documented on the function itself.
"""

from __future__ import annotations

import sys
from pathlib import Path

_config_directory = str(Path(__file__).resolve().parent / "config")
if _config_directory not in sys.path:
    sys.path.insert(0, _config_directory)

from advisor_scripts_constants.model_tier_run_validator_constants import (  # noqa: E402
    ALL_CLI_MODEL_ID_BY_TIER,
    ALL_MODEL_TIERS,
    UNKNOWN_LADDER_NAME_ERROR,
)


def canonical_tier_name(tier_name: str) -> str | None:
    """Return the Title Case ladder name for ``tier_name``, or ``None``.

    ::

        canonical_tier_name("opus")   # ok: "Opus"
        canonical_tier_name(" Opus ") # ok: "Opus"
        canonical_tier_name("")       # ok: None
        canonical_tier_name("Titan")  # ok: None

    Strips leading and trailing whitespace, then matches any letter case
    against ``ALL_MODEL_TIERS``.

    Args:
        tier_name: Raw tier text from a spawn log, protocol walk, or caller.

    Returns:
        The canonical Title Case ladder name, or ``None`` when unknown.
    """
    stripped_tier_name = tier_name.strip()
    if not stripped_tier_name:
        return None
    tier_by_lower_name = {
        each_tier.lower(): each_tier for each_tier in ALL_MODEL_TIERS
    }
    return tier_by_lower_name.get(stripped_tier_name.lower())


def resolve_cli_model_id(tier: str) -> str:
    """Return the CLI / Agent short model alias for a ladder tier name.

    ::

        resolve_cli_model_id("Sonnet")  # ok: "sonnet"
        resolve_cli_model_id("HAIKU")   # ok: "haiku"
        resolve_cli_model_id(" Opus ")  # ok: "opus"
        resolve_cli_model_id("Titan")   # flag: ValueError

    Accepts any letter case and surrounding whitespace. The returned string is
    the short alias used by the Agent tool ``model:`` field and the CLI
    ``--model`` flag — not a dated full model ID.

    Args:
        tier: Ladder tier name (``Fable``, ``Opus``, ``Sonnet``, or ``Haiku``).

    Returns:
        The short model alias for that tier (for example ``"opus"``).

    Raises:
        ValueError: When ``tier`` is not a known ladder tier, or the alias map
            is missing that ladder name.
    """
    maybe_canonical_tier = canonical_tier_name(tier)
    if maybe_canonical_tier is None:
        raise ValueError(UNKNOWN_LADDER_NAME_ERROR.format(tier))
    maybe_model_alias = ALL_CLI_MODEL_ID_BY_TIER.get(maybe_canonical_tier)
    if maybe_model_alias is None:
        raise ValueError(UNKNOWN_LADDER_NAME_ERROR.format(tier))
    return maybe_model_alias
