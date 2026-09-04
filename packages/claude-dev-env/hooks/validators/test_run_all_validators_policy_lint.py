"""Prove the policy-linter validator seam keeps native tools separate."""

from pathlib import Path

import pytest

from . import run_all_validators

_CLEAN_SOURCE = (
    "def add_two_numbers(first_number: int, second_number: int) -> int:\n"
    "    return first_number + second_number\n"
)
_OVERLAPPING_VALIDATOR_NAMES = frozenset(
    {"Python Style", "Magic Values", "Type Safety", "Test Safety", "React"}
)


def _result_names(all_results: list[run_all_validators.ValidatorResult]) -> set[str]:
    return {each_result.name for each_result in all_results}


def test_policy_lint_can_run_only_unique_in_process_validators(tmp_path: Path) -> None:
    all_results = run_all_validators.validate_proposed_file(
        str(tmp_path / "probe.py"),
        _CLEAN_SOURCE,
        include_ruff=False,
        excluded_validator_names=_OVERLAPPING_VALIDATOR_NAMES,
    )

    all_result_names = _result_names(all_results)
    assert all_result_names.isdisjoint(_OVERLAPPING_VALIDATOR_NAMES)
    assert "Ruff" not in all_result_names
    assert "Abbreviations" in all_result_names


def test_validate_proposed_file_keeps_ruff_as_an_explicit_native_step(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        run_all_validators,
        "run_ruff_checks",
        lambda _files, _config_source_path: run_all_validators.ValidatorResult(
            "Ruff", "37", True, "clean"
        ),
    )
    all_results = run_all_validators.validate_proposed_file(
        str(tmp_path / "probe.py"),
        _CLEAN_SOURCE,
        excluded_validator_names=_OVERLAPPING_VALIDATOR_NAMES,
    )

    assert "Ruff" in _result_names(all_results)
