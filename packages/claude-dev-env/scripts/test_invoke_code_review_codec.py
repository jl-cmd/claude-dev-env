"""Behavioral tests for text codec keyword forwarding in the ``/code-review`` invoker."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import claude_chain_runner as chain_runner
import invoke_code_review as invoker
import pytest
from claude_chain_runner import ChainAttempt, ChainInvocationOutcome
from dev_env_scripts_constants.timing import DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS

FIXTURE_ENCODING_KEYWORD_NAME = "encoding"
FIXTURE_ERRORS_KEYWORD_NAME = "errors"
FIXTURE_CHAIN_ENCODING = "utf-8"
FIXTURE_CHAIN_ERRORS = "replace"
FIXTURE_SERVED_COMMAND = "claude"
FIXTURE_CHAIN_STDOUT = '{"result":"review done"}'


def _served_outcome() -> ChainInvocationOutcome:
    return ChainInvocationOutcome(
        served_command=FIXTURE_SERVED_COMMAND,
        returncode=0,
        stdout=FIXTURE_CHAIN_STDOUT,
        stderr="",
        attempts=(ChainAttempt(command=FIXTURE_SERVED_COMMAND, status="served"),),
    )


def _build_recording_runner(
    all_observed_runner_keywords: dict[str, object],
) -> object:
    def _recording_runner(
        all_invocation_tokens: Sequence[str],
        *all_positionals: object,
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_positionals
        all_observed_runner_keywords.update(all_keywords)
        return subprocess.CompletedProcess(
            args=list(all_invocation_tokens),
            returncode=0,
            stdout=FIXTURE_CHAIN_STDOUT,
            stderr="",
        )

    return _recording_runner


def _install_codec_seams(
    monkeypatch: pytest.MonkeyPatch,
    *,
    all_chain_codec_keywords: dict[str, str],
) -> dict[str, object]:
    all_observed_runner_keywords: dict[str, object] = {}

    def _fake_claude(
        all_claude_arguments: list[str], *, timeout_seconds: int
    ) -> ChainInvocationOutcome:
        chain_runner.chain_subprocess_runner(
            [FIXTURE_SERVED_COMMAND, *all_claude_arguments],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            **all_chain_codec_keywords,
        )
        return _served_outcome()

    monkeypatch.setattr(
        chain_runner,
        "chain_subprocess_runner",
        _build_recording_runner(all_observed_runner_keywords),
    )
    monkeypatch.setattr(invoker, "review_claude_runner", _fake_claude)
    return all_observed_runner_keywords


def test_forwards_text_codec_keywords_to_subprocess_runner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    all_observed_runner_keywords = _install_codec_seams(
        monkeypatch,
        all_chain_codec_keywords={
            FIXTURE_ENCODING_KEYWORD_NAME: FIXTURE_CHAIN_ENCODING,
            FIXTURE_ERRORS_KEYWORD_NAME: FIXTURE_CHAIN_ERRORS,
        },
    )

    invoker._run_claude_with_empty_stdin(
        [],
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
        working_directory=tmp_path,
    )

    assert (
        all_observed_runner_keywords[FIXTURE_ENCODING_KEYWORD_NAME]
        == FIXTURE_CHAIN_ENCODING
    )
    assert (
        all_observed_runner_keywords[FIXTURE_ERRORS_KEYWORD_NAME]
        == FIXTURE_CHAIN_ERRORS
    )


def test_absent_text_codec_keywords_are_not_invented(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    all_observed_runner_keywords = _install_codec_seams(
        monkeypatch,
        all_chain_codec_keywords={},
    )

    invoker._run_claude_with_empty_stdin(
        [],
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
        working_directory=tmp_path,
    )

    assert FIXTURE_ENCODING_KEYWORD_NAME not in all_observed_runner_keywords
    assert FIXTURE_ERRORS_KEYWORD_NAME not in all_observed_runner_keywords
