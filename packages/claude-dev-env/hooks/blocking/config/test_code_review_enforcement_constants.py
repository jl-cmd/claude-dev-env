"""Behavioral tests for the code-review enforcement constants and comparator.

These exercise ``effort_meets_threshold`` against the ordered effort tokens and
assert the push and pull-request thresholds carry the push-based names the gate
family reads, so a rename that reintroduces commit terminology fails loudly.
"""

import importlib.util
import pathlib
import re

_CONFIG_DIR = pathlib.Path(__file__).parent

SAMPLE_ROOT_KEY_HEX_LENGTH = 16

_constants_spec = importlib.util.spec_from_file_location(
    "code_review_enforcement_constants",
    _CONFIG_DIR / "code_review_enforcement_constants.py",
)
assert _constants_spec is not None
assert _constants_spec.loader is not None
_constants_module = importlib.util.module_from_spec(_constants_spec)
_constants_spec.loader.exec_module(_constants_module)

effort_meets_threshold = _constants_module.effort_meets_threshold
CODE_REVIEW_ENFORCEMENT_ENABLED = _constants_module.CODE_REVIEW_ENFORCEMENT_ENABLED
PUSH_REQUIRED_EFFORT = _constants_module.PUSH_REQUIRED_EFFORT
PR_CREATE_REQUIRED_EFFORT = _constants_module.PR_CREATE_REQUIRED_EFFORT
GATED_PUSH_SUBCOMMANDS = _constants_module.GATED_PUSH_SUBCOMMANDS
ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER = _constants_module.ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER
PUSH_GATE_CORRECTIVE_MESSAGE = _constants_module.PUSH_GATE_CORRECTIVE_MESSAGE
SANCTIONED_STAMP_MINTER_FLAG = _constants_module.SANCTIONED_STAMP_MINTER_FLAG
STAMP_DIRECTORY_GUARD_MESSAGE = _constants_module.STAMP_DIRECTORY_GUARD_MESSAGE
STAMP_DIRECTORY_NAME = _constants_module.STAMP_DIRECTORY_NAME
GH_PR_CREATE_INVOCATION_PATTERN = _constants_module.GH_PR_CREATE_INVOCATION_PATTERN
STAMP_FILE_REFERENCE_BOUNDARY_PREFIX_PATTERN = (
    _constants_module.STAMP_FILE_REFERENCE_BOUNDARY_PREFIX_PATTERN
)
STAMP_FILE_ROOT_KEY_JSON_SUFFIX_PATTERN = _constants_module.STAMP_FILE_ROOT_KEY_JSON_SUFFIX_PATTERN


def test_gh_pr_create_pattern_matches_create_but_not_edit() -> None:
    invocation_pattern = re.compile(GH_PR_CREATE_INVOCATION_PATTERN, re.IGNORECASE)
    assert invocation_pattern.search("gh pr create --title T --body-file b.md") is not None
    assert invocation_pattern.search("gh pr edit 1 --title T") is None


def test_stamp_file_pattern_fragments_match_a_stamp_file_reference() -> None:
    stamp_file_pattern = re.compile(
        STAMP_FILE_REFERENCE_BOUNDARY_PREFIX_PATTERN
        + re.escape(STAMP_DIRECTORY_NAME)
        + STAMP_FILE_ROOT_KEY_JSON_SUFFIX_PATTERN % SAMPLE_ROOT_KEY_HEX_LENGTH,
        re.IGNORECASE,
    )
    stamp_file_reference = f"cat {STAMP_DIRECTORY_NAME}/{'a' * SAMPLE_ROOT_KEY_HEX_LENGTH}.json"
    assert stamp_file_pattern.search(stamp_file_reference) is not None
    assert stamp_file_pattern.search("cat notes.json") is None


def test_higher_effort_meets_a_lower_threshold() -> None:
    assert effort_meets_threshold("xhigh", "low") is True


def test_lower_effort_fails_a_higher_threshold() -> None:
    assert effort_meets_threshold("low", "xhigh") is False


def test_equal_effort_meets_the_threshold() -> None:
    assert effort_meets_threshold("low", "low") is True


def test_ultra_is_unranked_and_meets_nothing() -> None:
    assert effort_meets_threshold("ultra", "low") is False


def test_unknown_required_effort_meets_nothing() -> None:
    assert effort_meets_threshold("low", "ultra") is False


def test_push_requires_the_lowest_effort_token() -> None:
    every_token_meets_push = all(
        effort_meets_threshold(each_token, PUSH_REQUIRED_EFFORT)
        for each_token in ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER
    )
    assert every_token_meets_push


def test_pr_create_threshold_admits_xhigh_but_rejects_high() -> None:
    assert effort_meets_threshold("xhigh", PR_CREATE_REQUIRED_EFFORT) is True
    assert effort_meets_threshold("high", PR_CREATE_REQUIRED_EFFORT) is False


def test_gated_push_subcommands_gates_push_not_commit() -> None:
    assert "push" in GATED_PUSH_SUBCOMMANDS
    assert "commit" not in GATED_PUSH_SUBCOMMANDS


def test_ultra_absent_from_the_ordered_tokens() -> None:
    assert "ultra" not in ALL_EFFORT_TOKENS_IN_ASCENDING_ORDER


def test_push_gate_message_names_the_push_action_and_low_effort() -> None:
    assert "git push" in PUSH_GATE_CORRECTIVE_MESSAGE
    assert "CODE_REVIEW_PUSH_GATE" in PUSH_GATE_CORRECTIVE_MESSAGE
    assert "'low'" in PUSH_GATE_CORRECTIVE_MESSAGE


def test_guard_message_directs_users_to_the_sanctioned_minter_flag() -> None:
    assert SANCTIONED_STAMP_MINTER_FLAG in STAMP_DIRECTORY_GUARD_MESSAGE


def test_enforcement_defaults_to_off() -> None:
    assert CODE_REVIEW_ENFORCEMENT_ENABLED is False
