"""Behavioral tests for the model-tier spawn-walk log validator."""

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest


def _load_validator_module() -> ModuleType:
    module_path = Path(__file__).parent.parent / "model_tier_run_validator.py"
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
