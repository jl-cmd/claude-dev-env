"""Mechanically validate a model-tier spawn-walk log.

The advisor protocol's Model floor section emits a structured spawn-walk log.
This validator reads that log back and checks its invariants. A run is judged
from data, not inferred from a transcript.

::

    ladder_walk = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "spawned"}],
        selected_tier="Fable",
    )
    validate_model_tier_run(ladder_walk)  # ok: returns None, raises nothing

    cli_bind = ModelTierRun(
        own_tier="Opus",
        candidate_tiers=["Fable"],
        attempts=[{"tier": "Fable", "result": "cli"}],
        selected_tier="Fable",
    )
    validate_model_tier_run(cli_bind)  # ok: third-party-host CLI Claude-chain bind

A run whose selected_tier is not the first successful bind fails.
On any broken invariant, validate_model_tier_run raises ModelTierRunError.

CLI::

    python model_tier_run_validator.py path/to/spawn-walk-log.json
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

_scripts_directory = str(Path(__file__).resolve().parent)
_config_directory = str(Path(__file__).resolve().parent / "config")
if _config_directory not in sys.path:
    sys.path.insert(0, _config_directory)
if _scripts_directory not in sys.path:
    sys.path.insert(0, _scripts_directory)

from advisor_scripts_constants.model_tier_run_validator_constants import (  # noqa: E402
    ATTEMPT_ORDER_MISMATCH_MESSAGE,
    ATTEMPT_TIER_OUT_OF_SLICE_MESSAGE,
    CANDIDATE_TIERS_MISMATCH_MESSAGE,
    CLI_INVALID_JSON_EXIT_CODE,
    CLI_MISSING_PATH_EXIT_CODE,
    CLI_SUCCESS_EXIT_CODE,
    CLI_USAGE_MESSAGE,
    CLI_VALIDATION_FAILURE_EXIT_CODE,
    INCOMPLETE_FALLBACK_WALK_MESSAGE,
    MISSING_FALLBACK_REASON_MESSAGE,
    SELECTED_TIER_MISMATCH_MESSAGE,
    SELECTED_TIER_NOT_NULL_MESSAGE,
    THIRD_PARTY_MODEL_TIER,
    UNKNOWN_OWN_TIER_MESSAGE,
)
from advisor_scripts_constants.advisor_route_constants import (  # noqa: E402
    ADVISOR_FALLBACK_TIER,
    ADVISOR_MODEL_TIER,
    CODEX_BIND_SUCCESS_TOKEN,
    CLI_BIND_SUCCESS_TOKEN,
    SPAWN_OUTCOME_KEY,
    SPAWN_SUCCESS_TOKEN,
    TIER_KEY,
)
from tier_model_ids import canonical_tier_name  # noqa: E402


@dataclass(frozen=True)
class ModelTierRun:
    own_tier: str
    candidate_tiers: list[str]
    attempts: list[dict[str, str]]
    selected_tier: str | None
    fallback_reason: str | None = None
    is_sol_enabled: bool = False


class ModelTierRunError(ValueError):
    """Raised when a model-tier spawn-walk log violates an invariant."""


def _canonical_tier_list(all_tier_names: list[str]) -> list[str] | None:
    all_canonical_tiers: list[str] = []
    for each_tier_name in all_tier_names:
        maybe_canonical_tier = canonical_tier_name(each_tier_name)
        if maybe_canonical_tier is None:
            return None
        all_canonical_tiers.append(maybe_canonical_tier)
    return all_canonical_tiers


def _expected_candidate_tiers(
    own_tier: str, is_sol_enabled: bool = False
) -> list[str]:
    maybe_canonical_own_tier = canonical_tier_name(own_tier)
    if maybe_canonical_own_tier is None:
        raise ModelTierRunError(f"{UNKNOWN_OWN_TIER_MESSAGE}: {own_tier!r}")
    if maybe_canonical_own_tier == ADVISOR_MODEL_TIER:
        raise ModelTierRunError(f"{UNKNOWN_OWN_TIER_MESSAGE}: {own_tier!r}")
    all_expected_candidates = [ADVISOR_FALLBACK_TIER]
    if is_sol_enabled:
        all_expected_candidates.append(ADVISOR_MODEL_TIER)
    return all_expected_candidates


def _is_successful_attempt_outcome(
    canonical_tier: str,
    outcome_token: str,
) -> bool:
    if canonical_tier == THIRD_PARTY_MODEL_TIER:
        return False
    if canonical_tier == ADVISOR_MODEL_TIER:
        return outcome_token == CODEX_BIND_SUCCESS_TOKEN
    if outcome_token == CODEX_BIND_SUCCESS_TOKEN:
        return False
    if outcome_token == SPAWN_SUCCESS_TOKEN:
        return True
    if outcome_token == CLI_BIND_SUCCESS_TOKEN:
        return True
    return False


def validate_model_tier_run(run: ModelTierRun) -> None:
    """Check that a spawn-walk log satisfies every ladder invariant.

    ::

        validate_model_tier_run(ladder_walk)  # ok: multi-tier Agent walk
        validate_model_tier_run(cli_bind)     # ok: CLI Claude-chain bind
        validate_model_tier_run(broken_log)   # flag: ModelTierRunError

    Candidate tiers are Fable, plus Sol when ``is_sol_enabled`` is true.
    Consumer ``own_tier`` is recorded and must be a known tier; it does not
    add Opus to the advisor walk. Tries walk that list in order. Early stop
    only after ``spawned``, ``cli``, or Sol ``codex``. A null selected_tier
    requires a full walk plus fallback_reason.

    Args:
        run: The structured spawn-walk log to check.

    Returns:
        None when every invariant holds.

    Raises:
        ModelTierRunError: When any invariant is violated.
    """
    all_expected_candidates = _expected_candidate_tiers(
        run.own_tier,
        is_sol_enabled=run.is_sol_enabled,
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
    raw_sol_enabled = parsed_payload.get("sol_enabled", False)
    if not isinstance(raw_sol_enabled, bool):
        raise TypeError("sol_enabled must be a boolean")
    return ModelTierRun(
        own_tier=parsed_payload["own_tier"],
        candidate_tiers=list(parsed_payload["candidate_tiers"]),
        attempts=list(parsed_payload["attempts"]),
        selected_tier=parsed_payload.get("selected_tier"),
        fallback_reason=parsed_payload.get("fallback_reason"),
        is_sol_enabled=raw_sol_enabled,
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
