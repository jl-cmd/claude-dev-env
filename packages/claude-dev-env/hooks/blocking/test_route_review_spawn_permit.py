import hashlib
import hmac
import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).with_name("route_review_spawn_permit.py")


def _route_directory(data_root: Path, worktree: Path) -> Path:
    key = hashlib.sha256(str(worktree.resolve()).encode()).hexdigest()
    return data_root / "review-routing" / "v1" / key


def _write_record(directory: Path, name: str, record: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    secret = b"test-secret"
    (directory / "integrity.key").write_bytes(secret)
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    (directory / name).write_bytes(encoded)
    (directory / f"{name}.hmac").write_text(hmac.new(secret, encoded, hashlib.sha256).hexdigest())


def test_no_decision_preserves_allow_behavior(tmp_path: Path) -> None:
    result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"tool_name": "Agent", "cwd": str(tmp_path)}), text=True, capture_output=True)
    assert result.returncode == 0
    assert result.stdout == ""


def test_active_decision_requires_exact_armed_spawn(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    route_directory = _route_directory(data_root, tmp_path)
    decision = {"decision_id": "d1", "worktree": str(tmp_path.resolve())}
    armed_spawn = {"decision_id": "d1", "slot_id": "slot-1", "tool_name": "Agent", "executor_type": "Luna", "model": "gpt-5.6-luna", "effort": "high", "prompt_hash": "p"}
    _write_record(route_directory, "decision.json", decision)
    _write_record(route_directory, "armed-spawn.json", armed_spawn)
    environment = {**os.environ, "CLAUDE_PLUGIN_DATA": str(data_root)}
    payload = {"tool_name": "Agent", "cwd": str(tmp_path), "tool_input": {"model": "wrong", "prompt": "x"}}
    result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), text=True, capture_output=True, env=environment)
    assert "ROUTE_SPAWN_MISMATCH" in result.stdout
    assert (route_directory / "armed-spawn.json").exists()


def test_signed_record_without_integrity_key_blocks(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    route_directory = _route_directory(data_root, tmp_path)
    _write_record(route_directory, "decision.json", {"decision_id": "d1"})
    (route_directory / "integrity.key").unlink()
    environment = {**os.environ, "CLAUDE_PLUGIN_DATA": str(data_root)}
    payload = {"tool_name": "Agent", "cwd": str(tmp_path)}
    result = subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload), text=True, capture_output=True, env=environment)
    assert result.returncode == 0
    assert json.loads(result.stdout)["hookSpecificOutput"]["permissionDecisionReason"] == "ROUTE_SPAWN_MISMATCH"
    assert result.stderr == ""
