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
EVIDENCE_MUST_BE_OBJECT_MESSAGE = (
    model_tier_run_validator.EVIDENCE_MUST_BE_OBJECT_MESSAGE
)


def _native_codex_evidence(
    *,
    reply_path: str = "native",
    reference_status: str = "missing",
    advisor_flag: str | None = "passed",
) -> dict[str, object]:
    fallback: dict[str, object] = {
        "selected_tier": "Astra",
        "fallback_kind": None,
        "fallback_reason": None,
        "reply_path": reply_path,
    }
    if advisor_flag is not None:
        fallback["advisor_flag"] = advisor_flag
    return {
        "schema_version": 1,
        "reference": {
            "path": "~/.claude/docs/references/advisor-tool.md",
            "status": reference_status,
            "repair_action": "use the projected docs root",
            "repair_result": "read",
        },
        "fallback": fallback,
        "consult": {
            "changed_evidence": ["native bind returned a reply"],
            "validation": ["signal and session id read back"],
            "unresolved_risks": ["optional reference projection"],
            "report_back_status": "recorded",
        },
    }


def test_codex_native_bind_and_reply_readback_validate() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=[ADVISOR_MODEL_TIER],
        attempts=[{"tier": ADVISOR_MODEL_TIER, "result": "spawned"}],
        selected_tier=ADVISOR_MODEL_TIER,
        host_profile="Codex",
        evidence=_native_codex_evidence(),
    )

    assert validate_model_tier_run(run) is None


def test_codex_native_success_rejects_non_native_reply_path() -> None:
    evidence = _native_codex_evidence(reply_path="cli")
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=[ADVISOR_MODEL_TIER],
        attempts=[{"tier": ADVISOR_MODEL_TIER, "result": "spawned"}],
        selected_tier=ADVISOR_MODEL_TIER,
        host_profile="Codex",
        evidence=evidence,
    )

    with pytest.raises(ModelTierRunError, match="native reply path"):
        validate_model_tier_run(run)


def _codex_astra_success_run(evidence: dict[str, object]) -> ModelTierRun:
    return ModelTierRun(
        own_tier="Opus",
        candidate_tiers=[ADVISOR_MODEL_TIER],
        attempts=[{"tier": ADVISOR_MODEL_TIER, "result": "spawned"}],
        selected_tier=ADVISOR_MODEL_TIER,
        host_profile="Codex",
        evidence=evidence,
    )


def test_codex_plain_astra_spawn_binds_when_host_lacks_advisor_flag() -> None:
    run = _codex_astra_success_run(
        _native_codex_evidence(advisor_flag="unavailable")
    )

    assert validate_model_tier_run(run) is None


def test_codex_astra_spawn_that_skips_offered_advisor_flag_fails_closed() -> None:
    run = _codex_astra_success_run(_native_codex_evidence(advisor_flag="omitted"))

    with pytest.raises(ModelTierRunError, match="--advisor"):
        validate_model_tier_run(run)


def test_codex_astra_success_without_advisor_flag_record_fails_closed() -> None:
    run = _codex_astra_success_run(_native_codex_evidence(advisor_flag=None))

    with pytest.raises(ModelTierRunError, match="advisor_flag"):
        validate_model_tier_run(run)


def test_unknown_advisor_flag_state_is_rejected() -> None:
    run = _codex_astra_success_run(_native_codex_evidence(advisor_flag="skipped"))

    with pytest.raises(ModelTierRunError, match="advisor_flag"):
        validate_model_tier_run(run)


def test_broken_bind_keeps_fallback_evidence_separate_from_reference_gap() -> None:
    evidence = _native_codex_evidence()
    evidence["fallback"] = {
        "selected_tier": None,
        "fallback_kind": "broken",
        "fallback_reason": "native Astra bind failed",
        "reply_path": "none",
    }
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=[ADVISOR_MODEL_TIER],
        attempts=[{"tier": ADVISOR_MODEL_TIER, "result": "unavailable"}],
        selected_tier=None,
        fallback_reason="native Astra bind failed",
        host_profile="Codex",
        evidence=evidence,
    )

    assert validate_model_tier_run(run) is None


def test_cli_reads_versioned_advisor_evidence(tmp_path: Path) -> None:
    log_path = tmp_path / "model-tier-run.json"
    log_path.write_text(
        json.dumps(
            {
                "own_tier": "Opus",
                "candidate_tiers": [ADVISOR_MODEL_TIER],
                "attempts": [{"tier": ADVISOR_MODEL_TIER, "result": "spawned"}],
                "selected_tier": ADVISOR_MODEL_TIER,
                "host_profile": "Codex",
                "evidence": _native_codex_evidence(reference_status="read"),
            }
        ),
        encoding="utf-8",
    )

    assert main([str(log_path)]) == 0
    loaded_run = load_model_tier_run_from_json_path(from_path=log_path)
    assert loaded_run.evidence is not None
    assert loaded_run.evidence["consult"]["report_back_status"] == "recorded"


def test_non_object_evidence_reports_the_same_message_at_validate_and_load(
    tmp_path: Path,
) -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=[ADVISOR_MODEL_TIER],
        attempts=[{"tier": ADVISOR_MODEL_TIER, "result": "spawned"}],
        selected_tier=ADVISOR_MODEL_TIER,
        host_profile="Codex",
        evidence=["not", "an", "object"],
    )
    with pytest.raises(ModelTierRunError, match=EVIDENCE_MUST_BE_OBJECT_MESSAGE):
        validate_model_tier_run(run)

    log_path = tmp_path / "model-tier-run.json"
    log_path.write_text(
        json.dumps(
            {
                "own_tier": "Opus",
                "candidate_tiers": [ADVISOR_MODEL_TIER],
                "attempts": [{"tier": ADVISOR_MODEL_TIER, "result": "spawned"}],
                "selected_tier": ADVISOR_MODEL_TIER,
                "host_profile": "Codex",
                "evidence": "not an object",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(TypeError, match=EVIDENCE_MUST_BE_OBJECT_MESSAGE):
        load_model_tier_run_from_json_path(from_path=log_path)


def test_clean_single_spawn_at_top_of_slice_passes() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "spawned"}],
        selected_tier="Fable",
    )
    assert validate_model_tier_run(run) is None


def test_astra_codex_bind_succeeds_after_fable_when_enabled() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", ADVISOR_MODEL_TIER],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": ADVISOR_MODEL_TIER, "result": CODEX_BIND_SUCCESS_TOKEN},
        ],
        selected_tier=ADVISOR_MODEL_TIER,
        is_astra_enabled=True,
    )
    assert validate_model_tier_run(run) is None


def test_fable_success_with_astra_enabled_stops_before_astra() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", ADVISOR_MODEL_TIER],
        attempts=[{"tier": "Fable", "result": "spawned"}],
        selected_tier="Fable",
        is_astra_enabled=True,
    )
    assert validate_model_tier_run(run) is None


def test_astra_first_walk_raises_when_astra_is_enabled() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=[ADVISOR_MODEL_TIER, "Fable"],
        attempts=[{"tier": ADVISOR_MODEL_TIER, "result": CODEX_BIND_SUCCESS_TOKEN}],
        selected_tier=ADVISOR_MODEL_TIER,
        is_astra_enabled=True,
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_astra_rung_follows_fable_on_third_party_cli_floor_when_enabled() -> None:
    run = ModelTierRun(
        own_tier="ThirdParty",
        candidate_tiers=["Fable", ADVISOR_MODEL_TIER],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": ADVISOR_MODEL_TIER, "result": CODEX_BIND_SUCCESS_TOKEN},
        ],
        selected_tier=ADVISOR_MODEL_TIER,
        is_astra_enabled=True,
        host_profile="ThirdParty",
    )

    assert validate_model_tier_run(run) is None


def test_astra_codex_result_requires_astra_candidate() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": CODEX_BIND_SUCCESS_TOKEN}],
        selected_tier="Fable",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_astra_spawned_result_does_not_count_as_codex_success() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", ADVISOR_MODEL_TIER],
        attempts=[
            {"tier": "Fable", "result": "unavailable"},
            {"tier": ADVISOR_MODEL_TIER, "result": "spawned"},
        ],
        selected_tier=ADVISOR_MODEL_TIER,
        is_astra_enabled=True,
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
        is_astra_enabled=True,
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
        is_astra_enabled=True,
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


def test_incomplete_fallback_walk_before_astra_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", ADVISOR_MODEL_TIER],
        attempts=[{"tier": "Fable", "result": "unavailable"}],
        selected_tier=None,
        fallback_reason="stopped after Fable without trying Astra",
        is_astra_enabled=True,
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


def test_cli_rejects_non_boolean_astra_enabled(tmp_path: Path) -> None:
    log_path = tmp_path / "invalid-astra-enabled.json"
    log_path.write_text(
        json.dumps(
            {
                "own_tier": "Opus",
                "candidate_tiers": ["Fable"],
                "attempts": [{"tier": "Fable", "result": "spawned"}],
                "selected_tier": "Fable",
                "astra_enabled": "false",
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
                "candidate_tiers": ["Fable", "Astra"],
                "attempts": [{"tier": "Fable", "result": "unavailable"}],
                "selected_tier": None,
                "fallback_reason": "incomplete",
                "astra_enabled": True,
            }
        ),
        encoding="utf-8",
    )
    assert main([str(log_path)]) == 1


def test_cli_loads_astra_enabled_fallback_walk(tmp_path: Path) -> None:
    log_path = tmp_path / "astra-enabled-walk.json"
    log_path.write_text(
        json.dumps(
            {
                "own_tier": "ThirdParty",
                "host_profile": "ThirdParty",
                "candidate_tiers": ["Fable", "Astra"],
                "attempts": [
                    {"tier": "Fable", "result": "unavailable"},
                    {"tier": "Astra", "result": "codex"},
                ],
                "selected_tier": "Astra",
                "astra_enabled": True,
            }
        ),
        encoding="utf-8",
    )
    assert main([str(log_path)]) == 0
    loaded_run = load_model_tier_run_from_json_path(from_path=log_path)
    assert loaded_run.is_astra_enabled
    assert loaded_run.selected_tier == "Astra"


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


def test_codex_host_astra_in_session_spawn_passes() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=[ADVISOR_MODEL_TIER],
        attempts=[{"tier": ADVISOR_MODEL_TIER, "result": "spawned"}],
        selected_tier=ADVISOR_MODEL_TIER,
        host_profile="Codex",
    )
    assert validate_model_tier_run(run) is None


def test_codex_host_astra_codex_token_counts_as_success() -> None:
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


def test_codex_host_fable_then_astra_walk_raises() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable", ADVISOR_MODEL_TIER],
        attempts=[{"tier": ADVISOR_MODEL_TIER, "result": "spawned"}],
        selected_tier=ADVISOR_MODEL_TIER,
        is_astra_enabled=True,
        host_profile="Codex",
    )
    with pytest.raises(ModelTierRunError):
        validate_model_tier_run(run)


def test_codex_host_exhausted_astra_fails_closed() -> None:
    run = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=[ADVISOR_MODEL_TIER],
        attempts=[{"tier": ADVISOR_MODEL_TIER, "result": "unavailable"}],
        selected_tier=None,
        fallback_reason="Codex in-session Astra spawn did not bind",
        host_profile="Codex",
    )
    assert validate_model_tier_run(run) is None


def test_cli_loads_codex_host_profile(tmp_path: Path) -> None:
    log_path = tmp_path / "codex-host-walk.json"
    log_path.write_text(
        json.dumps(
            {
                "own_tier": "Opus",
                "candidate_tiers": ["Astra"],
                "attempts": [{"tier": "Astra", "result": "spawned"}],
                "selected_tier": "Astra",
                "host_profile": "Codex",
            }
        ),
        encoding="utf-8",
    )
    assert main([str(log_path)]) == 0
    loaded_run = load_model_tier_run_from_json_path(from_path=log_path)
    assert loaded_run.host_profile == "Codex"
