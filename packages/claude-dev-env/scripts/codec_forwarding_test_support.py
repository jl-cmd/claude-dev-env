"""Shared fixtures for text-codec keyword-forwarding behavioral tests."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence

import claude_chain_runner as chain_runner
import pytest
from claude_chain_runner import ChainAttempt, ChainInvocationOutcome

FIXTURE_ENCODING_KEYWORD_NAME = "encoding"
FIXTURE_ERRORS_KEYWORD_NAME = "errors"
FIXTURE_CHAIN_ENCODING = "utf-8"
FIXTURE_CHAIN_ERRORS = "replace"
FIXTURE_SERVED_COMMAND = "claude"


def build_served_outcome(*, chain_stdout: str) -> ChainInvocationOutcome:
    return ChainInvocationOutcome(
        served_command=FIXTURE_SERVED_COMMAND,
        returncode=0,
        stdout=chain_stdout,
        stderr="",
        attempts=(ChainAttempt(command=FIXTURE_SERVED_COMMAND, status="served"),),
    )


def build_recording_runner(
    all_observed_runner_keywords: dict[str, object],
    *,
    chain_stdout: str,
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
            stdout=chain_stdout,
            stderr="",
        )

    return _recording_runner


def install_codec_seams(
    monkeypatch: pytest.MonkeyPatch,
    *,
    all_chain_codec_keywords: dict[str, str],
    chain_stdout: str,
    runner_host: object,
    runner_attribute_name: str,
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
        return build_served_outcome(chain_stdout=chain_stdout)

    monkeypatch.setattr(
        chain_runner,
        "chain_subprocess_runner",
        build_recording_runner(
            all_observed_runner_keywords,
            chain_stdout=chain_stdout,
        ),
    )
    monkeypatch.setattr(runner_host, runner_attribute_name, _fake_claude)
    return all_observed_runner_keywords
