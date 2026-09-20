"""Graded-corpus exemption tests for the enforcer.

A benchmark case and a hook fixture are the input side of a measurement: the
defects they carry are what the run grades. A gate that reports them asks the
corpus to stop being the thing it measures::

    tests/audit/bench/cases/bugfix-discount-rounding/fixture/shop/pricing.py -> exempt
    tests/audit/bench/run_arm.py                                             -> governed
"""

from __future__ import annotations


from blocking import _path_setup
from code_rules_enforcer import validate_content_for_full_gate
from blocking.code_rules_shared import is_graded_corpus_path

PATH_SETUP_MODULE = _path_setup
_TEST_SOURCE_WITH_A_BANNED_IDENTIFIER = (
    "def test_thing() -> None:\n    result = 1\n    assert result\n"
)
_BENCHMARK_CASE_PATH = "/repo/tests/audit/bench/cases/bugfix/fixture/tests/test_pricing.py"
_HARNESS_PATH = "/repo/tests/audit/bench/test_run_arm.py"


def test_full_gate_reports_nothing_inside_a_benchmark_case() -> None:
    assert (
        validate_content_for_full_gate(
            _TEST_SOURCE_WITH_A_BANNED_IDENTIFIER,
            _BENCHMARK_CASE_PATH,
            include_comment_policy=True,
        )
        == []
    )


def test_full_gate_still_reports_the_same_source_in_the_harness_itself() -> None:
    assert validate_content_for_full_gate(
        _TEST_SOURCE_WITH_A_BANNED_IDENTIFIER, _HARNESS_PATH, include_comment_policy=True
    ) != []


def test_hook_fixture_path_is_corpus() -> None:
    assert is_graded_corpus_path("/repo/tests/audit/hooks/fixtures/hooks/overblocker.py")
