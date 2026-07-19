"""Argument contract, encoding, clean-stamp rules, effort tokens, and stamps."""

from __future__ import annotations

from pathlib import Path

import pytest

import invoke_code_review as invoker
from _code_review_test_support import (
    DriftingReview,
    EFFORT_LOW,
    FIXTURE_CHAIN_RETURNCODE,
    FIXTURE_FAILED_RETURNCODE,
    FIXTURE_SERVED_COMMAND,
    FIXTURE_SESSION_OPUS,
    HOST_PROFILE_THIRD_PARTY,
    MISSING_STORE_FILE_NAME,
    REJECTED_ULTRA_EFFORT,
    SINGLE_PASS_CAP,
    claude_failed,
    init_git_repository,
    install_seams,
    prepared_surface_repo,
    run_review,
    stable_clean_review,
    surface_changing_review,
)
from dev_env_scripts_constants.code_review_constants import (
    CODE_REVIEW_MODEL_ALIAS,
    DEFAULT_CODE_REVIEW_EFFORT,
    IN_SESSION_RETURNCODE,
    MAXIMUM_STAMP_MINT_PASSES,
    MODE_CHAIN,
    MODE_IN_SESSION,
    PERMISSION_MODE_BYPASS,
    PERMISSION_MODE_FLAG,
    RESULT_KEY_BOUND_HASH,
    RESULT_KEY_DIRTY_TREE,
    RESULT_KEY_MODE,
    RESULT_KEY_PASS_COUNT,
    RESULT_KEY_RETURNCODE,
    RESULT_KEY_SERVED_COMMAND,
    RESULT_KEY_STAMP_MINTED,
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
    assert invoker.is_code_review_clean_stamp_allowed(review_outcome) is False


def test_clean_stamp_allowed_only_on_successful_clean_serve() -> None:
    assert invoker.is_code_review_clean_stamp_allowed(CLEAN_SUCCESS_OUTCOME) is True
    assert invoker.is_code_review_clean_stamp_allowed(DIRTY_SUCCESS_OUTCOME) is False
    assert invoker.is_code_review_clean_stamp_allowed(FAILED_SERVE_OUTCOME) is False
    assert invoker.is_code_review_clean_stamp_allowed(IN_SESSION_READY_OUTCOME) is True
    assert invoker.is_successful_code_review(FAILED_SERVE_OUTCOME) is False
    assert invoker.is_successful_code_review(CLEAN_SUCCESS_OUTCOME) is True


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


def test_encode_stamp_mint_outcome_includes_mint_metadata() -> None:
    review_outcome = invoker.CodeReviewOutcome(
        mode=MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
        returncode=FIXTURE_CHAIN_RETURNCODE,
        is_dirty_tree=False,
    )
    mint_outcome = invoker.StampMintOutcome(
        review_outcome=review_outcome,
        is_stamp_minted=True,
        pass_count=SINGLE_PASS_CAP,
        bound_hash="abc123",
    )
    encoded_payload = invoker.encode_stamp_mint_outcome(mint_outcome)
    assert encoded_payload[RESULT_KEY_STAMP_MINTED] is True
    assert encoded_payload[RESULT_KEY_PASS_COUNT] == SINGLE_PASS_CAP
    assert encoded_payload[RESULT_KEY_BOUND_HASH] == "abc123"


def test_record_stamp_mints_on_surface_stable_clean_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = prepared_surface_repo(monkeypatch, tmp_path)
    monkeypatch.setattr(invoker, "invoke_code_review", stable_clean_review)
    mint_outcome = invoker.invoke_code_review_and_record_stamp(
        working_directory=working_directory,
        session_model=CODE_REVIEW_MODEL_ALIAS,
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
        effort=EFFORT_LOW,
    )
    assert mint_outcome.is_stamp_minted is True
    assert mint_outcome.bound_hash is not None
    store_module = invoker.load_code_review_stamp_store()
    assert store_module.stamp_covers_surface(
        str(working_directory), mint_outcome.bound_hash, EFFORT_LOW
    )


def test_record_stamp_does_not_mint_when_review_changes_surface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = prepared_surface_repo(monkeypatch, tmp_path)
    monkeypatch.setattr(invoker, "invoke_code_review", surface_changing_review)
    mint_outcome = invoker.invoke_code_review_and_record_stamp(
        working_directory=working_directory,
        session_model=CODE_REVIEW_MODEL_ALIAS,
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
        effort=EFFORT_LOW,
        maximum_passes=SINGLE_PASS_CAP,
    )
    assert mint_outcome.is_stamp_minted is False
    assert mint_outcome.pass_count == SINGLE_PASS_CAP
    assert mint_outcome.bound_hash is None


def test_record_stamp_hits_cap_without_minting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = prepared_surface_repo(monkeypatch, tmp_path)
    monkeypatch.setattr(invoker, "invoke_code_review", DriftingReview())
    mint_outcome = invoker.invoke_code_review_and_record_stamp(
        working_directory=working_directory,
        session_model=CODE_REVIEW_MODEL_ALIAS,
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
        effort=EFFORT_LOW,
        maximum_passes=MAXIMUM_STAMP_MINT_PASSES,
    )
    assert mint_outcome.is_stamp_minted is False
    assert mint_outcome.pass_count == MAXIMUM_STAMP_MINT_PASSES


def test_load_code_review_stamp_store_records_and_covers_surface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = prepared_surface_repo(monkeypatch, tmp_path)
    store_module = invoker.load_code_review_stamp_store()
    surface_hash = store_module.live_surface_hash(str(working_directory))
    assert surface_hash is not None
    stamp_path = store_module.record_clean_stamp(
        str(working_directory), surface_hash, EFFORT_LOW
    )
    assert stamp_path.exists()
    assert store_module.stamp_covers_surface(
        str(working_directory), surface_hash, EFFORT_LOW
    )


def test_load_code_review_stamp_store_raises_when_file_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        invoker, "STAMP_STORE_MODULE_FILE_NAME", MISSING_STORE_FILE_NAME
    )
    with pytest.raises(ModuleNotFoundError):
        invoker.load_code_review_stamp_store()
