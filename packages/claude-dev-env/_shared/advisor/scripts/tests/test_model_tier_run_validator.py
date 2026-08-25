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
ADVISOR_MODEL_TIER = model_tier_run_validator.ADVISOR_MODEL_TIER
CODEX_BIND_SUCCESS_TOKEN = model_tier_run_validator.CODEX_BIND_SUCCESS_TOKEN


def test_clean_single_spawn_at_top_of_slice_passes() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "spawned"}],
        selected_tier="Fable",
    )
    assert validate_model_tier_run(run) is None


def test_sol_codex_bind_succeeds_after_fable_when_enabled() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", ADVISOR_MODEL_TIER],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": ADVISOR_MODEL_TIER, "result": CODEX_BIND_SUCCESS_TOKEN},
        ],
        selected_tier=ADVISOR_MODEL_TIER,
        is_sol_enabled=True,
    )
    assert validate_model_tier_run(run) is None


def test_fable_success_with_sol_enabled_stops_before_sol() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", ADVISOR_MODEL_TIER],
        attempts=[{"tier": "Fable", "result": "spawned"}],
        selected_tier="Fable",
        is_sol_enabled=True,
    )
    assert validate_model_tier_run(run) is None


def test_sol_first_walk_raises_when_sol_is_enabled() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=[ADVISOR_MODEL_TIER, "Fable"],
        attempts=[{"tier": ADVISOR_MODEL_TIER, "result": CODEX_BIND_SUCCESS_TOKEN}],
        selected_tier=ADVISOR_MODEL_TIER,
        is_sol_enabled=True,
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_sol_rung_follows_fable_on_third_party_cli_floor_when_enabled() -> None:
    run = ModelTierRun(
        own_tier="ThirdParty",
        candidate_tiers=["Fable", ADVISOR_MODEL_TIER],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": ADVISOR_MODEL_TIER, "result": CODEX_BIND_SUCCESS_TOKEN},
        ],
        selected_tier=ADVISOR_MODEL_TIER,
        is_sol_enabled=True,
    )

    assert validate_model_tier_run(run) is None


def test_sol_codex_result_requires_sol_candidate() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": CODEX_BIND_SUCCESS_TOKEN}],
        selected_tier="Fable",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_sol_spawned_result_does_not_count_as_codex_success() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", ADVISOR_MODEL_TIER],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": ADVISOR_MODEL_TIER, "result": "spawned"},
        ],
        selected_tier=ADVISOR_MODEL_TIER,
        is_sol_enabled=True,
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_exhausted_fable_walk_fails_closed() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "unavailable"}],
        selected_tier=None,
        fallback_reason="Fable did not bind; no advisor",
    )
    assert validate_model_tier_run(run) is None


def test_fully_exhausted_walk_with_fallback_reason_passes() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "unavailable"}],
        selected_tier=None,
        fallback_reason="every candidate tier failed",
    )
    assert validate_model_tier_run(run) is None


def test_opus_candidate_on_advisor_walk_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[{"tier": "Fable", "result": "spawned"}],
        selected_tier="Fable",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_attempt_tier_outside_candidate_slice_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Haiku", "result": "spawned"}],
        selected_tier="Haiku",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_attempts_out_of_ladder_order_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", ADVISOR_MODEL_TIER],
        attempts=[
            {"tier": ADVISOR_MODEL_TIER, "result": CODEX_BIND_SUCCESS_TOKEN},
            {"tier": "Fable", "result": "unavailable"},
        ],
        selected_tier=ADVISOR_MODEL_TIER,
        is_sol_enabled=True,
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_selected_tier_not_first_spawned_attempt_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", ADVISOR_MODEL_TIER],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": ADVISOR_MODEL_TIER, "result": CODEX_BIND_SUCCESS_TOKEN},
        ],
        selected_tier="Fable",
        is_sol_enabled=True,
    )
    with pytest.raises(
        ModelTierRunError,
        match=(
            "selected_tier does not match the first successful bind "
            r"\(spawned or cli\)"
        ),
    ):
        validate_model_tier_run(run)


def test_exhausted_walk_with_non_null_selected_tier_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "unavailable"}],
        selected_tier="Fable",
        fallback_reason="every candidate tier failed",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_exhausted_walk_missing_fallback_reason_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "unavailable"}],
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
        candidate_tiers=["Fable"],
        attempts=[],
        selected_tier=None,
        fallback_reason="skipped straight to CLI fallback",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_incomplete_fallback_walk_before_sol_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", ADVISOR_MODEL_TIER],
        attempts=[{"tier": "Fable", "result": "unavailable"}],
        selected_tier=None,
        fallback_reason="stopped after Fable without trying Sol",
        is_sol_enabled=True,
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_lowercase_own_tier_and_candidates_pass() -> None:
    run = ModelTierRun(
        own_tier="opus",
        candidate_tiers=["fable"],
        attempts=[{"tier": "fable", "result": "spawned"}],
        selected_tier="fable",
    )
    assert validate_model_tier_run(run) is None


def test_cli_validates_json_log_file(tmp_path: Path) -> None:
    log_path = tmp_path / "model-tier-run.json"
    log_path.write_text(
        json.dumps(
            {
                "own_tier": "Opus",
                "candidate_tiers": ["Fable"],
                "attempts": [{"tier": "Fable", "result": "spawned"}],
                "selected_tier": "Fable",
            }
        ),
        encoding="utf-8",
    )
    assert main([str(log_path)]) == 0
    loaded_run = load_model_tier_run_from_json_path(from_path=log_path)
    assert loaded_run.selected_tier == "Fable"
    assert loaded_run.host_profile == "Claude"


def test_cli_rejects_non_string_host_profile(tmp_path: Path) -> None:
    log_path = tmp_path / "invalid-host-profile.json"
    log_path.write_text(
        json.dumps(
            {
                "own_tier": "Opus",
                "candidate_tiers": ["Fable"],
                "attempts": [{"tier": "Fable", "result": "spawned"}],
                "selected_tier": "Fable",
                "host_profile": 1,
            }
        ),
        encoding="utf-8",
    )
    assert main([str(log_path)]) == 2


def test_cli_rejects_non_boolean_sol_enabled(tmp_path: Path) -> None:
    log_path = tmp_path / "invalid-sol-enabled.json"
    log_path.write_text(
        json.dumps(
            {
                "own_tier": "Opus",
                "candidate_tiers": ["Fable"],
                "attempts": [{"tier": "Fable", "result": "spawned"}],
                "selected_tier": "Fable",
                "sol_enabled": "false",
            }
        ),
        encoding="utf-8",
    )
    assert main([str(log_path)]) == 2


def test_cli_rejects_incomplete_fallback_log(tmp_path: Path) -> None:
    log_path = tmp_path / "incomplete-walk.json"
    log_path.write_text(
        json.dumps(
            {
                "own_tier": "Opus",
                "candidate_tiers": ["Fable", "Sol"],
                "attempts": [{"tier": "Fable", "result": "unavailable"}],
                "selected_tier": None,
                "fallback_reason": "incomplete",
                "sol_enabled": True,
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
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "cli"}],
        selected_tier="Fable",
    )
    assert validate_model_tier_run(run) is None


def test_cli_bind_fallthrough_to_opus_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", "Opus"],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": "Opus", "result": "cli"},
        ],
        selected_tier="Opus",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_third_party_own_tier_maps_to_fable_cli_bind_passes() -> None:
    run = ModelTierRun(
        own_tier="ThirdParty",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "cli"}],
        selected_tier="Fable",
    )
    assert validate_model_tier_run(run) is None


def test_third_party_own_tier_lowercase_cli_bind_passes() -> None:
    run = ModelTierRun(
        own_tier="thirdparty",
        candidate_tiers=["fable"],
        attempts=[{"tier": "fable", "result": "cli"}],
        selected_tier="fable",
    )
    assert validate_model_tier_run(run) is None


def test_self_token_is_not_bind_success_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "self"}],
        selected_tier="Fable",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_third_party_self_token_is_not_bind_success_raises() -> None:
    run = ModelTierRun(
        own_tier="ThirdParty",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "self"}],
        selected_tier="Fable",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_third_party_host_legacy_single_tier_self_bind_raises() -> None:
    run = ModelTierRun(
        own_tier="ThirdParty",
        candidate_tiers=["ThirdParty"],
        attempts=[{"tier": "ThirdParty", "result": "self"}],
        selected_tier="ThirdParty",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_third_party_cli_exhausted_fail_closed_passes() -> None:
    run = ModelTierRun(
        own_tier="ThirdParty",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "unavailable"}],
        selected_tier=None,
        fallback_reason=(
            "third-party host CLI Claude-chain exhausted; fail closed"
        ),
    )
    assert validate_model_tier_run(run) is None


def test_third_party_cli_exhausted_without_fallback_reason_raises() -> None:
    run = ModelTierRun(
        own_tier="ThirdParty",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "unavailable"}],
        selected_tier=None,
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_third_party_cli_selected_tier_mismatch_raises() -> None:
    run = ModelTierRun(
        own_tier="ThirdParty",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "cli"}],
        selected_tier="Opus",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_claude_host_self_token_is_not_spawn_success_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "self"}],
        selected_tier="Fable",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_codex_host_sol_in_session_spawn_passes() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=[ADVISOR_MODEL_TIER],
        attempts=[{"tier": ADVISOR_MODEL_TIER, "result": "spawned"}],
        selected_tier=ADVISOR_MODEL_TIER,
        host_profile="Codex",
    )
    assert validate_model_tier_run(run) is None


def test_codex_host_sol_codex_token_counts_as_success() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=[ADVISOR_MODEL_TIER],
        attempts=[
            {"tier": ADVISOR_MODEL_TIER, "result": CODEX_BIND_SUCCESS_TOKEN}
        ],
        selected_tier=ADVISOR_MODEL_TIER,
        host_profile="Codex",
    )
    assert validate_model_tier_run(run) is None


def test_codex_host_fable_then_sol_walk_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", ADVISOR_MODEL_TIER],
        attempts=[{"tier": ADVISOR_MODEL_TIER, "result": "spawned"}],
        selected_tier=ADVISOR_MODEL_TIER,
        is_sol_enabled=True,
        host_profile="Codex",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_codex_host_exhausted_sol_fails_closed() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=[ADVISOR_MODEL_TIER],
        attempts=[{"tier": ADVISOR_MODEL_TIER, "result": "unavailable"}],
        selected_tier=None,
        fallback_reason="Codex in-session Sol spawn did not bind",
        host_profile="Codex",
    )
    assert validate_model_tier_run(run) is None


def test_cli_loads_codex_host_profile(tmp_path: Path) -> None:
    log_path = tmp_path / "codex-host-walk.json"
    log_path.write_text(
        json.dumps(
            {
                "own_tier": "Opus",
                "candidate_tiers": ["Sol"],
                "attempts": [{"tier": "Sol", "result": "spawned"}],
                "selected_tier": "Sol",
                "host_profile": "Codex",
            }
        ),
        encoding="utf-8",
    )
    assert main([str(log_path)]) == 0
    loaded_run = load_model_tier_run_from_json_path(from_path=log_path)
    assert loaded_run.host_profile == "Codex"
