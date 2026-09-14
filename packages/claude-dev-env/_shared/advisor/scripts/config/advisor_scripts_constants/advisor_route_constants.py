"""Shared constants for advisor selection and replies."""

from __future__ import annotations

import json
from pathlib import Path

ADVISOR_MODEL_TIER: str = "Astra"
ADVISOR_FALLBACK_TIER: str = "Fable"
ADVISOR_FALLBACK_RESULT: str = "fable"
ADVISOR_EFFORT_ENV_VAR: str = "ADVISOR_EFFORT"


def _policy_path_candidates() -> tuple[Path, ...]:
    shared_root = Path(__file__).resolve().parents[5]
    if shared_root.name == ".agents":
        agents_root = shared_root
    elif shared_root.name.lower() == ".claude":
        agents_root = shared_root.parent / ".agents"
    else:
        agents_root = shared_root.parent / f"{shared_root.name}.agents"
    if shared_root.name == ".agents":
        policy_root = shared_root
    elif shared_root.name.lower() == ".claude":
        policy_root = agents_root
    elif (shared_root / "package.json").is_file():
        policy_root = shared_root
    else:
        policy_root = agents_root
    return (policy_root / "rules" / "subagent-model-policy.json",)


def _read_policy_values() -> tuple[str, str, tuple[str, ...], dict[str, str]]:
    try:
        policy_path = next(
            (each_path for each_path in _policy_path_candidates() if each_path.is_file()),
            None,
        )
        if policy_path is None:
            raise RuntimeError("subagent model policy is missing")
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
        default_pair = policy["advisorDefault"]
        model_id = policy["models"][default_pair["model"]]["id"]
        all_efforts = tuple(policy["efforts"]["values"])
        effort_aliases = {
            str(each_alias).strip().lower(): str(each_target).strip().lower()
            for each_alias, each_target in policy["efforts"]["aliases"].items()
        }
        return (
            model_id,
            default_pair["effort"],
            all_efforts,
            effort_aliases,
        )
    except (
        AttributeError,
        IndexError,
        KeyError,
        OSError,
        RuntimeError,
        TypeError,
        UnicodeError,
        json.JSONDecodeError,
    ):
        return "", "", (), {}


(
    ADVISOR_CODEX_MODEL_ID,
    ADVISOR_EFFORT_DEFAULT,
    ALL_ADVISOR_EFFORT_LEVELS,
    ADVISOR_EFFORT_ALIASES,
) = _read_policy_values()
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
