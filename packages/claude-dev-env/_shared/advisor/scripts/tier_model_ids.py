"""Map ladder tier names to Claude Code CLI / Agent short model aliases.

::

    resolve_cli_model_id("Opus")   # ok: "opus"
    resolve_cli_model_id("fable")  # ok: "fable" (any letter case)
    resolve_cli_model_id("Grok")   # ok: "grok" (Grok host single tier)
    resolve_cli_model_id(" Opus ") # ok: "opus" (leading/trailing whitespace)
    resolve_cli_model_id("Titan")  # flag: ValueError

    detect_host_profile(setting_by_name={"GROK_BUILD": "1"})  # ok: "Grok"
    detect_host_profile(
        setting_by_name={"ADVISOR_HOST_PROFILE": "Claude"}
    )  # ok: "Claude"

Values are stable short aliases (``opus``, ``sonnet``, ``grok``), not dated
full model IDs such as ``claude-opus-4-…``. The map lives in
``advisor_scripts_constants`` so protocol text, skills, and tests share one
source of truth for the aliases the Agent tool ``model:`` field and CLI
``--model`` flag already accept.

Args and returns for the public helpers are documented on each function.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

_config_directory = str(Path(__file__).resolve().parent / "config")
if _config_directory not in sys.path:
    sys.path.insert(0, _config_directory)

from advisor_scripts_constants.model_tier_run_validator_constants import (  # noqa: E402
    ALL_CLI_MODEL_ID_BY_TIER,
    ALL_GROK_BUILD_TRUTHY_VALUES,
    ALL_HOST_PROFILES,
    ALL_KNOWN_TIER_NAMES,
    GROK_BUILD_ENV_VAR,
    HOST_PROFILE_CLAUDE,
    HOST_PROFILE_ENV_VAR,
    HOST_PROFILE_GROK,
    UNKNOWN_HOST_PROFILE_ERROR,
    UNKNOWN_LADDER_NAME_ERROR,
)


def canonical_tier_name(tier_name: str) -> str | None:
    """Return the Title Case ladder name for ``tier_name``, or ``None``.

    ::

        canonical_tier_name("opus")   # ok: "Opus"
        canonical_tier_name("grok")   # ok: "Grok"
        canonical_tier_name(" Opus ") # ok: "Opus"
        canonical_tier_name("")       # ok: None
        canonical_tier_name("Titan")  # ok: None

    Strips leading and trailing whitespace, then matches any letter case
    against ``ALL_KNOWN_TIER_NAMES`` (Claude ladder plus the Grok host tier).

    Args:
        tier_name: Raw tier text from a spawn log, protocol walk, or caller.

    Returns:
        The canonical Title Case ladder name, or ``None`` when unknown.
    """
    stripped_tier_name = tier_name.strip()
    if not stripped_tier_name:
        return None
    tier_by_lower_name = {
        each_tier.lower(): each_tier for each_tier in ALL_KNOWN_TIER_NAMES
    }
    return tier_by_lower_name.get(stripped_tier_name.lower())


def resolve_cli_model_id(tier: str) -> str:
    """Return the CLI / Agent short model alias for a ladder tier name.

    ::

        resolve_cli_model_id("Sonnet")  # ok: "sonnet"
        resolve_cli_model_id("HAIKU")   # ok: "haiku"
        resolve_cli_model_id("Grok")    # ok: "grok"
        resolve_cli_model_id(" Opus ")  # ok: "opus"
        resolve_cli_model_id("Titan")   # flag: ValueError

    Accepts any letter case and surrounding whitespace. The returned string is
    the short alias used by the Agent tool ``model:`` field and the CLI
    ``--model`` flag — not a dated full model ID.

    Args:
        tier: Ladder tier name (``Fable``, ``Opus``, ``Sonnet``, ``Haiku``,
            or ``Grok``).

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


def detect_host_profile(
    setting_by_name: Mapping[str, str] | None = None,
) -> str:
    """Return the advisor host profile from environment detection hints.

    ::

        detect_host_profile(setting_by_name={"ADVISOR_HOST_PROFILE": "Grok"})
        # ok: "Grok"
        detect_host_profile(setting_by_name={"GROK_BUILD": "1"})  # ok: "Grok"
        detect_host_profile(setting_by_name={})                   # ok: "Claude"
        detect_host_profile(setting_by_name={"ADVISOR_HOST_PROFILE": "X"})
        # flag: ValueError

    Order:

    1. ``ADVISOR_HOST_PROFILE`` when set (must be a known profile name).
    2. ``GROK_BUILD`` when truthy (``1``, ``true``, ``yes``, ``on``).
    3. Default ``Claude``.

    Args:
        setting_by_name: Env name → setting text (defaults to ``os.environ``).

    Returns:
        ``HOST_PROFILE_GROK`` or ``HOST_PROFILE_CLAUDE``.

    Raises:
        ValueError: When ``ADVISOR_HOST_PROFILE`` is set to an unknown name.
    """
    resolved_setting_by_name: Mapping[str, str] = (
        os.environ if setting_by_name is None else setting_by_name
    )
    explicit_host_profile = resolved_setting_by_name.get(
        HOST_PROFILE_ENV_VAR, ""
    ).strip()
    if explicit_host_profile:
        host_profile_by_lower_name = {
            each_profile.lower(): each_profile for each_profile in ALL_HOST_PROFILES
        }
        maybe_canonical_host = host_profile_by_lower_name.get(
            explicit_host_profile.lower()
        )
        if maybe_canonical_host is None:
            raise ValueError(UNKNOWN_HOST_PROFILE_ERROR.format(explicit_host_profile))
        return maybe_canonical_host
    raw_harness_marker = resolved_setting_by_name.get(
        GROK_BUILD_ENV_VAR, ""
    ).strip().lower()
    if raw_harness_marker in ALL_GROK_BUILD_TRUTHY_VALUES:
        return HOST_PROFILE_GROK
    return HOST_PROFILE_CLAUDE
