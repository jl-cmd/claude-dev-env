"""Behavioral tests for text codec keyword forwarding in worker-spawn headless overrides."""

from __future__ import annotations

from pathlib import Path

import pytest
import resolve_worker_spawn as dispatcher
from codec_forwarding_test_support import (
    FIXTURE_CHAIN_ENCODING,
    FIXTURE_CHAIN_ERRORS,
    FIXTURE_ENCODING_KEYWORD_NAME,
    FIXTURE_ERRORS_KEYWORD_NAME,
    install_codec_seams,
)
from dev_env_scripts_constants.grok_worker_constants import (
    DEFAULT_WORKER_TIMEOUT_SECONDS,
    UTF8_ENCODING,
)

FIXTURE_CHAIN_STDOUT = '{"tier":"claude","status":"done"}'
FIXTURE_PROMPT_TEXT = "do the work"


def _install_dispatcher_codec_seams(
    monkeypatch: pytest.MonkeyPatch,
    *,
    all_chain_codec_keywords: dict[str, str],
) -> dict[str, object]:
    return install_codec_seams(
        monkeypatch,
        all_chain_codec_keywords=all_chain_codec_keywords,
        chain_stdout=FIXTURE_CHAIN_STDOUT,
        runner_host=dispatcher,
        runner_attribute_name="spawn_claude_runner",
    )


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
    all_observed_runner_keywords = _install_dispatcher_codec_seams(
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
    all_observed_runner_keywords = _install_dispatcher_codec_seams(
        monkeypatch,
        all_chain_codec_keywords={},
    )

    _run_headless_with_prompt(
        prompt_file=prompt_file,
        working_directory=tmp_path,
    )

    assert FIXTURE_ENCODING_KEYWORD_NAME not in all_observed_runner_keywords
    assert FIXTURE_ERRORS_KEYWORD_NAME not in all_observed_runner_keywords
