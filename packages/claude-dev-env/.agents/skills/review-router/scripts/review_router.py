"""Thin route orchestrator for review-tier decisions."""

from __future__ import annotations

import json
from pathlib import Path

from review_router_constants.config.constants import UNSUPPORTED_ROUTE, UNSUPPORTED_TIER


def load_route_policy() -> dict:
    """Load versioned route policy data.

    Args:
    Returns:
        Route policy mapping.
    Raises:
        ValueError: If the policy schema is invalid.
    """
    policy_path = Path(__file__).parent.parent / "reference" / "route-policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    if policy.get("version") != 1 or not isinstance(policy.get("routes"), dict):
        raise ValueError("malformed route policy")
    return policy


def resolve_route(route: str, tier: str, policy: dict | None = None) -> dict:
    """Resolve one route or return a stable unsupported result.

    Args:
        route: Requested route name.
        tier: Effective tier.
        policy: Optional route policy.
    Returns:
        Dispatch record or unsupported status.
    """
    selected_policy = policy or load_route_policy()
    route_record = selected_policy["routes"].get(route)
    if route_record is None or route_record["status"] != "SUPPORTED":
        return {"status": UNSUPPORTED_ROUTE, "route": route, "tier": tier}
    if tier not in route_record["tiers"]:
        return {"status": UNSUPPORTED_TIER, "route": route, "tier": tier}
    dispatch = route_record["models"][tier]
    return {
        "status": "SUPPORTED",
        "route": route,
        "tier": tier,
        "skill": route_record["skill"],
        "dispatch": dispatch,
    }
