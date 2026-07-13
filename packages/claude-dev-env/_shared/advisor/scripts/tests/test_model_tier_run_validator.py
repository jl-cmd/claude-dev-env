"""Behavioral tests for the model-tier spawn-walk log validator."""

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_validator_module() -> ModuleType:
    scripts_root = Path(__file__).parent.parent
    constants_root = scripts_root / "config"
    sys.path.insert(0, str(constants_root))
    module_path = scripts_root / "model_tier_run_validator.py"
    specification = importlib.util.spec_from_file_location(
        "model_tier_run_validator", module_path
    )
    assert specification is not None
    assert specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    return module


model_tier_run_validator = _load_validator_module()
ModelTierRun = model_tier_run_validator.ModelTierRun
ModelTierRunError = model_tier_run_validator.ModelTierRunError
validate_model_tier_run = model_tier_run_validator.validate_model_tier_run
main = model_tier_run_validator.main
load_model_tier_run_from_json_path = (
    model_tier_run_validator.load_model_tier_run_from_json_path
)


def test_clean_single_spawn_at_top_of_slice_passes() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[{"tier": "Fable", "result": "spawned"}],
        selected_tier="Fable",
    )
    assert validate_model_tier_run(run) is None


def test_fallthrough_to_floor_tier_passes() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": "Opus", "result": "spawned"},
        ],
        selected_tier="Opus",
    )
    assert validate_model_tier_run(run) is None


def test_fully_exhausted_walk_with_fallback_reason_passes() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": "Opus", "result": "unavailable"},
        ],
        selected_tier=None,
        fallback_reason="every candidate tier failed; CLI fallback took over",
    )
    assert validate_model_tier_run(run) is None


def test_candidate_tiers_shorter_than_ladder_slice_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "spawned"}],
        selected_tier="Fable",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_attempt_tier_outside_candidate_slice_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[{"tier": "Haiku", "result": "spawned"}],
        selected_tier="Haiku",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_attempts_out_of_ladder_order_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[
            {"tier": "Opus", "result": "unavailable"},
            {"tier": "Fable", "result": "spawned"},
        ],
        selected_tier="Fable",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_selected_tier_not_first_spawned_attempt_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": "Opus", "result": "spawned"},
        ],
        selected_tier="Fable",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_exhausted_walk_with_non_null_selected_tier_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": "Opus", "result": "unavailable"},
        ],
        selected_tier="Opus",
        fallback_reason="every candidate tier failed",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_exhausted_walk_missing_fallback_reason_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": "Opus", "result": "unavailable"},
        ],
        selected_tier=None,
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_unknown_own_tier_raises() -> None:
    run = ModelTierRun(
        own_tier="Titan",
        candidate_tiers=["Titan"],
        attempts=[{"tier": "Titan", "result": "spawned"}],
        selected_tier="Titan",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_empty_attempts_with_null_selected_tier_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[],
        selected_tier=None,
        fallback_reason="skipped straight to CLI fallback",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_incomplete_fallback_walk_before_floor_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[{"tier": "Fable", "result": "unavailable"}],
        selected_tier=None,
        fallback_reason="stopped after Fable without trying Opus",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_lowercase_own_tier_and_candidates_pass() -> None:
    run = ModelTierRun(
        own_tier="opus",
        candidate_tiers=["fable", "opus"],
        attempts=[
            {"tier": "fable", "result": "unavailable"},
            {"tier": "opus", "result": "spawned"},
        ],
        selected_tier="opus",
    )
    assert validate_model_tier_run(run) is None


def test_cli_validates_json_log_file(tmp_path: Path) -> None:
    log_path = tmp_path / "model-tier-run.json"
    log_path.write_text(
        json.dumps(
            {
                "own_tier": "Opus",
                "candidate_tiers": ["Fable", "Opus"],
                "attempts": [{"tier": "Fable", "result": "spawned"}],
                "selected_tier": "Fable",
            }
        ),
        encoding="utf-8",
    )
    assert main([str(log_path)]) == 0
    loaded_run = load_model_tier_run_from_json_path(from_path=log_path)
    assert loaded_run.selected_tier == "Fable"


def test_cli_rejects_incomplete_fallback_log(tmp_path: Path) -> None:
    log_path = tmp_path / "incomplete-walk.json"
    log_path.write_text(
        json.dumps(
            {
                "own_tier": "Opus",
                "candidate_tiers": ["Fable", "Opus"],
                "attempts": [{"tier": "Fable", "result": "unavailable"}],
                "selected_tier": None,
                "fallback_reason": "incomplete",
            }
        ),
        encoding="utf-8",
    )
    assert main([str(log_path)]) == 1


def test_cli_missing_path_returns_usage_exit_code() -> None:
    assert main([]) == 2


def test_cli_bind_at_fable_passes() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[{"tier": "Fable", "result": "cli"}],
        selected_tier="Fable",
    )
    assert validate_model_tier_run(run) is None


def test_cli_bind_fallthrough_to_opus_passes() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": "Opus", "result": "cli"},
        ],
        selected_tier="Opus",
    )
    assert validate_model_tier_run(run) is None


def test_grok_own_tier_maps_to_fable_opus_cli_bind_passes() -> None:
    run = ModelTierRun(
        own_tier="Grok",
        candidate_tiers=["Fable", "Opus"],
        attempts=[{"tier": "Fable", "result": "cli"}],
        selected_tier="Fable",
    )
    assert validate_model_tier_run(run) is None


def test_grok_own_tier_lowercase_cli_bind_passes() -> None:
    run = ModelTierRun(
        own_tier="grok",
        candidate_tiers=["fable", "opus"],
        attempts=[{"tier": "fable", "result": "cli"}],
        selected_tier="fable",
    )
    assert validate_model_tier_run(run) is None


def test_self_token_is_not_bind_success_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[{"tier": "Fable", "result": "self"}],
        selected_tier="Fable",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_grok_self_token_is_not_bind_success_raises() -> None:
    run = ModelTierRun(
        own_tier="Grok",
        candidate_tiers=["Fable", "Opus"],
        attempts=[{"tier": "Fable", "result": "self"}],
        selected_tier="Fable",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_grok_host_legacy_single_tier_self_bind_raises() -> None:
    run = ModelTierRun(
        own_tier="Grok",
        candidate_tiers=["Grok"],
        attempts=[{"tier": "Grok", "result": "self"}],
        selected_tier="Grok",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_grok_cli_exhausted_fail_closed_passes() -> None:
    run = ModelTierRun(
        own_tier="Grok",
        candidate_tiers=["Fable", "Opus"],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": "Opus", "result": "unavailable"},
        ],
        selected_tier=None,
        fallback_reason=(
            "Grok host CLI Claude-chain exhausted; fail closed"
        ),
    )
    assert validate_model_tier_run(run) is None


def test_grok_cli_exhausted_without_fallback_reason_raises() -> None:
    run = ModelTierRun(
        own_tier="Grok",
        candidate_tiers=["Fable", "Opus"],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": "Opus", "result": "unavailable"},
        ],
        selected_tier=None,
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_grok_cli_selected_tier_mismatch_raises() -> None:
    run = ModelTierRun(
        own_tier="Grok",
        candidate_tiers=["Fable", "Opus"],
        attempts=[{"tier": "Fable", "result": "cli"}],
        selected_tier="Opus",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_claude_host_self_token_is_not_spawn_success_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[{"tier": "Fable", "result": "self"}],
        selected_tier="Fable",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)
