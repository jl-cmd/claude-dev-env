"""Fail-closed PreToolUse gate for prompt-carried route permits."""

from __future__ import annotations

import hashlib
import hmac
import json
import subprocess
import sys
from pathlib import Path

hook_root = Path(__file__).resolve().parent
router_script = hook_root.parent.parent / "skills" / "review-router" / "scripts"
tier_script = hook_root.parent.parent / "skills" / "review-tier" / "scripts"
for each_path in (hook_root, router_script, tier_script):
    if str(each_path) not in sys.path:
        sys.path.insert(0, str(each_path))
from review_tier import (  # noqa: E402
    canonical_json_hash,
    inventory_generation,
    router_state_directory,
    router_state_root,
    router_state_root_id,
)
from route_review_config.config.constants import ROUTE_SPAWN_MISMATCH  # noqa: E402


def _record_path(root: Path, name: str) -> Path:
    return router_state_directory(root) / name


def _read_signed_record(path: Path) -> dict | None:
    hmac_path = path.with_name(f"{path.name}.hmac")
    secret_path = path.with_name("integrity.key")
    try:
        if not path.exists() or not hmac_path.exists() or not secret_path.exists():
            return None
        encoded = path.read_bytes()
        secret = secret_path.read_bytes()
        expected = hmac.new(secret, encoded, hashlib.sha256).hexdigest()
        actual = hmac_path.read_text()
        if not hmac.compare_digest(expected, actual):
            return None
        record = json.loads(encoded)
    except (OSError, TypeError, ValueError):
        return None
    return record if isinstance(record, dict) else None


def _block_spawn_mismatch() -> int:
    print(json.dumps({"hookSpecificOutput": {"permissionDecision": "block", "permissionDecisionReason": ROUTE_SPAWN_MISMATCH}}))
    return 0


def main() -> int:
    payload = json.load(sys.stdin)
    if payload.get("tool_name") not in {"Agent", "Task"}:
        return 0
    root = payload.get("cwd")
    if not root:
        return 0
    decision_path = _record_path(Path(root), "decision.json")
    decision = _read_signed_record(decision_path)
    if decision is None and (decision_path.exists() or decision_path.with_name("decision.json.hmac").exists()):
        return _block_spawn_mismatch()
    if decision is None:
        return 0
    armed_path = _record_path(Path(root), "armed-spawn.json")
    armed = _read_signed_record(armed_path)
    tool_input = payload.get("tool_input", {})
    if "diff_hash" not in decision or "base_ref" not in decision:
        return _block_spawn_mismatch()
    decision_base = decision.get("base_ref") if decision.get("base_source") == "explicit" else None
    try:
        current_state_root = router_state_root(root)
        current_hash = str(inventory_generation(root, decision_base, state_root=current_state_root)["diff_hash"])
    except (OSError, ValueError, subprocess.SubprocessError):
        return _block_spawn_mismatch()
    decision_hash = canonical_json_hash(decision)
    armed_record = armed or {}
    expected = armed_record.get("tool_name"), armed_record.get("executor_type"), armed_record.get("model"), armed_record.get("effort"), armed_record.get("prompt_hash"), armed_record.get("decision_hash"), armed_record.get("diff_hash"), armed_record.get("state_root_id")
    actual_prompt = tool_input.get("prompt", "")
    actual = payload.get("tool_name"), tool_input.get("executor_type"), tool_input.get("model"), tool_input.get("effort"), hashlib.sha256(actual_prompt.encode()).hexdigest(), decision_hash, current_hash, router_state_root_id(current_state_root)
    if armed is None or expected != actual:
        return _block_spawn_mismatch()
    consumed = armed_path.parent / "consumed"
    consumed.mkdir(exist_ok=True)
    hmac_path = armed_path.with_name(f"{armed_path.name}.hmac")
    consumed_name = f"{armed['decision_id']}--{armed['slot_id']}"
    armed_path.replace(consumed / f"{consumed_name}.json")
    hmac_path.replace(consumed / f"{consumed_name}.json.hmac")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
