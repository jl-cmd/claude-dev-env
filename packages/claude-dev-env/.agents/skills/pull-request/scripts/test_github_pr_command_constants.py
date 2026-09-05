"""Tests for explicit GitHub pull request command constants."""

import sys
from pathlib import Path

_SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIRECTORY))

from github_pr_command_constants.config import constants


def test_action_and_linter_mappings_are_complete() -> None:
    assert constants.ALL_LINTER_ACTIONS_BY_COMMAND == {
        constants.ACTION_COMMENT: constants.LINTER_ACTION_COMMENT,
        constants.ACTION_CREATE: constants.LINTER_ACTION_CREATE,
        constants.ACTION_EDIT: constants.LINTER_ACTION_EDIT,
        constants.ACTION_REVIEW: constants.LINTER_ACTION_REVIEW,
    }


def test_review_event_flags_are_complete() -> None:
    assert constants.ALL_REVIEW_FLAGS_BY_EVENT == {
        constants.REVIEW_EVENT_APPROVE: "--approve",
        constants.REVIEW_EVENT_COMMENT: "--comment",
        constants.REVIEW_EVENT_REQUEST_CHANGES: "--request-changes",
    }


def test_account_boundary_constants_are_safe_and_stable() -> None:
    assert constants.SELECTED_ACCOUNT_ENVIRONMENT_KEY == "GITHUB_DEFAULT_ACCOUNT"
    assert constants.ACCOUNT_LOOKUP_FAILURE_EXIT_CODE == 1
    assert constants.ACCOUNT_LOOKUP_FAILED_MESSAGE.endswith("lookup failed\n")
    assert constants.ACCOUNT_LOOKUP_EMPTY_MESSAGE.endswith("returned no value\n")


def test_legacy_recovery_constants_define_one_record_boundary() -> None:
    assert constants.ALL_GH_AUTH_SWITCH_COMMAND_HEAD == (
        "gh",
        "auth",
        "switch",
        "--user",
    )
    assert constants.LEGACY_RECORD_NAME_PATTERN.fullmatch(
        "gh_pr_author_swap_session-a.json"
    )
    assert not constants.LEGACY_RECORD_NAME_PATTERN.fullmatch("other.json")
    assert constants.LEGACY_RECORD_STALE_AGE_SECONDS == 1800
    assert constants.RECOVERY_UNRESOLVED_EXIT_CODE == 3
