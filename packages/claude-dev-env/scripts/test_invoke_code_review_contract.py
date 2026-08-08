"""Argument contract, outcome encoding, and effort-token behavior."""

from __future__ import annotations

from pathlib import Path

import pytest

import invoke_code_review as invoker
from _code_review_test_support import (
    EFFORT_LOW,
    FIXTURE_CHAIN_RETURNCODE,
    FIXTURE_FAILED_RETURNCODE,
    FIXTURE_SERVED_COMMAND,
    FIXTURE_SESSION_OPUS,
    HOST_PROFILE_THIRD_PARTY,
    REJECTED_ULTRA_EFFORT,
    claude_failed,
    init_git_repository,
    install_seams,
    run_review,
)
from dev_env_scripts_constants.code_review_constants import (
    CODE_REVIEW_MODEL_ALIAS,
    DEFAULT_CODE_REVIEW_EFFORT,
    IN_SESSION_RETURNCODE,
    MODE_CHAIN,
    MODE_IN_SESSION,
    REVIEW_PERMISSION_MODE as PERMISSION_MODE_BYPASS,
    PERMISSION_MODE_FLAG,
    RESULT_KEY_DIRTY_TREE,
    RESULT_KEY_MODE,
    RESULT_KEY_RETURNCODE,
    RESULT_KEY_SERVED_COMMAND,
)
from dev_env_scripts_constants.grok_worker_constants import (
    MODEL_FLAG,
    OUTPUT_FORMAT_FLAG,
    OUTPUT_FORMAT_JSON,
    SINGLE_TURN_FLAG,
)
from dev_env_scripts_constants.timing import DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS

CLEAN_SUCCESS_OUTCOME = invoker.CodeReviewOutcome(
    mode=MODE_CHAIN,
    served_command=FIXTURE_SERVED_COMMAND,
    returncode=FIXTURE_CHAIN_RETURNCODE,
    is_dirty_tree=False,
)
DIRTY_SUCCESS_OUTCOME = invoker.CodeReviewOutcome(
    mode=MODE_CHAIN,
    served_command=FIXTURE_SERVED_COMMAND,
    returncode=FIXTURE_CHAIN_RETURNCODE,
    is_dirty_tree=True,
)
FAILED_SERVE_OUTCOME = invoker.CodeReviewOutcome(
    mode=MODE_CHAIN,
    served_command=None,
    returncode=FIXTURE_FAILED_RETURNCODE,
    is_dirty_tree=False,
)
IN_SESSION_READY_OUTCOME = invoker.CodeReviewOutcome(
    mode=MODE_IN_SESSION,
    served_command=None,
    returncode=IN_SESSION_RETURNCODE,
    is_dirty_tree=False,
)


def test_build_code_review_arguments_matches_contract() -> None:
    all_arguments = invoker.build_code_review_arguments()
    assert all_arguments == [
        SINGLE_TURN_FLAG,
        invoker.build_code_review_prompt(DEFAULT_CODE_REVIEW_EFFORT),
        MODEL_FLAG,
        CODE_REVIEW_MODEL_ALIAS,
        OUTPUT_FORMAT_FLAG,
        OUTPUT_FORMAT_JSON,
        PERMISSION_MODE_FLAG,
        PERMISSION_MODE_BYPASS,
    ]


def test_chain_failure_preserves_returncode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=claude_failed(),
        working_directory=working_directory,
    )

    review_outcome = run_review(working_directory, session_model=FIXTURE_SESSION_OPUS)

    assert review_outcome.mode == MODE_CHAIN
    assert review_outcome.served_command is None
    assert review_outcome.returncode == FIXTURE_FAILED_RETURNCODE
    assert review_outcome.is_dirty_tree is False
    assert invoker.is_successful_code_review(review_outcome) is False


def test_encode_code_review_outcome_shape() -> None:
    review_outcome = invoker.CodeReviewOutcome(
        mode=MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
        returncode=FIXTURE_CHAIN_RETURNCODE,
        is_dirty_tree=True,
    )
    encoded_payload = invoker.encode_code_review_outcome(review_outcome)
    assert encoded_payload == {
        RESULT_KEY_MODE: MODE_CHAIN,
        RESULT_KEY_SERVED_COMMAND: FIXTURE_SERVED_COMMAND,
        RESULT_KEY_RETURNCODE: FIXTURE_CHAIN_RETURNCODE,
        RESULT_KEY_DIRTY_TREE: True,
    }


@pytest.mark.parametrize("valid_effort", ["low", "medium", "high", "xhigh", "max"])
def test_validate_effort_token_accepts_known_tokens(valid_effort: str) -> None:
    assert invoker.validate_effort_token(valid_effort) is None


def test_validate_effort_token_rejects_ultra_loudly() -> None:
    error_message = invoker.validate_effort_token(REJECTED_ULTRA_EFFORT)
    assert error_message is not None
    assert REJECTED_ULTRA_EFFORT in error_message


def test_validate_effort_token_rejects_unknown_token() -> None:
    error_message = invoker.validate_effort_token("bogus")
    assert error_message is not None
    assert "bogus" in error_message


def test_build_code_review_prompt_reads_as_slash_command() -> None:
    assert invoker.build_code_review_prompt(EFFORT_LOW) == "/code-review low --fix"
    assert invoker.build_code_review_prompt("xhigh") == "/code-review xhigh --fix"
