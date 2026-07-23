import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

CLI = Path(__file__).with_name("review_router_cli.py")
HOOKS = Path(__file__).resolve().parents[3] / "hooks" / "hooks.json"


def _registered_hook() -> Path:
    configuration = json.loads(HOOKS.read_text(encoding="utf-8"))
    commands = [hook["command"] for group in configuration["hooks"]["PreToolUse"] if group["matcher"] == "Agent|Task" for hook in group["hooks"] if hook["command"].endswith("route_review_spawn_permit.py")]
    assert len(commands) == 1
    command_tokens = commands[0].split()
    return Path(command_tokens[1].replace("${CLAUDE_PLUGIN_ROOT}", str(HOOKS.parent.parent)))


def _run(tmp_path: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return _run_with_plugin_data(tmp_path / "plugin-data", *arguments)


def _run_with_plugin_data(plugin_data: Path | None, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    if plugin_data is None:
        environment.pop("CLAUDE_PLUGIN_DATA", None)
    else:
        environment["CLAUDE_PLUGIN_DATA"] = str(plugin_data)
    return subprocess.run([sys.executable, str(CLI), *arguments], capture_output=True, text=True, env=environment)


def _repository(tmp_path: Path) -> Path:
    repository = tmp_path / "repository"
    repository.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repository, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repository, check=True)
    (repository / "README.md").write_text("test", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=repository, check=True)
    return repository


def test_e_simplify_command_matches_router_cli() -> None:
    assert "review_router_cli.py resolve" in (Path(__file__).resolve().parents[2] / "e-simplify" / "SKILL.md").read_text()


def test_resolve_writes_real_decision(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    command_result = _run(tmp_path, "resolve", "--review-kind", "e-simplify", "--cwd", str(repository), "--arguments", "--tier 2")
    assert command_result.returncode == 0
    assert json.loads(command_result.stdout)["effective_tier"] == "T2"
    assert list((tmp_path / "plugin-data").rglob("decision.json"))


def test_arm_derives_and_writes_real_spawn(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    resolved = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository), "--arguments", "--tier 1").stdout)
    armed = _run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0])
    assert json.loads(armed.stdout)["tool_input"]["model"] == "gpt-5.6-luna"
    assert list((tmp_path / "plugin-data").rglob("armed-spawn.json"))


def test_registered_hook_consumes_cli_armed_spawn(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    resolved = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository)).stdout)
    payload = json.loads(_run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0]).stdout)
    environment = {**os.environ, "CLAUDE_PLUGIN_DATA": str(tmp_path / "plugin-data")}
    hook = _registered_hook()
    hook_result = subprocess.run([sys.executable, str(hook)], input=json.dumps({"tool_name": "Agent", "cwd": str(repository), "tool_input": payload["tool_input"]}), capture_output=True, text=True, env=environment)
    assert hook_result.stdout == ""
    assert list((tmp_path / "plugin-data").rglob("consumed/*.json"))


def test_registered_hook_consumes_explicit_base_cli_armed_spawn(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    base_ref = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repository, check=True, capture_output=True, text=True).stdout.strip()
    (repository / "feature.py").write_text("feature\n", encoding="utf-8")
    subprocess.run(["git", "add", "feature.py"], cwd=repository, check=True)
    subprocess.run(["git", "commit", "-qm", "feature"], cwd=repository, check=True)
    resolved_result = _run(tmp_path, "resolve", "--cwd", str(repository), "--base-ref", base_ref)
    assert resolved_result.returncode == 0
    resolved = json.loads(resolved_result.stdout)
    decision = json.loads(next((tmp_path / "plugin-data").rglob("decision.json")).read_text(encoding="utf-8"))
    assert decision["base_source"] == "explicit"
    armed_result = _run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0])
    assert armed_result.returncode == 0
    payload = json.loads(armed_result.stdout)
    hook_result = _run_hook_payload(tmp_path, repository, payload["tool_input"])
    assert hook_result.returncode == 0
    assert hook_result.stdout == ""


def test_close_rejects_armed_then_closes_consumed_decision(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    resolved = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository)).stdout)
    armed = json.loads(_run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0]).stdout)
    assert _run(tmp_path, "close", "--cwd", str(repository), "--decision-id", resolved["decision_id"]).returncode != 0
    environment = {**os.environ, "CLAUDE_PLUGIN_DATA": str(tmp_path / "plugin-data")}
    hook = _registered_hook()
    subprocess.run([sys.executable, str(hook)], input=json.dumps({"tool_name": "Agent", "cwd": str(repository), "tool_input": armed["tool_input"]}), text=True, check=True, env=environment)
    assert _run(tmp_path, "close", "--cwd", str(repository), "--decision-id", resolved["decision_id"]).returncode == 0


@pytest.mark.parametrize(("override", "model", "effort", "slot_count"), [("1", "gpt-5.6-luna", "high", 1), ("2", "gpt-5.6-luna", "max", 1), ("3", "gpt-5.6-luna", "high", 6)])
def test_resolve_topology(override: str, model: str, effort: str, slot_count: int, tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    resolved = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository), "--arguments", f"--tier {override}").stdout)
    assert len(resolved["slot_ids"]) == slot_count
    armed = json.loads(_run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0]).stdout)
    assert armed["tool_input"]["model"] == model
    assert armed["tool_input"]["effort"] == effort


@pytest.mark.parametrize("mutation", ["model", "effort", "prompt"])
def test_registered_hook_blocks_mutation_and_preserves_armed_spawn(mutation: str, tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    resolved = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository)).stdout)
    armed = json.loads(_run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0]).stdout)
    tool_input = dict(armed["tool_input"])
    tool_input[mutation] = "mutated"
    environment = {**os.environ, "CLAUDE_PLUGIN_DATA": str(tmp_path / "plugin-data")}
    armed_path = next((tmp_path / "plugin-data").rglob("armed-spawn.json"))
    original = armed_path.read_bytes()
    hook_result = subprocess.run([sys.executable, str(_registered_hook())], input=json.dumps({"tool_name": "Agent", "cwd": str(repository), "tool_input": tool_input}), text=True, capture_output=True, env=environment)
    assert "ROUTE_SPAWN_MISMATCH" in hook_result.stdout
    assert armed_path.read_bytes() == original


def test_registered_hook_no_decision_allows(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    environment = {**os.environ, "CLAUDE_PLUGIN_DATA": str(tmp_path / "plugin-data")}
    hook_result = subprocess.run([sys.executable, str(_registered_hook())], input=json.dumps({"tool_name": "Agent", "cwd": str(repository), "tool_input": {}}), text=True, capture_output=True, env=environment)
    assert hook_result.stdout == ""


def test_resolve_unsupported_e_code_review_writes_zero_artifacts(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    command_result = _run(tmp_path, "resolve", "--review-kind", "e-code-review", "--cwd", str(repository))
    assert json.loads(command_result.stdout)["status"] == "UNSUPPORTED_ROUTE"
    assert not (tmp_path / "plugin-data").exists()


def test_hook_blocks_content_stale_decision(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    resolved = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository)).stdout)
    _run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0])
    (repository / "README.md").write_text("changed", encoding="utf-8")
    hook_result = _run_hook(tmp_path, repository)
    assert "ROUTE_SPAWN_MISMATCH" in hook_result.stdout


def test_hook_blocks_invalid_partial_and_tampered_decision_state(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _run(tmp_path, "resolve", "--cwd", str(repository))
    decision_path = next((tmp_path / "plugin-data").rglob("decision.json"))
    decision_path.with_name("decision.json.hmac").unlink()
    hook_result = _run_hook(tmp_path, repository)
    assert "ROUTE_SPAWN_MISMATCH" in hook_result.stdout


def test_hook_blocks_when_surface_recomputation_errors(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    resolved = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository)).stdout)
    _run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0])
    (repository / ".git" / "HEAD").write_text("invalid\n", encoding="utf-8")
    hook_result = _run_hook(tmp_path, repository)
    assert "ROUTE_SPAWN_MISMATCH" in hook_result.stdout


def test_consumption_moves_armed_json_and_hmac_together(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    resolved = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository)).stdout)
    payload = json.loads(_run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0]).stdout)
    hook_result = _run_hook_payload(tmp_path, repository, payload["tool_input"])
    assert hook_result.stdout == ""
    consumed = list((tmp_path / "plugin-data").rglob("consumed/*"))
    assert len(consumed) == 2
    assert any(path.suffix == ".hmac" for path in consumed)


def test_consumed_slot_is_scoped_to_decision_id(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    first = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository)).stdout)
    _consume_first_slot(tmp_path, repository, first)
    second = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository)).stdout)
    assert _run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", second["decision_id"], "--slot", second["slot_ids"][0]).returncode == 0


def test_t3_arm_rejects_reuse_and_out_of_order_slot(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    resolved = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository), "--arguments", "--tier 3").stdout)
    assert _run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][1]).returncode != 0
    payload = json.loads(_run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0]).stdout)
    _run_hook_payload(tmp_path, repository, payload["tool_input"])
    assert _run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0]).returncode != 0


def test_arbitrary_unsupported_review_kind_writes_zero_artifacts(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    route_result = _run(tmp_path, "resolve", "--review-kind", "unknown-route", "--cwd", str(repository))
    assert json.loads(route_result.stdout)["status"] == "UNSUPPORTED_ROUTE"
    assert not (tmp_path / "plugin-data").exists()


def test_every_route_prompt_contains_full_upstream_cleanup_contract(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    for tier in ("1", "2", "3"):
        resolved = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository), "--arguments", f"--tier {tier}").stdout)
        for slot_id in resolved["slot_ids"]:
            payload = json.loads(_run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", slot_id).stdout)
            prompt = payload["tool_input"]["prompt"]
            assert all(angle in prompt for angle in ("Reuse", "Simplification", "Efficiency", "Altitude"))
            assert "direct fixes" in prompt and "Skip" in prompt
            _run_hook_payload(tmp_path, repository, payload["tool_input"])
        _run(tmp_path, "close", "--cwd", str(repository), "--decision-id", resolved["decision_id"])


def test_router_tier_and_hook_import_together_without_config_collision(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    route_result = _run(tmp_path, "resolve", "--cwd", str(repository))
    assert route_result.returncode == 0
    assert json.loads(route_result.stdout)["status"] == "SUPPORTED"


def test_default_plugin_data_inside_repo_is_excluded_from_hook_recomputation(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    resolved = json.loads(_run_with_plugin_data(None, "resolve", "--cwd", str(repository)).stdout)
    armed = json.loads(_run_with_plugin_data(None, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0]).stdout)
    hook_result = subprocess.run([sys.executable, str(_registered_hook())], input=json.dumps({"tool_name": "Agent", "cwd": str(repository), "tool_input": armed["tool_input"]}), capture_output=True, text=True, env={environment_key: environment_value for environment_key, environment_value in os.environ.items() if environment_key != "CLAUDE_PLUGIN_DATA"})
    assert hook_result.stdout == ""


def test_explicit_plugin_data_inside_repo_is_excluded_from_inventory(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    plugin_data = repository / ".claude-plugin-data"
    resolved = json.loads(_run_with_plugin_data(plugin_data, "resolve", "--cwd", str(repository)).stdout)
    assert resolved["status"] == "SUPPORTED"
    decision = json.loads(next((plugin_data / "review-routing").rglob("decision.json")).read_text(encoding="utf-8"))
    assert decision["evidence"]["files"] == 0
    assert decision["evidence"]["packages"] == 0


def test_external_plugin_data_records_state_root_identity_and_hook_validates_it(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    plugin_data = tmp_path / "external-plugin-data"
    resolved = json.loads(_run_with_plugin_data(plugin_data, "resolve", "--cwd", str(repository)).stdout)
    decision = json.loads(next((plugin_data / "review-routing").rglob("decision.json")).read_text(encoding="utf-8"))
    assert decision["state_root_id"]
    armed = json.loads(_run_with_plugin_data(plugin_data, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0]).stdout)
    assert armed["tool_input"]["prompt"]


def test_resolve_close_resolve_preserves_tier_and_diff_hash_without_user_change(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    first = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository)).stdout)
    decision_path = next((tmp_path / "plugin-data").rglob("decision.json"))
    first_decision = json.loads(decision_path.read_text(encoding="utf-8"))
    assert _run(tmp_path, "close", "--cwd", str(repository), "--decision-id", first["decision_id"]).returncode == 0
    second = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository)).stdout)
    second_decision = json.loads(next((tmp_path / "plugin-data").rglob("decision.json")).read_text(encoding="utf-8"))
    assert second["automatic_tier"] == first["automatic_tier"]
    assert second_decision["diff_hash"] == first_decision["diff_hash"]


def test_real_user_edit_changes_hash_and_blocks_armed_spawn(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    resolved = json.loads(_run(tmp_path, "resolve", "--cwd", str(repository)).stdout)
    armed = json.loads(_run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0]).stdout)
    (repository / "README.md").write_text("user edit", encoding="utf-8")
    hook_result = _run_hook_payload(tmp_path, repository, armed["tool_input"])
    assert "ROUTE_SPAWN_MISMATCH" in hook_result.stdout


def test_sibling_named_paths_remain_included_in_hash(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    plugin_data = repository / ".claude-plugin-data"
    for relative_path in ("user.txt", "review-routing/v2/user.txt"):
        target = plugin_data / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(relative_path, encoding="utf-8")
    for relative_path in ("other/review-routing/v1/user.txt", "review-routing/v1-copy/user.txt"):
        target = repository / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(relative_path, encoding="utf-8")
    first = json.loads(_run_with_plugin_data(plugin_data, "resolve", "--cwd", str(repository)).stdout)
    (repository / "other/review-routing/v1/user.txt").write_text("changed", encoding="utf-8")
    second = json.loads(_run_with_plugin_data(plugin_data, "resolve", "--cwd", str(repository)).stdout)
    assert second["decision_id"] != first["decision_id"]


def test_normalized_and_symlinked_state_roots_exclude_consistently(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    plugin_data = tmp_path / "plugin-data"
    symlinked = tmp_path / "plugin-link"
    symlinked.symlink_to(plugin_data, target_is_directory=True)
    first = json.loads(_run_with_plugin_data(plugin_data / "nested" / "..", "resolve", "--cwd", str(repository)).stdout)
    second = json.loads(_run_with_plugin_data(symlinked, "resolve", "--cwd", str(repository)).stdout)
    first_decision = json.loads(next((plugin_data / "review-routing").rglob("decision.json")).read_text(encoding="utf-8"))
    assert first_decision["evidence"]["files"] == 0
    assert first["automatic_tier"] == second["automatic_tier"]


def test_tracked_file_under_runtime_root_fails_closed(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    state_file = repository / ".claude-plugin-data" / "review-routing" / "v1" / "tracked.txt"
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text("tracked", encoding="utf-8")
    subprocess.run(["git", "add", str(state_file)], cwd=repository, check=True)
    route_result = _run_with_plugin_data(repository / ".claude-plugin-data", "resolve", "--cwd", str(repository))
    assert "ROUTING_STATE_ROOT_TRACKED" in route_result.stderr


def _run_hook_payload(tmp_path: Path, repository: Path, tool_input: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(_registered_hook())], input=json.dumps({"tool_name": "Agent", "cwd": str(repository), "tool_input": tool_input}), capture_output=True, text=True, env={**os.environ, "CLAUDE_PLUGIN_DATA": str(tmp_path / "plugin-data")})


def _run_hook(tmp_path: Path, repository: Path) -> subprocess.CompletedProcess[str]:
    armed_paths = list((tmp_path / "plugin-data").rglob("armed-spawn.json"))
    if not armed_paths:
        return _run_hook_payload(tmp_path, repository, {})
    armed = json.loads(armed_paths[0].read_text(encoding="utf-8"))
    return _run_hook_payload(tmp_path, repository, {key: armed[key] for key in ("executor_type", "model", "effort", "prompt")})


def _consume_first_slot(tmp_path: Path, repository: Path, resolved: dict) -> None:
    payload = json.loads(_run(tmp_path, "arm", "--cwd", str(repository), "--decision-id", resolved["decision_id"], "--slot", resolved["slot_ids"][0]).stdout)
    _run_hook_payload(tmp_path, repository, payload["tool_input"])
