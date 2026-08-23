"""Shared advisor_route_constants for advisor selection and replies."""

from __future__ import annotations

ADVISOR_MODEL_TIER: str = "Sol"
ADVISOR_CODEX_MODEL_ID: str = "gpt-5.6-sol"
ADVISOR_FALLBACK_TIER: str = "Fable"
ADVISOR_FALLBACK_RESULT: str = "fable"
FABLE_ADVISOR_CLI_EFFORT: str = "medium"
ALL_ADVISOR_GUIDANCE_SIGNALS: frozenset[str] = frozenset(
    {"ENDORSE", "CORRECTION", "PLAN", "STOP"}
)

TIER_KEY: str = "tier"
SPAWN_OUTCOME_KEY: str = "result"
SPAWN_SUCCESS_TOKEN: str = "spawned"
CLI_BIND_SUCCESS_TOKEN: str = "cli"
CODEX_BIND_SUCCESS_TOKEN: str = "codex"

ALL_CODEX_MODEL_ID_BY_TIER: dict[str, str] = {
    ADVISOR_MODEL_TIER: ADVISOR_CODEX_MODEL_ID,
}
