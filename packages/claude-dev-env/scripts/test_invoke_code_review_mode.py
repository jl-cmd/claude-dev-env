"""Mode-decision behavior of the host-aware ``/code-review`` invoker."""

from __future__ import annotations

from pathlib import Path

import pytest

import invoke_code_review as invoker
from _code_review_test_support import (
    FIXTURE_SESSION_HAIKU,
    FIXTURE_SESSION_OPUS,
    FIXTURE_SESSION_OPUS_UPPER,
    FIXTURE_SESSION_SONNET,
    HOST_PROFILE_CLAUDE,
    HOST_PROFILE_THIRD_PARTY,
    claude_served,
    init_git_repository,
    install_seams,
    run_review,
)
from dev_env_scripts_constants.code_review_constants import (
    IN_SESSION_RETURNCODE,
    MODE_CHAIN,
    MODE_IN_SESSION,
    SESSION_HAS_USAGE_LEFT_FALSE,
    SESSION_HAS_USAGE_LEFT_TRUE,
    SESSION_HAS_USAGE_LEFT_UNKNOWN,
)


@pytest.mark.parametrize(
    ("host_profile", "session_model", "expected_mode"),
    [
        (HOST_PROFILE_CLAUDE, FIXTURE_SESSION_OPUS, MODE_IN_SESSION),
        (HOST_PROFILE_CLAUDE, FIXTURE_SESSION_OPUS_UPPER, MODE_IN_SESSION),
        (HOST_PROFILE_CLAUDE, FIXTURE_SESSION_SONNET, MODE_CHAIN),
        (HOST_PROFILE_CLAUDE, FIXTURE_SESSION_HAIKU, MODE_CHAIN),
        (HOST_PROFILE_THIRD_PARTY, FIXTURE_SESSION_OPUS, MODE_CHAIN),
        (HOST_PROFILE_THIRD_PARTY, FIXTURE_SESSION_SONNET, MODE_CHAIN),
    ],
)
def test_mode_decision_host_and_model_matrix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    host_profile: str,
    session_model: str,
    expected_mode: str,
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    claude_outcome = claude_served() if expected_mode == MODE_CHAIN else None
    call_log = install_seams(
        monkeypatch,
        host_profile=host_profile,
        claude_outcome=claude_outcome,
        working_directory=working_directory,
    )

    review_outcome = run_review(working_directory, session_model=session_model)

    assert review_outcome.mode == expected_mode
    assert call_log.host_profile_calls == 1
    if expected_mode == MODE_IN_SESSION:
        assert call_log.claude_calls == 0
        assert review_outcome.served_command is None
        assert review_outcome.returncode == IN_SESSION_RETURNCODE
        assert review_outcome.is_dirty_tree is False
    else:
        assert call_log.claude_calls == 1


@pytest.mark.parametrize(
    ("session_model", "expected_is_opus"),
    [
        (FIXTURE_SESSION_OPUS, True),
        (FIXTURE_SESSION_OPUS_UPPER, True),
        (FIXTURE_SESSION_SONNET, False),
        ("  opus  ", True),
    ],
)
def test_is_opus_session_model(session_model: str, expected_is_opus: bool) -> None:
    assert invoker.is_opus_session_model(session_model) is expected_is_opus


@pytest.mark.parametrize(
    ("host_profile", "session_model", "expected_mode"),
    [
        (HOST_PROFILE_CLAUDE, FIXTURE_SESSION_OPUS, MODE_IN_SESSION),
        (HOST_PROFILE_CLAUDE, FIXTURE_SESSION_SONNET, MODE_CHAIN),
        (HOST_PROFILE_THIRD_PARTY, FIXTURE_SESSION_OPUS, MODE_CHAIN),
    ],
)
def test_decide_review_mode(
    host_profile: str, session_model: str, expected_mode: str
) -> None:
    assert (
        invoker.decide_review_mode(
            host_profile=host_profile,
            session_model=session_model,
        )
        == expected_mode
    )


@pytest.mark.parametrize(
    ("session_has_usage_left", "expected_mode"),
    [
        (False, MODE_CHAIN),
        (True, MODE_IN_SESSION),
        (None, MODE_IN_SESSION),
    ],
)
def test_decide_review_mode_session_has_usage_left(
    session_has_usage_left: bool | None, expected_mode: str
) -> None:
    assert (
        invoker.decide_review_mode(
            host_profile=HOST_PROFILE_CLAUDE,
            session_model=FIXTURE_SESSION_OPUS,
            session_has_usage_left=session_has_usage_left,
        )
        == expected_mode
    )


@pytest.mark.parametrize(
    ("session_has_usage_left_token", "expected_value"),
    [
        (SESSION_HAS_USAGE_LEFT_TRUE, True),
        (SESSION_HAS_USAGE_LEFT_FALSE, False),
        (SESSION_HAS_USAGE_LEFT_UNKNOWN, None),
        ("TRUE", True),
    ],
)
def test_parse_session_has_usage_left_token(
    session_has_usage_left_token: str, expected_value: bool | None
) -> None:
    assert (
        invoker.parse_session_has_usage_left_token(session_has_usage_left_token)
        is expected_value
    )


def test_parse_session_has_usage_left_token_rejects_unsupported_label() -> None:
    with pytest.raises(ValueError):
        invoker.parse_session_has_usage_left_token("bogus")


def test_install_seams_auto_probe_forces_chain_without_live_subprocess(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    call_log = install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_CLAUDE,
        claude_outcome=claude_served(),
        working_directory=working_directory,
        session_has_usage_left=False,
    )

    review_outcome = run_review(working_directory, session_model=FIXTURE_SESSION_OPUS)

    assert review_outcome.mode == MODE_CHAIN
    assert call_log.claude_calls == 1
