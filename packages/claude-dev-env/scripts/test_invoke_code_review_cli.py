"""CLI JSON output for in-session, error, effort, and record-stamp paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import invoke_code_review as invoker
from _code_review_test_support import (
    DriftingReview,
    EFFORT_LOW,
    FIXTURE_CHAIN_CONFIG_ERROR_MESSAGE,
    FIXTURE_HOST_PROFILE_ERROR_MESSAGE,
    FIXTURE_SESSION_OPUS,
    HOST_PROFILE_CLAUDE,
    HOST_PROFILE_THIRD_PARTY,
    REJECTED_ULTRA_EFFORT,
    init_git_repository,
    install_seams,
    prepared_surface_repo,
    run_record_stamp_cli,
    run_review_cli,
)
from claude_chain_runner import ChainConfigurationError
from dev_env_scripts_constants.claude_chain_constants import (
    CHAIN_CONFIG_ERROR_EXIT_CODE,
)
from dev_env_scripts_constants.code_review_constants import (
    CLI_SESSION_MODEL_FLAG,
    HOST_PROFILE_ERROR_RETURNCODE,
    IN_SESSION_RETURNCODE,
    INVALID_EFFORT_RETURNCODE,
    MAXIMUM_STAMP_MINT_PASSES,
    MODE_CHAIN,
    MODE_IN_SESSION,
    RESULT_KEY_BOUND_HASH,
    RESULT_KEY_DIRTY_TREE,
    RESULT_KEY_MODE,
    RESULT_KEY_PASS_COUNT,
    RESULT_KEY_RETURNCODE,
    RESULT_KEY_SERVED_COMMAND,
    RESULT_KEY_STAMP_MINTED,
    STAMP_DID_NOT_CONVERGE_RETURNCODE,
)
from dev_env_scripts_constants.grok_worker_constants import CWD_FLAG


def test_cli_prints_result_json_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_CLAUDE,
        claude_outcome=None,
        working_directory=working_directory,
    )

    exit_code = run_review_cli(working_directory, session_model=FIXTURE_SESSION_OPUS)

    assert exit_code == IN_SESSION_RETURNCODE
    captured = capsys.readouterr()
    assert captured.err == ""
    parsed_payload = json.loads(captured.out)
    assert parsed_payload == {
        RESULT_KEY_MODE: MODE_IN_SESSION,
        RESULT_KEY_SERVED_COMMAND: None,
        RESULT_KEY_RETURNCODE: IN_SESSION_RETURNCODE,
        RESULT_KEY_DIRTY_TREE: False,
    }


def test_cli_emits_json_on_chain_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=ChainConfigurationError(FIXTURE_CHAIN_CONFIG_ERROR_MESSAGE),
        working_directory=working_directory,
    )
    exit_code = run_review_cli(working_directory, session_model=FIXTURE_SESSION_OPUS)

    assert exit_code == CHAIN_CONFIG_ERROR_EXIT_CODE
    captured = capsys.readouterr()
    parsed_payload = json.loads(captured.out)
    assert parsed_payload == {
        RESULT_KEY_MODE: MODE_CHAIN,
        RESULT_KEY_SERVED_COMMAND: None,
        RESULT_KEY_RETURNCODE: CHAIN_CONFIG_ERROR_EXIT_CODE,
        RESULT_KEY_DIRTY_TREE: False,
    }
    config_error_outcome = invoker.CodeReviewOutcome(
        mode=MODE_CHAIN,
        served_command=None,
        returncode=CHAIN_CONFIG_ERROR_EXIT_CODE,
        is_dirty_tree=False,
    )
    assert invoker.is_code_review_clean_stamp_allowed(config_error_outcome) is False


def test_cli_emits_json_on_host_profile_value_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")

    def fake_host_profile_raises(setting_by_name: object | None = None) -> str:
        del setting_by_name
        raise ValueError(FIXTURE_HOST_PROFILE_ERROR_MESSAGE)

    monkeypatch.setattr(
        invoker, "review_host_profile_detector", fake_host_profile_raises
    )

    exit_code = run_review_cli(working_directory, session_model=FIXTURE_SESSION_OPUS)

    assert exit_code == HOST_PROFILE_ERROR_RETURNCODE
    captured = capsys.readouterr()
    parsed_payload = json.loads(captured.out)
    assert parsed_payload == {
        RESULT_KEY_MODE: MODE_CHAIN,
        RESULT_KEY_SERVED_COMMAND: None,
        RESULT_KEY_RETURNCODE: HOST_PROFILE_ERROR_RETURNCODE,
        RESULT_KEY_DIRTY_TREE: False,
    }


def test_cli_rejects_ultra_effort_with_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_CLAUDE,
        claude_outcome=None,
        working_directory=tmp_path,
    )
    exit_code = invoker.main(
        [
            CWD_FLAG,
            str(tmp_path),
            CLI_SESSION_MODEL_FLAG,
            FIXTURE_SESSION_OPUS,
            REJECTED_ULTRA_EFFORT,
        ]
    )
    assert exit_code == INVALID_EFFORT_RETURNCODE
    assert REJECTED_ULTRA_EFFORT in capsys.readouterr().err


def test_cli_record_stamp_returns_non_convergence_code_on_cap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    working_directory = prepared_surface_repo(monkeypatch, tmp_path)
    monkeypatch.setattr(invoker, "invoke_code_review", DriftingReview())
    exit_code = run_record_stamp_cli(working_directory, effort=EFFORT_LOW)
    assert exit_code == STAMP_DID_NOT_CONVERGE_RETURNCODE
    parsed_payload = json.loads(capsys.readouterr().out)
    assert parsed_payload[RESULT_KEY_STAMP_MINTED] is False
    assert parsed_payload[RESULT_KEY_PASS_COUNT] == MAXIMUM_STAMP_MINT_PASSES
    assert parsed_payload[RESULT_KEY_BOUND_HASH] is None


def test_cli_record_stamp_reports_missing_store_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_missing_store(*all_args: object, **all_keywords: object) -> object:
        del all_args, all_keywords
        raise ModuleNotFoundError("store missing", name="code_review_stamp_store")

    working_directory = prepared_surface_repo(monkeypatch, tmp_path)
    monkeypatch.setattr(invoker, "load_code_review_stamp_store", raise_missing_store)
    exit_code = run_record_stamp_cli(working_directory, effort=EFFORT_LOW)
    assert exit_code == INVALID_EFFORT_RETURNCODE
    captured = capsys.readouterr()
    assert "stamp store" in captured.err
    parsed_payload = json.loads(captured.out)
    assert parsed_payload[RESULT_KEY_STAMP_MINTED] is False
