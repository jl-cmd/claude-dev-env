"""Synchronization tests for the per-check identifier catalog.

Each sample below is a message copied from the check that raises it. A check
whose wording moves fails its sample here, so the catalog and the checks stay
in step.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from policy_lint.check_catalog import check_id_for_message
from policy_lint.config.check_catalog_constants import (
    ALL_CHECK_CATALOG_ENTRIES,
    UNCLASSIFIED_CHECK_NAME,
)
from policy_lint.model import Diagnostic, Severity

_BUNDLING_RULE_ID = "code-rules"
_HOOKS_DIRECTORY = Path(__file__).resolve().parents[2] / "hooks"
_TEST_FILE_PREFIX = "test_"
_PYTHON_GLOB = "*.py"
_SOURCE_ENCODING = "utf-8"

ALL_MESSAGE_SAMPLES: tuple[tuple[str, str], ...] = (
    (
        "Line 20: Function 'run' is 74 lines - exceeds blocking threshold - "
        "split into helpers",
        "function-length",
    ),
    (
        "Line 8: Function-local constant TIMEOUT - consider moving to config/",
        "function-local-constant",
    ),
    ("Line 3: Constant TIMEOUT - move to config/", "constant-outside-config"),
    (
        "Line 5: Collection parameter paths - prefix with all_ (CODE_RULES §5)",
        "collection-name-prefix",
    ),
    (
        "Line 6: loop variable 'path' - prefix with each_ (CODE_RULES §5)",
        "loop-variable-prefix",
    ),
    (
        "Line 7: Stuttering collection prefix 'all_all_paths'",
        "stuttering-collection-prefix",
    ),
    ("Line 9: string separator '\\n' - name it", "unnamed-string-separator"),
    ("Line 10: string magic value 'utf-8'", "string-magic-value"),
    (
        "Line 11: Block comment found - refactor to self-documenting code",
        "block-comment-added",
    ),
    (
        "Line 12: Comment found - refactor to self-documenting code",
        "comment-added",
    ),
    ("Line 13: TODO comment added: fix later", "comment-diff"),
    (
        "Line 14: module docstring carries a 44-word run-on sentence",
        "docstring-runon-sentence",
    ),
    ("Line 15: module summary runs 9 prose lines", "docstring-prose-wall"),
    (
        "Line 16: parameter 'count' on 'run' missing type annotation (CODE_RULES §6)",
        "missing-type-annotation",
    ),
    (
        "Line 17: function 'run' missing return type annotation (CODE_RULES §6)",
        "missing-return-annotation",
    ),
    ("src/app.py:3: Single-letter variable 'p'", "single-letter-variable"),
)


def _all_hook_source_texts() -> tuple[str, ...]:
    return tuple(
        each_path.read_text(encoding=_SOURCE_ENCODING)
        for each_path in _HOOKS_DIRECTORY.rglob(_PYTHON_GLOB)
        if not each_path.name.startswith(_TEST_FILE_PREFIX)
    )


@pytest.mark.parametrize(("sample_message", "expected_name"), ALL_MESSAGE_SAMPLES)
def test_a_message_sample_resolves_to_its_check_name(
    sample_message: str, expected_name: str
) -> None:
    resolved_check_id = check_id_for_message(_BUNDLING_RULE_ID, sample_message)

    assert resolved_check_id == f"{_BUNDLING_RULE_ID}/{expected_name}"


def test_every_catalog_entry_carries_a_message_sample() -> None:
    all_sampled_names = {each_sample[1] for each_sample in ALL_MESSAGE_SAMPLES}
    all_catalog_names = {
        each_entry.check_name for each_entry in ALL_CHECK_CATALOG_ENTRIES
    }

    assert all_catalog_names == all_sampled_names


@pytest.mark.parametrize("catalog_entry", ALL_CHECK_CATALOG_ENTRIES)
def test_each_catalog_marker_is_still_written_by_a_check(catalog_entry) -> None:
    all_source_texts = _all_hook_source_texts()

    assert any(
        catalog_entry.message_marker in each_text for each_text in all_source_texts
    )


def test_every_catalog_check_name_is_distinct_from_its_neighbours() -> None:
    all_names = [each_entry.check_name for each_entry in ALL_CHECK_CATALOG_ENTRIES]

    assert len(set(all_names)) == len(all_names)


def test_an_unmatched_message_stays_unclassified() -> None:
    resolved_check_id = check_id_for_message(
        _BUNDLING_RULE_ID, "Line 4: a finding no catalog entry names"
    )

    assert resolved_check_id == f"{_BUNDLING_RULE_ID}/{UNCLASSIFIED_CHECK_NAME}"


def test_a_rule_outside_the_bundling_set_keeps_its_own_identifier() -> None:
    resolved_check_id = check_id_for_message(
        "rmtree-safety", "Line 9: shutil.rmtree with ignore_errors=True"
    )

    assert resolved_check_id == "rmtree-safety"


def test_a_diagnostic_reports_its_rule_identifier_when_it_carries_no_check_name() -> (
    None
):
    diagnostic = Diagnostic("test-pairing", Severity.ERROR, "no matching test")

    assert diagnostic.as_dict()["check_id"] == "test-pairing"


def test_a_diagnostic_reports_the_check_identifier_it_carries() -> None:
    diagnostic = Diagnostic(
        "code-rules",
        Severity.ERROR,
        "Line 3: Constant TIMEOUT - move to config/",
        None,
        "code-rules/constant-outside-config",
    )

    assert diagnostic.as_dict()["check_id"] == "code-rules/constant-outside-config"
