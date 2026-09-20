"""Graded-corpus scope tests for the policy-lint document rules.

A benchmark case and a hook fixture carry their defects on purpose, so the
Python and code rules do not accept them::

    tests/audit/bench/cases/bugfix/fixture/shop/pricing.py -> not accepted
    tests/audit/bench/run_arm.py                           -> accepted
"""

from __future__ import annotations

from policy_lint import adapters
from policy_lint.model import Document

CORPUS_PATH = "tests/audit/bench/cases/bugfix/fixture/shop/pricing.py"
HOOK_FIXTURE_PATH = "tests/audit/hooks/fixtures/hooks/overblocker.py"
HARNESS_PATH = "tests/audit/bench/run_arm.py"
CORPUS_README_PATH = "tests/audit/bench/cases/feature-cli-json-flag/fixture/README.md"
HARNESS_DOCUMENT_PATH = "tests/audit/PROPERTIES.md"
SOURCE = "value = 1\n"


def _document(path: str) -> Document:
    return Document.from_text(path, SOURCE)


def test_python_rules_skip_a_benchmark_case() -> None:
    assert adapters.accepts_python(_document(CORPUS_PATH)) is False


def test_python_rules_skip_a_hook_fixture() -> None:
    assert adapters.accepts_python(_document(HOOK_FIXTURE_PATH)) is False


def test_code_rules_skip_a_benchmark_case() -> None:
    assert adapters.accepts_code(_document(CORPUS_PATH)) is False


def test_python_rules_accept_the_harness_itself() -> None:
    assert adapters.accepts_python(_document(HARNESS_PATH)) is True


def test_markdown_rules_skip_a_benchmark_case() -> None:
    assert adapters.accepts_markdown(_document(CORPUS_README_PATH)) is False


def test_markdown_rules_accept_a_harness_document() -> None:
    assert adapters.accepts_markdown(_document(HARNESS_DOCUMENT_PATH)) is True
