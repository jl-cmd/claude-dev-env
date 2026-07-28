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
from claude_chain_runner import ChainConfigurationError
from _code_review_test_support import FIXTURE_SESSION_OPUS
from dev_env_scripts_constants.code_review_constants import DEFAULT_CODE_REVIEW_EFFORT


CHAIN_CONFIG_REMEDY_TEXT: str = (
    "Claude chain config not found at the path this specification names. "
    "Copy the example config there and list your account binaries."
)
HOST_PROFILE_FAILURE_TEXT: str = "session model alias carries no host profile"
MINT_TIMEOUT_SECONDS: int = 1


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
