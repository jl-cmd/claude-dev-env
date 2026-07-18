"""Behavioral tests for text codec keyword forwarding in worker-spawn headless overrides."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import claude_chain_runner as chain_runner  # noqa: E402
import resolve_worker_spawn as dispatcher  # noqa: E402
from claude_chain_runner import ChainAttempt, ChainInvocationOutcome  # noqa: E402
from dev_env_scripts_constants.grok_worker_constants import (  # noqa: E402
    DEFAULT_WORKER_TIMEOUT_SECONDS,
    UTF8_ENCODING,
)

FIXTURE_ENCODING_KEYWORD_NAME = "encoding"
FIXTURE_ERRORS_KEYWORD_NAME = "errors"
FIXTURE_CHAIN_ENCODING = "utf-8"
FIXTURE_CHAIN_ERRORS = "replace"
FIXTURE_SERVED_COMMAND = "claude"
FIXTURE_CHAIN_STDOUT = '{"tier":"claude","status":"done"}'
FIXTURE_PROMPT_TEXT = "do the work"


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
    monkeypatch.setattr(dispatcher, "spawn_claude_runner", _fake_claude)
    return all_observed_runner_keywords


def _run_headless_with_prompt(
    *,
    prompt_file: Path,
    working_directory: Path,
    timeout_seconds: int = DEFAULT_WORKER_TIMEOUT_SECONDS,
) -> None:
    prompt_stdin = prompt_file.open(encoding=UTF8_ENCODING)
    try:
        dispatcher._run_claude_with_headless_overrides(
            [],
            timeout_seconds=timeout_seconds,
            working_directory=working_directory,
            prompt_stdin=prompt_stdin,
        )
    finally:
        prompt_stdin.close()


def test_forwards_text_codec_keywords_to_subprocess_runner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(FIXTURE_PROMPT_TEXT, encoding=UTF8_ENCODING)
    all_observed_runner_keywords = _install_codec_seams(
        monkeypatch,
        all_chain_codec_keywords={
            FIXTURE_ENCODING_KEYWORD_NAME: FIXTURE_CHAIN_ENCODING,
            FIXTURE_ERRORS_KEYWORD_NAME: FIXTURE_CHAIN_ERRORS,
        },
    )

    _run_headless_with_prompt(
        prompt_file=prompt_file,
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
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(FIXTURE_PROMPT_TEXT, encoding=UTF8_ENCODING)
    all_observed_runner_keywords = _install_codec_seams(
        monkeypatch,
        all_chain_codec_keywords={},
    )

    _run_headless_with_prompt(
        prompt_file=prompt_file,
        working_directory=tmp_path,
    )

    assert FIXTURE_ENCODING_KEYWORD_NAME not in all_observed_runner_keywords
    assert FIXTURE_ERRORS_KEYWORD_NAME not in all_observed_runner_keywords
