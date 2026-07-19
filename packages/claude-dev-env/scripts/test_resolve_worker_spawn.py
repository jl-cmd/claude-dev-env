"""Behavioral tests for the worker-spawn tier dispatcher."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import claude_chain_runner as chain_runner  # noqa: E402
import resolve_worker_spawn as dispatcher  # noqa: E402
from claude_chain_runner import (  # noqa: E402
    ChainAttempt,
    ChainConfigurationError,
    ChainInvocationOutcome,
)
from dev_env_scripts_constants.grok_worker_constants import (  # noqa: E402
    AGENT_FLAG,
    ALL_AGENT_FILENAMES_BY_ROLE,
    ATTEMPT_KEY_OK,
    ATTEMPT_KEY_REASON,
    ATTEMPT_KEY_TIER,
    CLI_ENABLE_CLAUDE_TIER_FLAG,
    CLI_ROLE_FLAG,
    CLI_RUN_STATE_DIR_FLAG,
    CLI_TIMEOUT_FLAG,
    CLASSIFICATION_AUTH_FAILURE,
    CLASSIFICATION_OK,
    CLASSIFICATION_USAGE_LIMIT,
    CWD_FLAG,
    DEFAULT_ROLE,
    DEFAULT_SPAWN_MAX_TURNS,
    DEFAULT_WORKER_TIMEOUT_SECONDS,
    OUTPUT_FORMAT_FLAG,
    OUTPUT_FORMAT_JSON,
    PROMPT_FILE_FLAG,
    REASON_CLAUDE_AGENT_REQUIRED,
    REASON_GROK_AUTH_FAILED,
    REASON_PROMPT_FILE_MISSING,
    RESULT_KEY_ATTEMPTS,
    RESULT_KEY_OK,
    RESULT_KEY_OUTPUT,
    RESULT_KEY_RETURNCODE,
    RESULT_KEY_TIER_USED,
    SINGLE_TURN_FLAG,
    SPAWN_CONFIG_ERROR_EXIT_CODE,
    SPAWN_EXHAUSTED_EXIT_CODE,
    SPAWN_SERVED_EXIT_CODE,
    TIER_CLAUDE_AGENT,
    TIER_CLAUDE_HEADLESS,
    TIER_GROK,
)
from grok_headless_runner import GrokRunnerOutcome  # noqa: E402
from grok_worker_preflight import PreflightOutcome  # noqa: E402

HOST_PROFILE_CLAUDE = "Claude"
HOST_PROFILE_THIRD_PARTY = "ThirdParty"

FIXTURE_GROK_STDOUT = '{"tier":"grok","status":"done"}'
FIXTURE_CLAUDE_STDOUT = '{"tier":"claude","status":"done"}'
FIXTURE_PROMPT_TEXT = "do the work"
FIXTURE_GROK_RETURNCODE = 0
FIXTURE_CLAUDE_RETURNCODE = 0
FIXTURE_FAILED_RETURNCODE = 1
FIXTURE_ROLE = "code-quality-agent"
LARGE_PROMPT_CHARACTER_COUNT = 40000
WINDOWS_SAFE_ARGV_ELEMENT_CEILING = 8192
EXPECTED_PRIMARY_AGENT_FOR_DEFAULT_ROLE = Path(
    ALL_AGENT_FILENAMES_BY_ROLE[DEFAULT_ROLE][0]
).stem


def _usable_preflight() -> PreflightOutcome:
    return PreflightOutcome(is_usable=True, reason=None)


def _fallthrough_preflight(reason: str) -> PreflightOutcome:
    return PreflightOutcome(is_usable=False, reason=reason)


def _grok_ok(stdout: str = FIXTURE_GROK_STDOUT) -> GrokRunnerOutcome:
    return GrokRunnerOutcome(
        is_ok=True,
        returncode=FIXTURE_GROK_RETURNCODE,
        classification=CLASSIFICATION_OK,
        stdout=stdout,
        stderr="",
    )


def _grok_failure(
    classification: str,
    *,
    returncode: int = FIXTURE_FAILED_RETURNCODE,
    stdout: str = "",
    stderr: str = "",
) -> GrokRunnerOutcome:
    return GrokRunnerOutcome(
        is_ok=False,
        returncode=returncode,
        classification=classification,
        stdout=stdout,
        stderr=stderr,
    )


def _claude_served(
    stdout: str = FIXTURE_CLAUDE_STDOUT,
    *,
    returncode: int = FIXTURE_CLAUDE_RETURNCODE,
) -> ChainInvocationOutcome:
    return ChainInvocationOutcome(
        served_command="claude",
        returncode=returncode,
        stdout=stdout,
        stderr="",
        attempts=(ChainAttempt(command="claude", status="served"),),
    )


def _claude_exhausted() -> ChainInvocationOutcome:
    return ChainInvocationOutcome(
        served_command=None,
        returncode=FIXTURE_FAILED_RETURNCODE,
        stdout="",
        stderr="usage limit reached",
        attempts=(ChainAttempt(command="claude", status="usage_limited"),),
    )


def _paths(tmp_path: Path) -> tuple[Path, Path, Path]:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(FIXTURE_PROMPT_TEXT, encoding="utf-8")
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    run_state_directory.mkdir()
    return prompt_file, working_directory, run_state_directory


@dataclass
class SeamCallLog:
    preflight_calls: int = 0
    grok_calls: int = 0
    claude_calls: int = 0
    claude_arguments: list[str] | None = None
    host_profile_calls: int = 0
    is_stdin_from_prompt_file: bool = False
    claude_stdin_path: Path | None = None
    claude_working_directory: Path | None = None
    grok_keyword_arguments: dict[str, object] | None = None
    max_argv_element_length: int = 0
    all_observed_working_directories: list[Path] = field(default_factory=list)


def _install_seams(
    monkeypatch: pytest.MonkeyPatch,
    *,
    preflight_outcome: PreflightOutcome = _usable_preflight(),
    grok_outcome: GrokRunnerOutcome | None = None,
    claude_outcome: ChainInvocationOutcome | BaseException | None = None,
    host_profile: str = HOST_PROFILE_CLAUDE,
) -> SeamCallLog:
    call_log = SeamCallLog()

    def fake_preflight(**_keyword_arguments: object) -> PreflightOutcome:
        call_log.preflight_calls += 1
        return preflight_outcome

    def fake_grok(**keyword_arguments: object) -> GrokRunnerOutcome:
        call_log.grok_calls += 1
        call_log.grok_keyword_arguments = dict(keyword_arguments)
        assert grok_outcome is not None
        return grok_outcome

    def fake_claude(
        all_claude_arguments: list[str], *, timeout_seconds: int
    ) -> ChainInvocationOutcome:
        call_log.claude_calls += 1
        call_log.claude_arguments = list(all_claude_arguments)
        chain_runner.chain_subprocess_runner(
            ["claude", *all_claude_arguments],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        if isinstance(claude_outcome, BaseException):
            raise claude_outcome
        assert isinstance(claude_outcome, ChainInvocationOutcome)
        return claude_outcome

    def fake_host_profile(
        setting_by_name: object | None = None,
    ) -> str:
        del setting_by_name
        call_log.host_profile_calls += 1
        return host_profile

    monkeypatch.setattr(dispatcher, "spawn_preflight_runner", fake_preflight)
    monkeypatch.setattr(dispatcher, "spawn_grok_runner", fake_grok)
    monkeypatch.setattr(dispatcher, "spawn_claude_runner", fake_claude)
    monkeypatch.setattr(dispatcher, "spawn_host_profile_detector", fake_host_profile)

    def _tracking_subprocess_runner(
        all_invocation_tokens: Sequence[str],
        *all_positionals: object,
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_positionals
        for each_token in all_invocation_tokens:
            call_log.max_argv_element_length = max(
                call_log.max_argv_element_length, len(str(each_token))
            )
        maybe_stdin = all_keywords.get("stdin")
        if maybe_stdin is not None and maybe_stdin is not subprocess.DEVNULL:
            call_log.is_stdin_from_prompt_file = True
            maybe_name = getattr(maybe_stdin, "name", None)
            if maybe_name is not None:
                call_log.claude_stdin_path = Path(str(maybe_name))
        maybe_cwd = all_keywords.get("cwd")
        if maybe_cwd is not None:
            working_directory = Path(str(maybe_cwd))
            call_log.claude_working_directory = working_directory
            call_log.all_observed_working_directories.append(working_directory)
        return subprocess.CompletedProcess(
            args=list(all_invocation_tokens),
            returncode=0,
            stdout="{}",
            stderr="",
        )

    monkeypatch.setattr(
        chain_runner, "chain_subprocess_runner", _tracking_subprocess_runner
    )
    return call_log


def test_grok_ok_serves_tier_one(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    call_log = _install_seams(
        monkeypatch,
        grok_outcome=_grok_ok(),
    )

    spawn_outcome = dispatcher.resolve_worker_spawn(
        role=FIXTURE_ROLE,
        prompt_file=prompt_file,
        working_directory=working_directory,
        timeout_seconds=DEFAULT_WORKER_TIMEOUT_SECONDS,
        is_claude_tier_enabled=False,
        run_state_directory=run_state_directory,
        max_turns=DEFAULT_SPAWN_MAX_TURNS,
    )

    assert spawn_outcome.is_ok is True
    assert spawn_outcome.tier_used == TIER_GROK
    assert spawn_outcome.captured_stdout == FIXTURE_GROK_STDOUT
    assert spawn_outcome.returncode == FIXTURE_GROK_RETURNCODE
    assert call_log.preflight_calls == 1
    assert call_log.grok_calls == 1
    assert call_log.claude_calls == 0
    assert call_log.host_profile_calls == 0
    assert call_log.grok_keyword_arguments is not None
    assert call_log.grok_keyword_arguments["agent_name"] == FIXTURE_ROLE
    assert len(spawn_outcome.all_attempts) == 1
    assert spawn_outcome.all_attempts[0].tier == TIER_GROK
    assert spawn_outcome.all_attempts[0].is_ok is True
    assert spawn_outcome.all_attempts[0].reason is None


def test_grok_usage_limited_on_claude_host_requires_agent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    call_log = _install_seams(
        monkeypatch,
        grok_outcome=_grok_failure(CLASSIFICATION_USAGE_LIMIT),
        host_profile=HOST_PROFILE_CLAUDE,
    )

    spawn_outcome = dispatcher.resolve_worker_spawn(
        role=FIXTURE_ROLE,
        prompt_file=prompt_file,
        working_directory=working_directory,
        timeout_seconds=DEFAULT_WORKER_TIMEOUT_SECONDS,
        is_claude_tier_enabled=False,
        run_state_directory=run_state_directory,
        max_turns=DEFAULT_SPAWN_MAX_TURNS,
    )

    assert spawn_outcome.is_ok is False
    assert spawn_outcome.tier_used is None
    assert call_log.claude_calls == 0
    assert call_log.host_profile_calls == 1
    all_reasons = [each_attempt.reason for each_attempt in spawn_outcome.all_attempts]
    assert REASON_CLAUDE_AGENT_REQUIRED in all_reasons
    assert spawn_outcome.all_attempts[0].tier == TIER_GROK
    assert spawn_outcome.all_attempts[0].is_ok is False
    assert spawn_outcome.all_attempts[0].reason == CLASSIFICATION_USAGE_LIMIT
    assert spawn_outcome.all_attempts[1].tier == TIER_CLAUDE_AGENT
    assert spawn_outcome.all_attempts[1].reason == REASON_CLAUDE_AGENT_REQUIRED


def test_grok_auth_failed_on_third_party_runs_tier_three(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    call_log = _install_seams(
        monkeypatch,
        grok_outcome=_grok_failure(CLASSIFICATION_AUTH_FAILURE),
        claude_outcome=_claude_served(),
        host_profile=HOST_PROFILE_THIRD_PARTY,
    )

    spawn_outcome = dispatcher.resolve_worker_spawn(
        role=FIXTURE_ROLE,
        prompt_file=prompt_file,
        working_directory=working_directory,
        timeout_seconds=DEFAULT_WORKER_TIMEOUT_SECONDS,
        is_claude_tier_enabled=False,
        run_state_directory=run_state_directory,
        max_turns=DEFAULT_SPAWN_MAX_TURNS,
    )

    assert spawn_outcome.is_ok is True
    assert spawn_outcome.tier_used == TIER_CLAUDE_HEADLESS
    assert spawn_outcome.captured_stdout == FIXTURE_CLAUDE_STDOUT
    assert call_log.claude_calls == 1
    assert call_log.claude_arguments is not None
    assert PROMPT_FILE_FLAG not in call_log.claude_arguments
    assert FIXTURE_PROMPT_TEXT not in call_log.claude_arguments
    assert call_log.claude_arguments == [
        SINGLE_TURN_FLAG,
        OUTPUT_FORMAT_FLAG,
        OUTPUT_FORMAT_JSON,
        AGENT_FLAG,
        FIXTURE_ROLE,
    ]
    assert call_log.is_stdin_from_prompt_file is True
    assert call_log.claude_stdin_path == prompt_file
    assert call_log.claude_working_directory == working_directory
    assert spawn_outcome.all_attempts[0].tier == TIER_GROK
    assert spawn_outcome.all_attempts[0].reason == CLASSIFICATION_AUTH_FAILURE
    assert spawn_outcome.all_attempts[1].tier == TIER_CLAUDE_HEADLESS
    assert spawn_outcome.all_attempts[1].is_ok is True


def test_tier_three_exhausted_returns_exit_two(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    _install_seams(
        monkeypatch,
        grok_outcome=_grok_failure(CLASSIFICATION_AUTH_FAILURE),
        claude_outcome=_claude_exhausted(),
        host_profile=HOST_PROFILE_THIRD_PARTY,
    )

    exit_code = dispatcher.main(
        [
            CLI_ROLE_FLAG,
            FIXTURE_ROLE,
            PROMPT_FILE_FLAG,
            str(prompt_file),
            CWD_FLAG,
            str(working_directory),
            CLI_TIMEOUT_FLAG,
            str(DEFAULT_WORKER_TIMEOUT_SECONDS),
            CLI_RUN_STATE_DIR_FLAG,
            str(run_state_directory),
        ]
    )

    assert exit_code == SPAWN_EXHAUSTED_EXIT_CODE
    captured = capsys.readouterr()
    parsed_payload = json.loads(captured.out)
    assert parsed_payload[RESULT_KEY_OK] is False
    assert parsed_payload[RESULT_KEY_TIER_USED] is None


def test_config_error_returns_exit_three(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    _install_seams(
        monkeypatch,
        grok_outcome=_grok_failure(CLASSIFICATION_AUTH_FAILURE),
        claude_outcome=ChainConfigurationError("chain config missing"),
        host_profile=HOST_PROFILE_THIRD_PARTY,
    )

    exit_code = dispatcher.main(
        [
            CLI_ROLE_FLAG,
            FIXTURE_ROLE,
            PROMPT_FILE_FLAG,
            str(prompt_file),
            CWD_FLAG,
            str(working_directory),
            CLI_TIMEOUT_FLAG,
            str(DEFAULT_WORKER_TIMEOUT_SECONDS),
            CLI_RUN_STATE_DIR_FLAG,
            str(run_state_directory),
        ]
    )

    assert exit_code == SPAWN_CONFIG_ERROR_EXIT_CODE
    captured = capsys.readouterr()
    parsed_payload = json.loads(captured.out)
    assert parsed_payload[RESULT_KEY_OK] is False
    assert parsed_payload[RESULT_KEY_RETURNCODE] == SPAWN_CONFIG_ERROR_EXIT_CODE


def test_attempts_array_ordering_across_tiers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    _install_seams(
        monkeypatch,
        grok_outcome=_grok_failure(CLASSIFICATION_USAGE_LIMIT),
        claude_outcome=_claude_served(),
        host_profile=HOST_PROFILE_CLAUDE,
    )

    spawn_outcome = dispatcher.resolve_worker_spawn(
        role=FIXTURE_ROLE,
        prompt_file=prompt_file,
        working_directory=working_directory,
        timeout_seconds=DEFAULT_WORKER_TIMEOUT_SECONDS,
        is_claude_tier_enabled=True,
        run_state_directory=run_state_directory,
        max_turns=DEFAULT_SPAWN_MAX_TURNS,
    )

    all_tiers = [each_attempt.tier for each_attempt in spawn_outcome.all_attempts]
    assert all_tiers == [TIER_GROK, TIER_CLAUDE_HEADLESS]
    assert spawn_outcome.tier_used == TIER_CLAUDE_HEADLESS


def test_cli_stdout_carries_only_json_result(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    _install_seams(
        monkeypatch,
        grok_outcome=_grok_ok(),
    )

    exit_code = dispatcher.main(
        [
            CLI_ROLE_FLAG,
            FIXTURE_ROLE,
            PROMPT_FILE_FLAG,
            str(prompt_file),
            CWD_FLAG,
            str(working_directory),
            CLI_TIMEOUT_FLAG,
            str(DEFAULT_WORKER_TIMEOUT_SECONDS),
            CLI_RUN_STATE_DIR_FLAG,
            str(run_state_directory),
        ]
    )

    assert exit_code == SPAWN_SERVED_EXIT_CODE
    captured = capsys.readouterr()
    assert captured.err == ""
    parsed_payload = json.loads(captured.out)
    assert captured.out == json.dumps(
        parsed_payload
    ) + "\n" or captured.out.strip() == json.dumps(parsed_payload)
    reparsed = json.loads(captured.out.strip())
    assert reparsed is not None
    assert set(reparsed.keys()) == {
        RESULT_KEY_TIER_USED,
        RESULT_KEY_OK,
        RESULT_KEY_ATTEMPTS,
        RESULT_KEY_OUTPUT,
        RESULT_KEY_RETURNCODE,
    }
    assert reparsed[RESULT_KEY_TIER_USED] == TIER_GROK
    assert reparsed[RESULT_KEY_OK] is True
    assert reparsed[RESULT_KEY_OUTPUT] == FIXTURE_GROK_STDOUT
    first_attempt = reparsed[RESULT_KEY_ATTEMPTS][0]
    assert first_attempt[ATTEMPT_KEY_TIER] == TIER_GROK
    assert first_attempt[ATTEMPT_KEY_OK] is True
    assert first_attempt[ATTEMPT_KEY_REASON] is None


def test_preflight_fallthrough_skips_grok_runner(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    call_log = _install_seams(
        monkeypatch,
        preflight_outcome=_fallthrough_preflight(REASON_GROK_AUTH_FAILED),
        host_profile=HOST_PROFILE_CLAUDE,
    )

    spawn_outcome = dispatcher.resolve_worker_spawn(
        role=DEFAULT_ROLE,
        prompt_file=prompt_file,
        working_directory=working_directory,
        timeout_seconds=DEFAULT_WORKER_TIMEOUT_SECONDS,
        is_claude_tier_enabled=False,
        run_state_directory=run_state_directory,
        max_turns=DEFAULT_SPAWN_MAX_TURNS,
    )

    assert call_log.grok_calls == 0
    assert spawn_outcome.all_attempts[0].reason == REASON_GROK_AUTH_FAILED
    assert REASON_CLAUDE_AGENT_REQUIRED in [
        each_attempt.reason for each_attempt in spawn_outcome.all_attempts
    ]


def test_detect_host_profile_is_consumed_not_reimplemented() -> None:
    source_text = Path(dispatcher.__file__).read_text(encoding="utf-8")
    assert "spawn_host_profile_detector" in source_text
    assert "detect_host_profile" in source_text
    assert "ADVISOR_HOST_PROFILE" not in source_text
    assert "THIRD_PARTY" not in source_text


def test_default_max_turns_reaches_grok_kwargs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    call_log = _install_seams(
        monkeypatch,
        grok_outcome=_grok_ok(),
    )

    exit_code = dispatcher.main(
        [
            CLI_ROLE_FLAG,
            FIXTURE_ROLE,
            PROMPT_FILE_FLAG,
            str(prompt_file),
            CWD_FLAG,
            str(working_directory),
            CLI_TIMEOUT_FLAG,
            str(DEFAULT_WORKER_TIMEOUT_SECONDS),
            CLI_RUN_STATE_DIR_FLAG,
            str(run_state_directory),
        ]
    )

    assert exit_code == SPAWN_SERVED_EXIT_CODE
    assert call_log.grok_keyword_arguments is not None
    assert call_log.grok_keyword_arguments["max_turns"] == DEFAULT_SPAWN_MAX_TURNS
    parsed_payload = json.loads(capsys.readouterr().out)
    assert parsed_payload[RESULT_KEY_OK] is True


def test_encode_spawn_outcome_shape() -> None:
    spawn_outcome = dispatcher.SpawnOutcome(
        tier_used=TIER_GROK,
        is_ok=True,
        all_attempts=(
            dispatcher.SpawnAttempt(tier=TIER_GROK, is_ok=True, reason=None),
        ),
        captured_stdout=FIXTURE_GROK_STDOUT,
        returncode=FIXTURE_GROK_RETURNCODE,
    )
    encoded_payload = dispatcher.encode_spawn_outcome(spawn_outcome)
    assert encoded_payload[RESULT_KEY_TIER_USED] == TIER_GROK
    assert encoded_payload[RESULT_KEY_OK] is True
    assert encoded_payload[RESULT_KEY_OUTPUT] == FIXTURE_GROK_STDOUT
    assert encoded_payload[RESULT_KEY_RETURNCODE] == FIXTURE_GROK_RETURNCODE
    assert encoded_payload[RESULT_KEY_ATTEMPTS] == [
        {
            ATTEMPT_KEY_TIER: TIER_GROK,
            ATTEMPT_KEY_OK: True,
            ATTEMPT_KEY_REASON: None,
        }
    ]


def test_enable_claude_tier_flag_reaches_tier_three_on_claude_host(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    call_log = _install_seams(
        monkeypatch,
        grok_outcome=_grok_failure(CLASSIFICATION_USAGE_LIMIT),
        claude_outcome=_claude_served(),
        host_profile=HOST_PROFILE_CLAUDE,
    )

    exit_code = dispatcher.main(
        [
            CLI_ROLE_FLAG,
            FIXTURE_ROLE,
            PROMPT_FILE_FLAG,
            str(prompt_file),
            CWD_FLAG,
            str(working_directory),
            CLI_TIMEOUT_FLAG,
            str(DEFAULT_WORKER_TIMEOUT_SECONDS),
            CLI_ENABLE_CLAUDE_TIER_FLAG,
            CLI_RUN_STATE_DIR_FLAG,
            str(run_state_directory),
        ]
    )

    assert exit_code == SPAWN_SERVED_EXIT_CODE
    assert call_log.claude_calls == 1
    assert call_log.is_stdin_from_prompt_file is True
    assert call_log.claude_stdin_path == prompt_file
    assert call_log.claude_working_directory == working_directory
    assert call_log.claude_arguments is not None
    assert PROMPT_FILE_FLAG not in call_log.claude_arguments
    assert SINGLE_TURN_FLAG in call_log.claude_arguments
    assert OUTPUT_FORMAT_JSON in call_log.claude_arguments
    assert AGENT_FLAG in call_log.claude_arguments
    parsed_payload = json.loads(capsys.readouterr().out)
    assert parsed_payload[RESULT_KEY_TIER_USED] == TIER_CLAUDE_HEADLESS


def test_default_role_maps_to_primary_agent_stem(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    call_log = _install_seams(
        monkeypatch,
        grok_outcome=_grok_ok(),
    )

    spawn_outcome = dispatcher.resolve_worker_spawn(
        role=DEFAULT_ROLE,
        prompt_file=prompt_file,
        working_directory=working_directory,
        timeout_seconds=DEFAULT_WORKER_TIMEOUT_SECONDS,
        is_claude_tier_enabled=False,
        run_state_directory=run_state_directory,
        max_turns=DEFAULT_SPAWN_MAX_TURNS,
    )

    assert spawn_outcome.is_ok is True
    assert call_log.grok_keyword_arguments is not None
    agent_name = call_log.grok_keyword_arguments["agent_name"]
    assert agent_name == EXPECTED_PRIMARY_AGENT_FOR_DEFAULT_ROLE
    assert agent_name != DEFAULT_ROLE
    assert agent_name != "bugteam"


def test_tier_three_argv_includes_agent_for_default_role(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    call_log = _install_seams(
        monkeypatch,
        grok_outcome=_grok_failure(CLASSIFICATION_AUTH_FAILURE),
        claude_outcome=_claude_served(),
        host_profile=HOST_PROFILE_THIRD_PARTY,
    )

    spawn_outcome = dispatcher.resolve_worker_spawn(
        role=DEFAULT_ROLE,
        prompt_file=prompt_file,
        working_directory=working_directory,
        timeout_seconds=DEFAULT_WORKER_TIMEOUT_SECONDS,
        is_claude_tier_enabled=False,
        run_state_directory=run_state_directory,
        max_turns=DEFAULT_SPAWN_MAX_TURNS,
    )

    assert spawn_outcome.tier_used == TIER_CLAUDE_HEADLESS
    assert call_log.claude_arguments is not None
    assert AGENT_FLAG in call_log.claude_arguments
    assert EXPECTED_PRIMARY_AGENT_FOR_DEFAULT_ROLE in call_log.claude_arguments
    agent_flag_index = call_log.claude_arguments.index(AGENT_FLAG)
    assert (
        call_log.claude_arguments[agent_flag_index + 1]
        == EXPECTED_PRIMARY_AGENT_FOR_DEFAULT_ROLE
    )


def test_large_prompt_stays_out_of_claude_argv(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    large_prompt_text = "x" * LARGE_PROMPT_CHARACTER_COUNT
    prompt_file.write_text(large_prompt_text, encoding="utf-8")
    call_log = _install_seams(
        monkeypatch,
        grok_outcome=_grok_failure(CLASSIFICATION_AUTH_FAILURE),
        claude_outcome=_claude_served(),
        host_profile=HOST_PROFILE_THIRD_PARTY,
    )

    spawn_outcome = dispatcher.resolve_worker_spawn(
        role=DEFAULT_ROLE,
        prompt_file=prompt_file,
        working_directory=working_directory,
        timeout_seconds=DEFAULT_WORKER_TIMEOUT_SECONDS,
        is_claude_tier_enabled=False,
        run_state_directory=run_state_directory,
        max_turns=DEFAULT_SPAWN_MAX_TURNS,
    )

    assert spawn_outcome.tier_used == TIER_CLAUDE_HEADLESS
    assert call_log.claude_arguments is not None
    assert large_prompt_text not in call_log.claude_arguments
    assert call_log.max_argv_element_length < WINDOWS_SAFE_ARGV_ELEMENT_CEILING
    assert call_log.is_stdin_from_prompt_file is True
    assert call_log.claude_stdin_path == prompt_file


def test_missing_prompt_file_returns_json_config_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    run_state_directory.mkdir()
    missing_prompt_file = tmp_path / "absent-prompt.txt"
    _install_seams(monkeypatch, grok_outcome=_grok_ok())

    exit_code = dispatcher.main(
        [
            CLI_ROLE_FLAG,
            FIXTURE_ROLE,
            PROMPT_FILE_FLAG,
            str(missing_prompt_file),
            CWD_FLAG,
            str(working_directory),
            CLI_TIMEOUT_FLAG,
            str(DEFAULT_WORKER_TIMEOUT_SECONDS),
            CLI_RUN_STATE_DIR_FLAG,
            str(run_state_directory),
        ]
    )

    assert exit_code == SPAWN_CONFIG_ERROR_EXIT_CODE
    captured = capsys.readouterr()
    assert captured.err == ""
    parsed_payload = json.loads(captured.out)
    assert parsed_payload[RESULT_KEY_OK] is False
    assert parsed_payload[RESULT_KEY_TIER_USED] is None
    assert parsed_payload[RESULT_KEY_OUTPUT] == REASON_PROMPT_FILE_MISSING
    assert parsed_payload[RESULT_KEY_RETURNCODE] == SPAWN_CONFIG_ERROR_EXIT_CODE


def _deny_prompt_open(
    monkeypatch: pytest.MonkeyPatch,
    prompt_file: Path,
    open_error: OSError,
) -> None:
    real_open = Path.open
    resolved_prompt = prompt_file.resolve()

    def open_with_denied_prompt(
        self: Path,
        *all_positionals: object,
        **all_keywords: object,
    ) -> object:
        if self.resolve() == resolved_prompt:
            raise open_error
        return real_open(self, *all_positionals, **all_keywords)

    monkeypatch.setattr(Path, "open", open_with_denied_prompt)


def _main_arguments_for_paths(
    *,
    prompt_file: Path,
    working_directory: Path,
    run_state_directory: Path,
) -> list[str]:
    return [
        CLI_ROLE_FLAG,
        FIXTURE_ROLE,
        PROMPT_FILE_FLAG,
        str(prompt_file),
        CWD_FLAG,
        str(working_directory),
        CLI_TIMEOUT_FLAG,
        str(DEFAULT_WORKER_TIMEOUT_SECONDS),
        CLI_RUN_STATE_DIR_FLAG,
        str(run_state_directory),
    ]


def test_unreadable_prompt_file_returns_json_config_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    _install_seams(
        monkeypatch,
        grok_outcome=_grok_failure(CLASSIFICATION_AUTH_FAILURE),
        claude_outcome=_claude_served(),
        host_profile=HOST_PROFILE_THIRD_PARTY,
    )
    _deny_prompt_open(
        monkeypatch,
        prompt_file,
        PermissionError("Access is denied"),
    )

    exit_code = dispatcher.main(
        _main_arguments_for_paths(
            prompt_file=prompt_file,
            working_directory=working_directory,
            run_state_directory=run_state_directory,
        )
    )

    assert exit_code == SPAWN_CONFIG_ERROR_EXIT_CODE
    captured = capsys.readouterr()
    assert captured.err == ""
    parsed_payload = json.loads(captured.out)
    assert parsed_payload[RESULT_KEY_OK] is False
    assert parsed_payload[RESULT_KEY_TIER_USED] is None
    assert parsed_payload[RESULT_KEY_OUTPUT] == REASON_PROMPT_FILE_MISSING
    assert parsed_payload[RESULT_KEY_RETURNCODE] == SPAWN_CONFIG_ERROR_EXIT_CODE
    assert "executable_not_found" not in json.dumps(parsed_payload)
    all_attempt_reasons = [
        each_attempt.get(ATTEMPT_KEY_REASON)
        for each_attempt in parsed_payload[RESULT_KEY_ATTEMPTS]
    ]
    assert REASON_PROMPT_FILE_MISSING in all_attempt_reasons
    assert "executable_not_found" not in all_attempt_reasons


def test_prompt_open_failure_not_classified_as_executable_not_found(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    monkeypatch.setattr(
        dispatcher,
        "spawn_preflight_runner",
        lambda **_keyword_arguments: _fallthrough_preflight(REASON_GROK_AUTH_FAILED),
    )
    monkeypatch.setattr(
        dispatcher,
        "spawn_host_profile_detector",
        lambda *all_positionals, **all_keywords: HOST_PROFILE_THIRD_PARTY,
    )
    monkeypatch.setattr(
        chain_runner,
        "load_chain",
        lambda _config_path: [chain_runner.ChainEntry(command="claude", extra_args=())],
    )
    monkeypatch.setattr(
        chain_runner,
        "chain_subprocess_runner",
        lambda *all_positionals, **all_keywords: subprocess.CompletedProcess(
            args=["claude"],
            returncode=0,
            stdout="{}",
            stderr="",
        ),
    )
    _deny_prompt_open(
        monkeypatch,
        prompt_file,
        FileNotFoundError(2, "No such file or directory", str(prompt_file)),
    )

    exit_code = dispatcher.main(
        _main_arguments_for_paths(
            prompt_file=prompt_file,
            working_directory=working_directory,
            run_state_directory=run_state_directory,
        )
    )

    assert exit_code == SPAWN_CONFIG_ERROR_EXIT_CODE
    captured = capsys.readouterr()
    assert captured.err == ""
    parsed_payload = json.loads(captured.out)
    assert parsed_payload[RESULT_KEY_OK] is False
    assert parsed_payload[RESULT_KEY_TIER_USED] is None
    assert parsed_payload[RESULT_KEY_OUTPUT] == REASON_PROMPT_FILE_MISSING
    assert parsed_payload[RESULT_KEY_RETURNCODE] == SPAWN_CONFIG_ERROR_EXIT_CODE
    serialized_payload = json.dumps(parsed_payload)
    assert "executable_not_found" not in serialized_payload
    all_attempt_reasons = [
        each_attempt.get(ATTEMPT_KEY_REASON)
        for each_attempt in parsed_payload[RESULT_KEY_ATTEMPTS]
    ]
    assert REASON_PROMPT_FILE_MISSING in all_attempt_reasons
    assert "executable_not_found" not in all_attempt_reasons


def test_headless_chain_runner_lock_serializes_distinct_cwds(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(FIXTURE_PROMPT_TEXT, encoding="utf-8")
    first_working_directory = tmp_path / "project-a"
    second_working_directory = tmp_path / "project-b"
    first_working_directory.mkdir()
    second_working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    run_state_directory.mkdir()
    call_log = _install_seams(
        monkeypatch,
        grok_outcome=_grok_failure(CLASSIFICATION_AUTH_FAILURE),
        claude_outcome=_claude_served(),
        host_profile=HOST_PROFILE_THIRD_PARTY,
    )
    all_errors: list[BaseException] = []
    barrier = threading.Barrier(2)

    def _run_with_working_directory(working_directory: Path) -> None:
        try:
            barrier.wait(timeout=5)
            dispatcher.resolve_worker_spawn(
                role=DEFAULT_ROLE,
                prompt_file=prompt_file,
                working_directory=working_directory,
                timeout_seconds=DEFAULT_WORKER_TIMEOUT_SECONDS,
                is_claude_tier_enabled=False,
                run_state_directory=run_state_directory,
                max_turns=DEFAULT_SPAWN_MAX_TURNS,
            )
        except (OSError, RuntimeError, ValueError, AssertionError) as raised_error:
            all_errors.append(raised_error)

    first_thread = threading.Thread(
        target=_run_with_working_directory, args=(first_working_directory,)
    )
    second_thread = threading.Thread(
        target=_run_with_working_directory, args=(second_working_directory,)
    )
    first_thread.start()
    second_thread.start()
    first_thread.join(timeout=10)
    second_thread.join(timeout=10)

    assert all_errors == []
    assert call_log.claude_calls == 2
    assert set(call_log.all_observed_working_directories) == {
        first_working_directory,
        second_working_directory,
    }
    assert chain_runner.chain_subprocess_runner is not None


def test_usage_limit_fallover_delivers_full_prompt_to_each_binary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file, working_directory, run_state_directory = _paths(tmp_path)
    monkeypatch.setattr(
        dispatcher,
        "spawn_preflight_runner",
        lambda **_keyword_arguments: _fallthrough_preflight(REASON_GROK_AUTH_FAILED),
    )
    monkeypatch.setattr(
        dispatcher,
        "spawn_host_profile_detector",
        lambda *all_positionals, **all_keywords: HOST_PROFILE_THIRD_PARTY,
    )
    monkeypatch.setattr(
        chain_runner,
        "load_chain",
        lambda _config_path: [
            chain_runner.ChainEntry(command="claude", extra_args=()),
            chain_runner.ChainEntry(command="claude-ev", extra_args=()),
        ],
    )
    prompt_text_by_command: dict[str, str] = {}

    def _reading_subprocess_runner(
        all_invocation_tokens: Sequence[str],
        *all_positionals: object,
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_positionals
        command_name = str(all_invocation_tokens[0])
        read_prompt = getattr(all_keywords.get("stdin"), "read", None)
        prompt_text_by_command[command_name] = read_prompt() if read_prompt else ""
        is_primary = command_name == "claude"
        return subprocess.CompletedProcess(
            args=list(all_invocation_tokens),
            returncode=(
                FIXTURE_FAILED_RETURNCODE if is_primary else SPAWN_SERVED_EXIT_CODE
            ),
            stdout="usage limit reached" if is_primary else FIXTURE_CLAUDE_STDOUT,
            stderr="",
        )

    monkeypatch.setattr(
        chain_runner, "chain_subprocess_runner", _reading_subprocess_runner
    )

    outcome = dispatcher.resolve_worker_spawn(
        role=DEFAULT_ROLE,
        prompt_file=prompt_file,
        working_directory=working_directory,
        timeout_seconds=DEFAULT_WORKER_TIMEOUT_SECONDS,
        is_claude_tier_enabled=False,
        run_state_directory=run_state_directory,
        max_turns=DEFAULT_SPAWN_MAX_TURNS,
    )

    assert prompt_text_by_command["claude"] == FIXTURE_PROMPT_TEXT
    assert prompt_text_by_command["claude-ev"] == FIXTURE_PROMPT_TEXT
    assert outcome.tier_used == TIER_CLAUDE_HEADLESS
    assert outcome.is_ok is True
