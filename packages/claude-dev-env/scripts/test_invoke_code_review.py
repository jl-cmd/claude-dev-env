"""Specifications for what a blocked mint tells the person it blocked.

Enforcement refuses every push until a clean stamp covers the branch surface,
and ``invoke_code_review.py --record-stamp`` is the only way to mint one. When
that call cannot run, the reason it names is the person's only route back to a
working push.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import invoke_code_review as invoker
from claude_chain_runner import ChainConfigurationError, ChainInvocationOutcome
from _code_review_test_support import FIXTURE_SESSION_OPUS
from dev_env_scripts_constants.claude_chain_constants import TERMINAL_STATUS_SERVED
from dev_env_scripts_constants.code_review_constants import (
    DEFAULT_CODE_REVIEW_EFFORT,
    PERMISSION_MODE_ACCEPT_EDITS,
    PERMISSION_MODE_BYPASS,
    REVIEW_PERMISSION_MODE,
)


def test_review_arguments_carry_the_permission_mode_this_caller_resolves() -> None:
    """The review command asks for a permission mode the binary accepts here.

    The binary refuses the bypass mode outright for a root caller, so asking
    for it there means no review runs and no stamp is ever minted.
    """
    all_arguments = invoker.build_code_review_arguments(DEFAULT_CODE_REVIEW_EFFORT)

    assert REVIEW_PERMISSION_MODE in all_arguments


def test_the_resolved_permission_mode_is_one_the_binary_knows() -> None:
    assert REVIEW_PERMISSION_MODE in (
        PERMISSION_MODE_ACCEPT_EDITS,
        PERMISSION_MODE_BYPASS,
    )


CHAIN_CONFIG_REMEDY_TEXT: str = (
    "Claude chain config not found at the path this specification names. "
    "Copy the example config there and list your account binaries."
)
HOST_PROFILE_FAILURE_TEXT: str = "session model alias carries no host profile"
MINT_TIMEOUT_SECONDS: int = 1
SERVED_COMMAND_NAME: str = "claude"
REVIEW_BINARY_REFUSAL_TEXT: str = (
    "--dangerously-skip-permissions cannot be used with root privileges"
)
REVIEW_FAILURE_RETURNCODE: int = 1
EMPTY_REVIEW_STDOUT: str = ""
ROOT_USER_ID: int = 0
UNPRIVILEGED_USER_ID: int = 1000


def _serve_a_refusing_binary(
    *_all_positional: object, **_all_keyword: object
) -> ChainInvocationOutcome:
    return ChainInvocationOutcome(
        served_command=SERVED_COMMAND_NAME,
        returncode=REVIEW_FAILURE_RETURNCODE,
        stdout=EMPTY_REVIEW_STDOUT,
        stderr=REVIEW_BINARY_REFUSAL_TEXT,
        attempts=(),
        terminal_status=TERMINAL_STATUS_SERVED,
    )


def test_failed_review_reports_what_the_served_binary_wrote(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A review that a served binary refused names the refusal.

    The binary can decline for reasons the caller must act on, such as a
    permission mode it will not accept. Dropping its words leaves a bare
    exit code, and no stamp is minted either way.
    """
    monkeypatch.setattr(
        invoker, "_run_claude_with_empty_stdin", _serve_a_refusing_binary
    )

    outcome = invoker._run_chain_review(
        working_directory=tmp_path,
        timeout_seconds=MINT_TIMEOUT_SECONDS,
        effort=DEFAULT_CODE_REVIEW_EFFORT,
    )

    captured_streams = capsys.readouterr()
    assert outcome.returncode == REVIEW_FAILURE_RETURNCODE
    assert REVIEW_BINARY_REFUSAL_TEXT in captured_streams.err


def test_missing_chain_config_reports_its_remedy_on_stderr(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_chain_configuration_error(**_all_keyword_arguments: object) -> None:
        raise ChainConfigurationError(CHAIN_CONFIG_REMEDY_TEXT)

    monkeypatch.setattr(
        invoker, "invoke_code_review_and_record_stamp", raise_chain_configuration_error
    )

    outcome = invoker._mint_or_config_outcome(
        working_directory=tmp_path,
        session_model=FIXTURE_SESSION_OPUS,
        timeout_seconds=MINT_TIMEOUT_SECONDS,
        effort=DEFAULT_CODE_REVIEW_EFFORT,
    )

    captured_streams = capsys.readouterr()
    assert outcome.is_stamp_minted is False
    assert CHAIN_CONFIG_REMEDY_TEXT in captured_streams.err


def test_host_profile_failure_reports_its_reason_on_stderr(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def raise_host_profile_error(**_all_keyword_arguments: object) -> None:
        raise ValueError(HOST_PROFILE_FAILURE_TEXT)

    monkeypatch.setattr(
        invoker, "invoke_code_review_and_record_stamp", raise_host_profile_error
    )

    outcome = invoker._mint_or_config_outcome(
        working_directory=tmp_path,
        session_model=FIXTURE_SESSION_OPUS,
        timeout_seconds=MINT_TIMEOUT_SECONDS,
        effort=DEFAULT_CODE_REVIEW_EFFORT,
    )

    captured_streams = capsys.readouterr()
    assert outcome.is_stamp_minted is False
    assert HOST_PROFILE_FAILURE_TEXT in captured_streams.err
