"""Tests for scoping proposed violations against the on-disk baseline."""

from collections import Counter

from .baseline_diff import _scope_new_and_preexisting
from .validator_result import ValidatorResult


class TestScopeNewAndPreexisting:
    def test_failed_result_without_located_lines_is_treated_as_new(self) -> None:
        summary_only_result = ValidatorResult(
            name="Ruff", checks="37", passed=False, output="Found 1 error."
        )

        new_results, preexisting_results = _scope_new_and_preexisting(
            [summary_only_result], "import os\n", Counter()
        )

        assert [each_result.name for each_result in new_results] == ["Ruff"]
        assert preexisting_results == []
