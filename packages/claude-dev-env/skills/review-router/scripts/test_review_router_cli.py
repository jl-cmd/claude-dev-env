"""CLI production-path acceptance tests."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
import pytest

import review_router_cli
from review_router_cli import arm, close, resolve

CLI = Path(__file__).with_name("review_router_cli.py")


def _initialized_repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repository, check=True)
    (repository / "README.md").write_text("test", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=repository, check=True)
    return repository


def _policy_naming(route_model: str) -> dict:
    dispatch = {"role": "executor", "model": route_model, "effort": "high", "pass_ids": ["simplify-01"]}
    route = {"status": "SUPPORTED", "skill": "e-simplify", "tiers": ["T1"], "models": {"T1": dispatch}}
    return {"version": 1, "routes": {"e-simplify": route}}


def test_arm_rejects_a_model_no_harness_can_resolve(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = _initialized_repository(tmp_path)
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "data"))
    monkeypatch.setattr(review_router_cli, "load_route_policy", lambda: _policy_naming("unknown-vendor-model"))
    resolved = resolve(str(repository), "e-simplify", "--tier 1", base_ref=None)
    with pytest.raises(ValueError, match="UNRESOLVABLE_ROUTE_MODEL"):
        arm(str(repository), resolved["decision_id"], resolved["slot_ids"][0])
    assert not list((tmp_path / "data").rglob("armed-spawn.json"))


def test_arm_accepts_the_tier_equivalent_model_the_shipped_policy_names(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = _initialized_repository(tmp_path)
    monkeypatch.setenv("CLAUDE_PLUGIN_DATA", str(tmp_path / "data"))
    monkeypatch.setattr(review_router_cli, "load_route_policy", lambda: _policy_naming("opus-equivalent"))
    resolved = resolve(str(repository), "e-simplify", "--tier 1", base_ref=None)
    armed = arm(str(repository), resolved["decision_id"], resolved["slot_ids"][0])
    assert armed["tool_input"]["model"] == "opus-equivalent"


def test_public_arm_and_close_reject_missing_signed_state(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        arm(str(tmp_path), "missing", "slot")
    with pytest.raises(OSError):
        close(str(tmp_path), "missing")


def test_cli_rejects_requested_dispatch(tmp_path: Path) -> None:
    command_result = subprocess.run(
        [sys.executable, str(CLI), "next", "--cwd", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert command_result.returncode != 0
    assert "invalid choice" in command_result.stderr


@pytest.mark.parametrize("arguments", ["--tier 4", "--tier", "--tier x", "--tier 1 --tier 2"])
def test_malformed_tier_override_writes_no_artifacts(tmp_path: Path, arguments: str) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    environment = {**os.environ, "CLAUDE_PLUGIN_DATA": str(tmp_path / "data")}
    command_result = subprocess.run([sys.executable, str(CLI), "resolve", "--cwd", str(repository), "--arguments", arguments], capture_output=True, text=True, env=environment)
    assert command_result.returncode != 0
    assert not (tmp_path / "data").exists()
