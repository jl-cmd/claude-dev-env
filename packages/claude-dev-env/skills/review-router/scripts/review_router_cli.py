"""CLI for signed review decisions and one-time spawn permits."""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import shlex
import secrets
import sys
from pathlib import Path

tier_script = Path(__file__).resolve().parents[1].parent / "review-tier" / "scripts"
if str(tier_script) not in sys.path:
    sys.path.insert(0, str(tier_script))
from review_router_constants.config.constants import (  # noqa: E402
    ALL_OVERRIDE_VALUES,
    CLEANUP_CONTRACT,
    DECISION_ID_BYTES,
    INTEGRITY_KEY_BYTES,
    INVALID_ROUTE_ARM,
    INVALID_ROUTE_RECORD,
    MALFORMED_TIER_OVERRIDE,
    ROUTE_SPAWN_ARMED,
    UNKNOWN_ROUTE_SLOT,
    UNSUPPORTED_ROUTE,
)
from review_tier import (  # noqa: E402
    build_generation,
    canonical_json_hash,
    inventory_generation,
    policy_hash,
    router_state_directory,
    router_state_root,
    router_state_root_id,
)
from review_router import load_route_policy, resolve_route  # noqa: E402


def _write_signed(directory: Path, name: str, record: dict, secret: bytes) -> None:
    encoded = _encode_record(record)
    temporary = directory / f".{name}.tmp"
    temporary.write_bytes(encoded)
    temporary.replace(directory / name)
    (directory / f"{name}.hmac").write_text(hmac.new(secret, encoded, hashlib.sha256).hexdigest(), encoding="ascii")


def _read_signed(directory: Path, name: str) -> dict:
    secret = (directory / "integrity.key").read_bytes()
    record_path = directory / name
    encoded = record_path.read_bytes()
    expected = hmac.new(secret, encoded, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, (directory / f"{name}.hmac").read_text(encoding="ascii")):
        raise ValueError(INVALID_ROUTE_RECORD)
    return json.loads(encoded)


def _encode_record(record: dict) -> bytes:
    return json.dumps(record, sort_keys=True, separators=(",", ":")).encode()


def _override(arguments: str) -> str | None:
    tokens = shlex.split(arguments)
    matches = [token for token in tokens if token == "--tier" or token.startswith("--tier=")]
    if len(matches) > 1:
        raise ValueError(MALFORMED_TIER_OVERRIDE)
    if not matches:
        return None
    if matches[0] == "--tier":
        index = tokens.index("--tier")
        if index + 1 >= len(tokens) or tokens[index + 1] not in ALL_OVERRIDE_VALUES:
            raise ValueError(MALFORMED_TIER_OVERRIDE)
        return f"T{tokens[index + 1]}"
    override = matches[0].split("=", 1)[1]
    if override not in ALL_OVERRIDE_VALUES:
        raise ValueError(MALFORMED_TIER_OVERRIDE)
    return f"T{override}"


def resolve(cwd: str, review_kind: str, arguments: str, base_ref: str | None) -> dict:
    """Create a signed review decision.

    Args:
        cwd: Repository path.
        review_kind: Requested review route.
        arguments: Review command arguments.
        base_ref: Optional base reference.
    Returns:
        Decision summary.
    Raises:
        ValueError: If the override or base reference is invalid.
    """
    route_policy = load_route_policy()
    route_record = route_policy["routes"].get(review_kind)
    if route_record is None or route_record.get("status") != "SUPPORTED":
        return {"status": UNSUPPORTED_ROUTE}
    override = _override(arguments)
    directory = router_state_directory(cwd)
    if (directory / "armed-spawn.json").exists():
        raise ValueError(ROUTE_SPAWN_ARMED)
    directory.mkdir(parents=True, exist_ok=True)
    key_path = directory / "integrity.key"
    if not key_path.exists():
        key_path.write_bytes(secrets.token_bytes(INTEGRITY_KEY_BYTES))
    secret = key_path.read_bytes()
    state_root = router_state_root(cwd)
    generation = build_generation(cwd, requested_override=override, base_ref=base_ref, state_root=state_root)
    route = resolve_route(review_kind, generation["effective_tier"], route_policy)
    decision_id = secrets.token_hex(DECISION_ID_BYTES)
    dispatch = route["dispatch"]
    slots = [{"slot_id": each_slot_id, "model": dispatch["model"], "effort": dispatch["effort"]} for each_slot_id in dispatch["pass_ids"]]
    decision = {**generation, "decision_id": decision_id, "review_kind": review_kind, "route_policy_hash": policy_hash(route_policy), "state_root_id": router_state_root_id(state_root), "slots": slots}
    _write_signed(directory, "decision.json", decision, secret)
    return {"status": "SUPPORTED", "decision_id": decision_id, "effective_tier": decision["effective_tier"], "automatic_tier": decision["calculated_tier"], "slot_ids": [slot["slot_id"] for slot in slots]}


def arm(cwd: str, decision_id: str, slot_id: str) -> dict:
    """Create a one-time spawn permit.

    Args:
        cwd: Repository path.
        decision_id: Decision identifier.
        slot_id: Selected dispatch slot.
    Returns:
        Agent tool payload.
    Raises:
        OSError: If signed state is unavailable.
        ValueError: If the decision or slot is invalid.
    """
    directory = router_state_directory(cwd)
    secret = (directory / "integrity.key").read_bytes()
    decision = _read_signed(directory, "decision.json")
    if decision["decision_id"] != decision_id or (directory / "armed-spawn.json").exists():
        raise ValueError(INVALID_ROUTE_ARM)
    consumed_prefix = f"{decision_id}--{slot_id}"
    if any(path.name.startswith(consumed_prefix) for path in (directory / "consumed").glob(f"{consumed_prefix}*")):
        raise ValueError(INVALID_ROUTE_ARM)
    slot = next((each_slot for each_slot in decision["slots"] if each_slot["slot_id"] == slot_id), None)
    if slot is None:
        raise ValueError(UNKNOWN_ROUTE_SLOT)
    consumed_slots = {path.name.split("--", 1)[1].split(".", 1)[0] for path in (directory / "consumed").glob(f"{decision_id}--*.json")}
    expected_slots = [each_slot["slot_id"] for each_slot in decision["slots"] if each_slot["slot_id"] not in consumed_slots]
    if expected_slots and slot_id != expected_slots[0]:
        raise ValueError(INVALID_ROUTE_ARM)
    decision_base = decision.get("base_ref") if decision.get("base_source") == "explicit" else None
    state_root = router_state_root(cwd)
    current_hash = str(inventory_generation(cwd, decision_base, state_root=state_root)["diff_hash"])
    if current_hash != decision["diff_hash"]:
        raise ValueError(INVALID_ROUTE_ARM)
    prompt = f"{CLEANUP_CONTRACT} Review {decision['review_kind']} for {decision['worktree']}. Angles: Reuse, Simplification, Efficiency, Altitude. Apply direct fixes within scope. Skip correctness, security, behavior-changing, and out-of-scope findings. Decision {decision_id}; slot {slot_id}."
    spawn = {"decision_id": decision_id, "decision_hash": canonical_json_hash(decision), "state_root_id": router_state_root_id(state_root), "slot_id": slot_id, "tool_name": "Agent", "executor_type": "Luna", "model": slot["model"], "effort": slot["effort"], "prompt": prompt, "prompt_hash": hashlib.sha256(prompt.encode()).hexdigest(), "diff_hash": decision["diff_hash"]}
    _write_signed(directory, "armed-spawn.json", spawn, secret)
    return {"tool_name": "Agent", "tool_input": {"executor_type": "Luna", "model": spawn["model"], "effort": spawn["effort"], "prompt": prompt}}


def close(cwd: str, decision_id: str) -> dict:
    """Close a decision after its permit is consumed.

    Args:
        cwd: Repository path.
        decision_id: Decision identifier.
    Returns:
        Closure summary.
    Raises:
        OSError: If signed state is unavailable.
        ValueError: If the decision is invalid or still armed.
    """
    directory = router_state_directory(cwd)
    decision = _read_signed(directory, "decision.json")
    if decision["decision_id"] != decision_id or (directory / "armed-spawn.json").exists():
        raise ValueError(ROUTE_SPAWN_ARMED)
    (directory / "decision.json").unlink()
    (directory / "decision.json.hmac").unlink()
    return {"status": "CLOSED", "decision_id": decision_id}


def main() -> int:
    """Run the review-routing command line interface.

    Returns:
        Process exit status.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("resolve", "arm", "close"))
    parser.add_argument("--review-kind", default="e-simplify")
    parser.add_argument("--cwd", default=os.getcwd())
    parser.add_argument("--arguments", default="")
    parser.add_argument("--base-ref")
    parser.add_argument("--decision-id")
    parser.add_argument("--slot")
    parser.add_argument("--requested", action="store_true")
    options = parser.parse_args()
    if options.requested:
        parser.error("--requested is not supported")
    try:
        if options.command == "resolve":
            dispatch_record = resolve(options.cwd, options.review_kind, options.arguments, base_ref=options.base_ref)
        elif options.command == "arm":
            dispatch_record = arm(options.cwd, options.decision_id, options.slot)
        else:
            dispatch_record = close(options.cwd, options.decision_id)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(dispatch_record, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
