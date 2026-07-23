"""Behavioral tests for the staged_test_running parts module."""

from pathlib import Path

from code_rules_gate_parts import staged_test_running


def test_batched_pytest_arguments_splits_over_the_budget() -> None:
    all_batches = staged_test_running._batched_pytest_arguments(["aaaa", "bbbb", "cccc"], 10)
    assert all_batches == [["aaaa", "bbbb"], ["cccc"]]


def test_batched_pytest_arguments_keeps_oversized_argument_in_its_own_batch() -> None:
    all_batches = staged_test_running._batched_pytest_arguments(["wide_argument"], 4)
    assert all_batches == [["wide_argument"]]


def test_pytest_target_paths_drops_conftest_and_keeps_real_tests() -> None:
    all_staged_paths = [
        Path("pkg_a/conftest.py"),
        Path("pkg_b/conftest.py"),
        Path("pkg_a/test_alpha.py"),
        Path("pkg_b/tests/conftest.py"),
    ]

    all_targets = staged_test_running._pytest_target_paths(all_staged_paths)

    assert all_targets == [Path("pkg_a/test_alpha.py")]
