"""Mechanically validate a model-tier spawn-walk log.

The advisor protocol's Model floor section emits a structured spawn-walk log.
This validator reads that log back and checks its invariants.

::

    ladder_walk = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Opus"],
        attempts=[{"tier": "Opus", "result": "spawned"}],
        selected_tier="Opus",
    )
    validate_model_tier_run(ladder_walk)  # ok: returns None, raises nothing

    cli_bind = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Opus"],
        attempts=[{"tier": "Opus", "result": "cli"}],
        selected_tier="Opus",
    )
    validate_model_tier_run(cli_bind)  # ok: third-party-host CLI Claude-chain bind

    codex_bind = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Astra"],
        attempts=[{"tier": "Astra", "result": "spawned"}],
        selected_tier="Astra",
        host_profile="Codex",
    )
    validate_model_tier_run(codex_bind)  # ok: Codex in-session Astra spawn

A run whose selected_tier is not the first successful bind fails.
On any broken invariant, validate_model_tier_run raises ModelTierRunError.

CLI::

    python model_tier_run_validator.py path/to/spawn-walk-log.json
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

_scripts_directory = str(Path(__file__).resolve().parent)
_config_directory = str(Path(__file__).resolve().parent / "config")
if _config_directory not in sys.path:
    sys.path.insert(0, _config_directory)
if _scripts_directory not in sys.path:
    sys.path.insert(0, _scripts_directory)

from advisor_scripts_constants.advisor_route_constants import (
    ADVISOR_FALLBACK_TIER,
    ADVISOR_MODEL_TIER,
    CLI_BIND_SUCCESS_TOKEN,
    CODEX_BIND_SUCCESS_TOKEN,
    SPAWN_OUTCOME_KEY,
    SPAWN_SUCCESS_TOKEN,
    TIER_KEY,
)
from advisor_scripts_constants.astra_advisor_constants import (
    ASTRA_FALLBACK_KIND_BROKEN,
    ASTRA_FALLBACK_KIND_DECLINED,
)
from advisor_scripts_constants.model_tier_run_validator_constants import (
    ADVISOR_FLAG_OMITTED,
    ALL_ADVISOR_FLAG_STATES,
    ALL_ADVISOR_REPLY_PATHS,
    ATTEMPT_ORDER_MISMATCH_MESSAGE,
    ATTEMPT_TIER_OUT_OF_SLICE_MESSAGE,
    CANDIDATE_TIERS_MISMATCH_MESSAGE,
    CLI_INVALID_JSON_EXIT_CODE,
    CLI_MISSING_PATH_EXIT_CODE,
    CLI_SUCCESS_EXIT_CODE,
    CLI_USAGE_MESSAGE,
    CLI_VALIDATION_FAILURE_EXIT_CODE,
    EVIDENCE_MUST_BE_OBJECT_MESSAGE,
    HOST_PROFILE_CLAUDE,
    HOST_PROFILE_CODEX,
    HOST_PROFILE_JSON_KEY,
    HOST_PROFILE_MUST_BE_STRING_MESSAGE,
    INCOMPLETE_FALLBACK_WALK_MESSAGE,
    MISSING_ADVISOR_FLAG_MESSAGE,
    MISSING_FALLBACK_REASON_MESSAGE,
    OMITTED_ADVISOR_FLAG_MESSAGE,
    SELECTED_TIER_MISMATCH_MESSAGE,
    SELECTED_TIER_NOT_NULL_MESSAGE,
    THIRD_PARTY_MODEL_TIER,
    UNKNOWN_ADVISOR_FLAG_MESSAGE,
    UNKNOWN_HOST_PROFILE_ERROR,
    UNKNOWN_OWN_TIER_MESSAGE,
)
from tier_model_ids import canonical_host_profile, canonical_tier_name


@dataclass(frozen=True)
class ModelTierRun:
    own_tier: str
    candidate_tiers: list[str]
    attempts: list[dict[str, str]]
    selected_tier: str | None
    fallback_reason: str | None = None
    is_astra_enabled: bool = False
    host_profile: str = HOST_PROFILE_CLAUDE
    evidence: dict[str, object] | None = None


class ModelTierRunError(ValueError):
    """Raised when a model-tier spawn-walk log violates an invariant."""


def _required_evidence_text(
    fields_by_name: Mapping[str, object], section_name: str, field_name: str
) -> str:
    raw_field_text = fields_by_name.get(field_name)
    if not isinstance(raw_field_text, str) or not raw_field_text.strip():
        raise ModelTierRunError(
            f"evidence.{section_name}.{field_name} must be a non-empty string"
        )
    return raw_field_text.strip()


def _required_evidence_list(
    fields_by_name: Mapping[str, object], section_name: str, field_name: str
) -> list[str]:
    raw_field_entries = fields_by_name.get(field_name)
    if not isinstance(raw_field_entries, list) or not raw_field_entries:
        raise ModelTierRunError(
            f"evidence.{section_name}.{field_name} must be a non-empty list"
        )
    if any(
        not isinstance(each_entry, str) or not each_entry.strip()
        for each_entry in raw_field_entries
    ):
        raise ModelTierRunError(
            f"evidence.{section_name}.{field_name} must contain non-empty strings"
        )
    return [each_entry.strip() for each_entry in raw_field_entries]


def _required_evidence_section(
    sections_by_name: Mapping[str, object], section_name: str
) -> Mapping[str, object]:
    raw_section = sections_by_name.get(section_name)
    if not isinstance(raw_section, Mapping):
        raise ModelTierRunError(f"evidence.{section_name} must be an object")
    return raw_section


def _validate_reference_evidence(sections_by_name: Mapping[str, object]) -> None:
    reference = _required_evidence_section(sections_by_name, "reference")
    _required_evidence_text(reference, "reference", "path")
    reference_status = _required_evidence_text(reference, "reference", "status")
    if reference_status not in {"missing", "read"}:
        raise ModelTierRunError("evidence.reference.status must be missing or read")
    _required_evidence_text(reference, "reference", "repair_action")
    _required_evidence_text(reference, "reference", "repair_result")


def _validate_fallback_tier(
    fallback_by_name: Mapping[str, object], run: ModelTierRun
) -> str | None:
    raw_selected_tier = fallback_by_name.get("selected_tier")
    if raw_selected_tier is not None and not isinstance(raw_selected_tier, str):
        raise ModelTierRunError("evidence.fallback.selected_tier must be a string or null")
    maybe_selected_tier = (
        canonical_tier_name(raw_selected_tier)
        if isinstance(raw_selected_tier, str)
        else None
    )
    maybe_run_selected_tier = (
        canonical_tier_name(run.selected_tier)
        if run.selected_tier is not None
        else None
    )
    if maybe_selected_tier != maybe_run_selected_tier:
        raise ModelTierRunError(
            "evidence.fallback.selected_tier must match selected_tier"
        )
    return maybe_run_selected_tier


def _validate_fallback_kind(fallback_by_name: Mapping[str, object]) -> None:
    raw_fallback_kind = fallback_by_name.get("fallback_kind")
    if raw_fallback_kind not in {
        None,
        ASTRA_FALLBACK_KIND_BROKEN,
        ASTRA_FALLBACK_KIND_DECLINED,
    }:
        raise ModelTierRunError(
            "evidence.fallback.fallback_kind must be declined, broken, or null"
        )
    raw_fallback_reason = fallback_by_name.get("fallback_reason")
    if raw_fallback_reason is not None and (
        not isinstance(raw_fallback_reason, str) or not raw_fallback_reason.strip()
    ):
        raise ModelTierRunError(
            "evidence.fallback.fallback_reason must be a non-empty string or null"
        )
    if raw_fallback_kind is not None and raw_fallback_reason is None:
        raise ModelTierRunError(
            "evidence.fallback.fallback_reason is required for a fallback kind"
        )


def _validate_fallback_reply_path(
    fallback_by_name: Mapping[str, object],
    run: ModelTierRun,
    maybe_run_selected_tier: str | None,
) -> None:
    reply_path = _required_evidence_text(fallback_by_name, "fallback", "reply_path")
    if reply_path not in ALL_ADVISOR_REPLY_PATHS:
        raise ModelTierRunError(
            "evidence.fallback.reply_path is not a known advisor path"
        )
    is_codex_astra_success = (
        canonical_host_profile(run.host_profile) == HOST_PROFILE_CODEX
        and maybe_run_selected_tier == ADVISOR_MODEL_TIER
    )
    if is_codex_astra_success and reply_path != "native":
        raise ModelTierRunError(
            "Codex Astra success requires the native reply path"
        )
    raw_advisor_flag = fallback_by_name.get("advisor_flag")
    if raw_advisor_flag is None:
        if is_codex_astra_success:
            raise ModelTierRunError(MISSING_ADVISOR_FLAG_MESSAGE)
        return
    if (
        not isinstance(raw_advisor_flag, str)
        or raw_advisor_flag not in ALL_ADVISOR_FLAG_STATES
    ):
        raise ModelTierRunError(UNKNOWN_ADVISOR_FLAG_MESSAGE)
    if is_codex_astra_success and raw_advisor_flag == ADVISOR_FLAG_OMITTED:
        raise ModelTierRunError(OMITTED_ADVISOR_FLAG_MESSAGE)


def _validate_fallback_evidence(
    sections_by_name: Mapping[str, object], run: ModelTierRun
) -> None:
    fallback = _required_evidence_section(sections_by_name, "fallback")
    maybe_run_selected_tier = _validate_fallback_tier(fallback, run)
    _validate_fallback_kind(fallback)
    _validate_fallback_reply_path(fallback, run, maybe_run_selected_tier)


def _validate_consult_evidence(sections_by_name: Mapping[str, object]) -> None:
    consult = _required_evidence_section(sections_by_name, "consult")
    for each_field_name in ("changed_evidence", "validation", "unresolved_risks"):
        _required_evidence_list(consult, "consult", each_field_name)
    _required_evidence_text(consult, "consult", "report_back_status")


def _validate_advisor_evidence(
    evidence: object,
    run: ModelTierRun,
) -> None:
    if not isinstance(evidence, Mapping):
        raise ModelTierRunError(EVIDENCE_MUST_BE_OBJECT_MESSAGE)
    raw_schema_version = evidence.get("schema_version")
    if isinstance(raw_schema_version, bool) or raw_schema_version != 1:
        raise ModelTierRunError("evidence.schema_version must be 1")
    _validate_reference_evidence(evidence)
    _validate_fallback_evidence(evidence, run)
    _validate_consult_evidence(evidence)


def _canonical_tier_list(all_tier_names: list[str]) -> list[str] | None:
    all_canonical_tiers: list[str] = []
    for each_tier_name in all_tier_names:
        maybe_canonical_tier = canonical_tier_name(each_tier_name)
        if maybe_canonical_tier is None:
            return None
        all_canonical_tiers.append(maybe_canonical_tier)
    return all_canonical_tiers


def _expected_candidate_tiers(
    own_tier: str,
    is_astra_enabled: bool = False,
    host_profile: str = HOST_PROFILE_CLAUDE,
) -> list[str]:
    maybe_canonical_own_tier = canonical_tier_name(own_tier)
    if maybe_canonical_own_tier is None:
        raise ModelTierRunError(f"{UNKNOWN_OWN_TIER_MESSAGE}: {own_tier!r}")
    if maybe_canonical_own_tier == ADVISOR_MODEL_TIER:
        raise ModelTierRunError(f"{UNKNOWN_OWN_TIER_MESSAGE}: {own_tier!r}")
    maybe_canonical_host = canonical_host_profile(host_profile)
    if maybe_canonical_host is None:
        raise ModelTierRunError(UNKNOWN_HOST_PROFILE_ERROR.format(host_profile))
    if maybe_canonical_host == HOST_PROFILE_CODEX:
        return [ADVISOR_MODEL_TIER]
    all_expected_candidates = [ADVISOR_FALLBACK_TIER]
    if is_astra_enabled:
        all_expected_candidates.append(ADVISOR_MODEL_TIER)
    return all_expected_candidates


def _is_successful_attempt_outcome(
    canonical_tier: str,
    outcome_token: str,
    host_profile: str = HOST_PROFILE_CLAUDE,
) -> bool:
    maybe_canonical_host = canonical_host_profile(host_profile)
    if canonical_tier == THIRD_PARTY_MODEL_TIER:
        return False
    if canonical_tier == ADVISOR_MODEL_TIER:
        if maybe_canonical_host == HOST_PROFILE_CODEX:
            if outcome_token == SPAWN_SUCCESS_TOKEN:
                return True
            return outcome_token == CODEX_BIND_SUCCESS_TOKEN
        return outcome_token == CODEX_BIND_SUCCESS_TOKEN
    if outcome_token == CODEX_BIND_SUCCESS_TOKEN:
        return False
    if outcome_token == SPAWN_SUCCESS_TOKEN:
        return True
    return outcome_token == CLI_BIND_SUCCESS_TOKEN


def validate_model_tier_run(run: ModelTierRun) -> None:
    """Check that a spawn-walk log satisfies every ladder invariant.

    ::

        validate_model_tier_run(ladder_walk)  # ok: multi-tier Agent walk
        validate_model_tier_run(cli_bind)     # ok: CLI Claude-chain bind
        validate_model_tier_run(broken_log)   # flag: ModelTierRunError

    Candidate tiers are Opus, plus Astra when ``is_astra_enabled`` is true, on
    Claude and ThirdParty hosts. A Codex host walks Astra only. Consumer
    ``own_tier`` is recorded and must be a known tier. Tries walk that list in order. Early stop only
    after ``spawned``, ``cli``, or Astra ``codex`` (and Astra ``spawned`` on a
    Codex host). A null selected_tier requires a full walk plus
    fallback_reason.

    Args:
        run: The structured spawn-walk log to check.

    Returns:
        None when every invariant holds.

    Raises:
        ModelTierRunError: When any invariant is violated.
    """
    all_expected_candidates = _expected_candidate_tiers(
        run.own_tier,
        is_astra_enabled=run.is_astra_enabled,
        host_profile=run.host_profile,
    )
    maybe_canonical_candidates = _canonical_tier_list(run.candidate_tiers)
    if maybe_canonical_candidates != all_expected_candidates:
        raise ModelTierRunError(CANDIDATE_TIERS_MISMATCH_MESSAGE)
    maybe_attempted_tiers = _canonical_tier_list(
        [each_attempt[TIER_KEY] for each_attempt in run.attempts]
    )
    if maybe_attempted_tiers is None:
        raise ModelTierRunError(ATTEMPT_TIER_OUT_OF_SLICE_MESSAGE)
    all_attempted_tiers = maybe_attempted_tiers
    if any(
        each_tier not in all_expected_candidates for each_tier in all_attempted_tiers
    ):
        raise ModelTierRunError(ATTEMPT_TIER_OUT_OF_SLICE_MESSAGE)
    if all_attempted_tiers != all_expected_candidates[: len(all_attempted_tiers)]:
        raise ModelTierRunError(ATTEMPT_ORDER_MISMATCH_MESSAGE)
    _validate_selected_tier(
        run=run,
        all_attempted_tiers=all_attempted_tiers,
        all_expected_candidates=all_expected_candidates,
    )
    if run.evidence is not None:
        _validate_advisor_evidence(run.evidence, run)


def _validate_selected_tier(
    run: ModelTierRun,
    all_attempted_tiers: list[str],
    all_expected_candidates: list[str],
) -> None:
    all_bound_tiers = [
        each_tier
        for each_tier, each_attempt in zip(
            all_attempted_tiers, run.attempts, strict=True
        )
        if _is_successful_attempt_outcome(
            canonical_tier=each_tier,
            outcome_token=each_attempt[SPAWN_OUTCOME_KEY],
            host_profile=run.host_profile,
        )
    ]
    if all_bound_tiers:
        maybe_canonical_selected = (
            canonical_tier_name(run.selected_tier)
            if run.selected_tier is not None
            else None
        )
        if maybe_canonical_selected != all_bound_tiers[0]:
            raise ModelTierRunError(SELECTED_TIER_MISMATCH_MESSAGE)
        return
    if run.selected_tier is not None:
        raise ModelTierRunError(SELECTED_TIER_NOT_NULL_MESSAGE)
    if not all_attempted_tiers or all_attempted_tiers != all_expected_candidates:
        raise ModelTierRunError(INCOMPLETE_FALLBACK_WALK_MESSAGE)
    if not run.fallback_reason:
        raise ModelTierRunError(MISSING_FALLBACK_REASON_MESSAGE)


def load_model_tier_run_from_json_path(from_path: Path) -> ModelTierRun:
    """Load a ModelTierRun from a JSON spawn-walk log file.

    Args:
        from_path: Path to a JSON object with ModelTierRun fields.

    Returns:
        The parsed ModelTierRun.

    Raises:
        OSError: When the file cannot be read.
        json.JSONDecodeError: When the file is not valid JSON.
        KeyError: When a required field is missing.
        TypeError: When a field has the wrong shape.
    """
    parsed_payload = json.loads(from_path.read_text(encoding="utf-8"))
    raw_astra_enabled = parsed_payload.get("astra_enabled", False)
    if not isinstance(raw_astra_enabled, bool):
        raise TypeError("astra_enabled must be a boolean")
    raw_host_profile = parsed_payload.get(HOST_PROFILE_JSON_KEY, HOST_PROFILE_CLAUDE)
    if not isinstance(raw_host_profile, str):
        raise TypeError(HOST_PROFILE_MUST_BE_STRING_MESSAGE)
    raw_evidence = parsed_payload.get("evidence")
    if raw_evidence is not None and not isinstance(raw_evidence, dict):
        raise TypeError(EVIDENCE_MUST_BE_OBJECT_MESSAGE)
    return ModelTierRun(
        own_tier=parsed_payload["own_tier"],
        candidate_tiers=list(parsed_payload["candidate_tiers"]),
        attempts=list(parsed_payload["attempts"]),
        selected_tier=parsed_payload.get("selected_tier"),
        fallback_reason=parsed_payload.get("fallback_reason"),
        is_astra_enabled=raw_astra_enabled,
        host_profile=raw_host_profile,
        evidence=raw_evidence,
    )


def main(all_cli_arguments: list[str]) -> int:
    """Validate a spawn-walk log JSON file from the command line.

    Args:
        all_cli_arguments: Argument list without the program name.

    Returns:
        ``0`` when the log is valid, ``1`` when an invariant fails, ``2`` when
        the path or JSON was unusable.
    """
    if len(all_cli_arguments) != 1:
        print(CLI_USAGE_MESSAGE, file=sys.stderr)
        return CLI_MISSING_PATH_EXIT_CODE
    log_path = Path(all_cli_arguments[0])
    try:
        model_tier_run = load_model_tier_run_from_json_path(from_path=log_path)
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as load_error:
        print(str(load_error), file=sys.stderr)
        return CLI_INVALID_JSON_EXIT_CODE
    try:
        validate_model_tier_run(model_tier_run)
    except ModelTierRunError as validation_error:
        print(str(validation_error), file=sys.stderr)
        return CLI_VALIDATION_FAILURE_EXIT_CODE
    return CLI_SUCCESS_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
