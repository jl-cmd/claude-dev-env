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


def _mixed_newline_overlong_source() -> str:
    all_line_endings = ("\r\n", "\n")
    all_body_lines = "".join(
        "    running_total = running_total + 1"
        + all_line_endings[each_line_index % len(all_line_endings)]
        for each_line_index in range(29)
    )
    return (
        "def calculate_total(running_total: int) -> int:"
        + all_line_endings[0]
        + all_body_lines
        + "    return running_total"
        + all_line_endings[1]
    )


def test_validate_proposed_file_preserves_mixed_newline_diagnostics(
    tmp_path: Path,
) -> None:
    all_results = run_all_validators.validate_proposed_file(
        str(tmp_path / "probe.py"),
        _mixed_newline_overlong_source(),
        include_ruff=False,
    )

    code_quality_result = next(
        each_result
        for each_result in all_results
        if each_result.name == "Code Quality"
    )
    assert code_quality_result.passed is False
    assert "Function 'calculate_total' is 31 lines (max 30)" in (
        code_quality_result.output
    )
