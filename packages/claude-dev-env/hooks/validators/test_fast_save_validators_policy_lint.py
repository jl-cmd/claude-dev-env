"""Prove the fast-save validator seam can omit native or duplicate checks."""

from pathlib import Path

from .fast_save_validators import run_fast_save_validators

_CLEAN_SOURCE = (
    "def add_two_numbers(first_number: int, second_number: int) -> int:\n"
    "    return first_number + second_number\n"
)
_OVERLAPPING_VALIDATOR_NAMES = frozenset(
    {"Python Style", "Magic Values", "Type Safety", "Test Safety", "React"}
)


def test_fast_save_validators_excludes_requested_outcomes(tmp_path: Path) -> None:
    target_path = tmp_path / "probe.py"
    target_path.write_text(_CLEAN_SOURCE, encoding="utf-8")
    all_results = run_fast_save_validators(
        [target_path], _OVERLAPPING_VALIDATOR_NAMES
    )

    all_result_names = {each_result.name for each_result in all_results}
    assert all_result_names.isdisjoint(_OVERLAPPING_VALIDATOR_NAMES)
    assert "Abbreviations" in all_result_names
