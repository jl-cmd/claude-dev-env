"""Behavioral tests for the headless codex review wrapper."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import run_codex_review as wrapper  # noqa: E402
from codex_review_scripts_constants.run_constants import (  # noqa: E402
    ALL_SHAPE_PROBE_REQUIRED_FLAGS,
    BASE_TARGET_FLAG,
    CODEX_BINARY_NAME,
    CODEX_HOME_ENV_VAR,
    COMMIT_TARGET_FLAG,
    CUSTOM_INSTRUCTIONS_PROMPT,
    DEFAULT_TIMEOUT_SECONDS,
    EXEC_SUBCOMMAND,
    HELP_FLAG,
    JSON_FLAG,
    JSONL_CAPTURE_FILENAME,
    MISSING_BINARY_EXIT_CODE,
    MODEL_FLAG,
    OUTCOME_CLASS_CODEX_DOWN,
    OUTCOME_CLASS_COMPLETED,
    REVIEW_SUBCOMMAND,
    SUBPROCESS_DECODE_EXIT_CODE,
    TIMEOUT_EXIT_CODE,
    UNCOMMITTED_TARGET_FLAG,
    UTF8_ENCODING,
    VERSION_FLAG,
)

HELP_TEXT_WITH_TARGETS = (
    "Usage: codex exec review [OPTIONS] [PROMPT]\n"
    "      --uncommitted\n"
    "      --base <BRANCH>\n"
    "      --commit <SHA>\n"
    "      --json\n"
)
VERSION_STDOUT = "codex-cli 0.144.3\n"
EXPECTED_BINARY_VERSION = "0.144.3"
AGENT_MESSAGE_BODY = "No issues found.\n\n```json\n[]\n```"
CARRIAGE_RETURN_LINE_ENDING = b"\r\n"
SUCCESS_JSONL = "\n".join(
    [
        json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
        json.dumps({"type": "turn.started"}),
        json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "agent_message",
                    "text": AGENT_MESSAGE_BODY,
                },
            }
        ),
        json.dumps(
            {
                "type": "turn.completed",
                "usage": {
                    "input_tokens": 10,
                    "output_tokens": 5,
                },
            }
        ),
    ]
) + "\n"


@pytest.fixture
def repository_directory(tmp_path: Path) -> Path:
    existing_repository_directory = tmp_path / "repo"
    existing_repository_directory.mkdir()
    return existing_repository_directory


@pytest.fixture
def run_state_directory(tmp_path: Path) -> Path:
    existing_run_state_directory = tmp_path / "run_state"
    existing_run_state_directory.mkdir()
    return existing_run_state_directory


class _SubprocessRecorder:
    def __init__(
        self,
        behavior_for_invocation: Callable[
            [list[str]], subprocess.CompletedProcess[str] | BaseException
        ],
    ) -> None:
        self.behavior_for_invocation = behavior_for_invocation
        self.all_invocations: list[list[str]] = []
        self.all_keyword_arguments: list[dict[str, object]] = []

    def __call__(
        self,
        invocation: list[str],
        **keyword_arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        self.all_invocations.append(list(invocation))
        self.all_keyword_arguments.append(keyword_arguments)
        behavior = self.behavior_for_invocation(list(invocation))
        if isinstance(behavior, BaseException):
            raise behavior
        return behavior


def _completed(
    all_arguments: list[str],
    returncode: int,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=all_arguments,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


def _is_version_probe(all_arguments: list[str]) -> bool:
    return all_arguments == [CODEX_BINARY_NAME, VERSION_FLAG]


def _is_shape_probe(all_arguments: list[str]) -> bool:
    return all_arguments == [
        CODEX_BINARY_NAME,
        EXEC_SUBCOMMAND,
        REVIEW_SUBCOMMAND,
        HELP_FLAG,
    ]


def _is_review_run(all_arguments: list[str]) -> bool:
    return (
        len(all_arguments) >= 4
        and all_arguments[0] == CODEX_BINARY_NAME
        and all_arguments[1] == EXEC_SUBCOMMAND
        and REVIEW_SUBCOMMAND in all_arguments
        and JSON_FLAG in all_arguments
        and HELP_FLAG not in all_arguments
        and VERSION_FLAG not in all_arguments
    )


def _install_recorder(
    monkeypatch: pytest.MonkeyPatch,
    behavior_for_invocation: Callable[
        [list[str]], subprocess.CompletedProcess[str] | BaseException
    ],
) -> _SubprocessRecorder:
    recorder = _SubprocessRecorder(behavior_for_invocation)
    monkeypatch.setattr(wrapper, "codex_subprocess_runner", recorder)
    monkeypatch.setattr(
        wrapper, "_resolve_codex_command_prefix", lambda: [CODEX_BINARY_NAME]
    )
    return recorder


def _healthy_probe_then_review(
    review_returncode: int = 0,
    review_stdout: str = SUCCESS_JSONL,
    review_stderr: str = "",
) -> Callable[[list[str]], subprocess.CompletedProcess[str] | BaseException]:
    def behavior(
        all_arguments: list[str],
    ) -> subprocess.CompletedProcess[str] | BaseException:
        if _is_version_probe(all_arguments):
            return _completed(all_arguments, 0, stdout=VERSION_STDOUT)
        if _is_shape_probe(all_arguments):
            return _completed(all_arguments, 0, stdout=HELP_TEXT_WITH_TARGETS)
        if _is_review_run(all_arguments):
            return _completed(
                all_arguments,
                review_returncode,
                stdout=review_stdout,
                stderr=review_stderr,
            )
        raise AssertionError(f"unexpected invocation: {all_arguments!r}")

    return behavior


def _healthy_probe_then_failing_shape(
    shape_stdout: str,
) -> Callable[[list[str]], subprocess.CompletedProcess[str] | BaseException]:
    def behavior(
        all_arguments: list[str],
    ) -> subprocess.CompletedProcess[str] | BaseException:
        if _is_version_probe(all_arguments):
            return _completed(all_arguments, 0, stdout=VERSION_STDOUT)
        if _is_shape_probe(all_arguments):
            return _completed(all_arguments, 0, stdout=shape_stdout)
        raise AssertionError("review must not run after a failed shape probe")

    return behavior


def _only_review_invocation(recorder: _SubprocessRecorder) -> list[str]:
    return next(
        each_invocation
        for each_invocation in recorder.all_invocations
        if _is_review_run(each_invocation)
    )


def test_argv_assembly_for_uncommitted_target(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    review_invocation = _only_review_invocation(recorder)
    assert review_invocation == [
        CODEX_BINARY_NAME,
        EXEC_SUBCOMMAND,
        REVIEW_SUBCOMMAND,
        JSON_FLAG,
        UNCOMMITTED_TARGET_FLAG,
    ]
    assert CUSTOM_INSTRUCTIONS_PROMPT not in review_invocation
    assert review_outcome.outcome_class == OUTCOME_CLASS_COMPLETED


def test_argv_assembly_for_base_branch_target(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())
    base_branch = "origin/main"

    wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        base_branch=base_branch,
    )

    review_invocation = _only_review_invocation(recorder)
    assert review_invocation == [
        CODEX_BINARY_NAME,
        EXEC_SUBCOMMAND,
        REVIEW_SUBCOMMAND,
        JSON_FLAG,
        BASE_TARGET_FLAG,
        base_branch,
    ]
    assert CUSTOM_INSTRUCTIONS_PROMPT not in review_invocation


def test_argv_assembly_for_commit_target(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())
    commit_sha = "abc123def456"

    wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        commit_sha=commit_sha,
    )

    review_invocation = _only_review_invocation(recorder)
    assert review_invocation == [
        CODEX_BINARY_NAME,
        EXEC_SUBCOMMAND,
        REVIEW_SUBCOMMAND,
        JSON_FLAG,
        COMMIT_TARGET_FLAG,
        commit_sha,
    ]
    assert CUSTOM_INSTRUCTIONS_PROMPT not in review_invocation


def test_argv_assembly_for_prompt_target(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_prompt_target=True,
    )

    review_invocation = _only_review_invocation(recorder)
    assert review_invocation == [
        CODEX_BINARY_NAME,
        EXEC_SUBCOMMAND,
        REVIEW_SUBCOMMAND,
        JSON_FLAG,
        CUSTOM_INSTRUCTIONS_PROMPT,
    ]
    assert UNCOMMITTED_TARGET_FLAG not in review_invocation
    assert BASE_TARGET_FLAG not in review_invocation
    assert COMMIT_TARGET_FLAG not in review_invocation
    assert review_outcome.outcome_class == OUTCOME_CLASS_COMPLETED


def test_shape_probe_missing_target_flags_returns_codex_down(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    recorder = _install_recorder(
        monkeypatch,
        _healthy_probe_then_failing_shape("Usage: codex exec review\n  --legacy-only\n"),
    )

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    assert review_outcome.outcome_class == OUTCOME_CLASS_CODEX_DOWN
    assert review_outcome.binary_version == EXPECTED_BINARY_VERSION
    assert review_outcome.agent_message == ""
    assert review_outcome.jsonl_path is None
    assert not any(
        _is_review_run(each_invocation)
        for each_invocation in recorder.all_invocations
    )


def test_shape_probe_lookalike_flags_do_not_match_required_tokens(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    lookalike_help_text = (
        "Usage: codex exec review [OPTIONS]\n"
        "      --baseline <BRANCH>\n"
        "      --commit-message <TEXT>\n"
        "      --uncommitted-only\n"
        "      --json-output\n"
    )
    recorder = _install_recorder(
        monkeypatch, _healthy_probe_then_failing_shape(lookalike_help_text)
    )

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    assert review_outcome.outcome_class == OUTCOME_CLASS_CODEX_DOWN
    assert review_outcome.exit_code == 0
    assert review_outcome.jsonl_path is None
    assert not any(
        _is_review_run(each_invocation)
        for each_invocation in recorder.all_invocations
    )
    for each_required_flag in ALL_SHAPE_PROBE_REQUIRED_FLAGS:
        assert each_required_flag in lookalike_help_text


def test_shape_probe_nonzero_help_returns_codex_down(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    def behavior(
        all_arguments: list[str],
    ) -> subprocess.CompletedProcess[str] | BaseException:
        if _is_version_probe(all_arguments):
            return _completed(all_arguments, 0, stdout=VERSION_STDOUT)
        if _is_shape_probe(all_arguments):
            return _completed(
                all_arguments,
                2,
                stderr="error: unrecognized subcommand 'review'\n",
            )
        raise AssertionError("review must not run after a failed shape probe")

    _install_recorder(monkeypatch, behavior)

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    assert review_outcome.outcome_class == OUTCOME_CLASS_CODEX_DOWN
    assert review_outcome.exit_code == 2


def test_missing_binary_returns_codex_down(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    def behavior(
        all_arguments: list[str],
    ) -> subprocess.CompletedProcess[str] | BaseException:
        raise FileNotFoundError(all_arguments[0])

    _install_recorder(monkeypatch, behavior)

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    assert review_outcome.outcome_class == OUTCOME_CLASS_CODEX_DOWN
    assert review_outcome.exit_code == MISSING_BINARY_EXIT_CODE
    assert review_outcome.jsonl_path is None


def test_jsonl_capture_and_agent_message_extraction(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    expected_jsonl_path = run_state_directory / JSONL_CAPTURE_FILENAME
    assert review_outcome.outcome_class == OUTCOME_CLASS_COMPLETED
    assert review_outcome.exit_code == 0
    assert review_outcome.jsonl_path == expected_jsonl_path
    assert expected_jsonl_path.read_text(encoding=UTF8_ENCODING) == SUCCESS_JSONL
    assert review_outcome.agent_message == AGENT_MESSAGE_BODY
    assert review_outcome.binary_version == EXPECTED_BINARY_VERSION
    review_keyword_arguments = next(
        each_keyword_arguments
        for each_invocation, each_keyword_arguments in zip(
            recorder.all_invocations,
            recorder.all_keyword_arguments,
            strict=True,
        )
        if _is_review_run(each_invocation)
    )
    assert review_keyword_arguments["cwd"] == str(repository_directory)
    assert review_keyword_arguments["timeout"] == DEFAULT_TIMEOUT_SECONDS
    assert review_keyword_arguments["capture_output"] is True
    assert review_keyword_arguments["text"] is True
    assert review_keyword_arguments["encoding"] == UTF8_ENCODING
    assert review_keyword_arguments["check"] is False


def test_jsonl_capture_preserves_stream_line_endings(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    _install_recorder(monkeypatch, _healthy_probe_then_review())

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    assert review_outcome.jsonl_path is not None
    captured_bytes = review_outcome.jsonl_path.read_bytes()
    assert CARRIAGE_RETURN_LINE_ENDING not in captured_bytes
    assert captured_bytes == SUCCESS_JSONL.encode(UTF8_ENCODING)


def test_unicode_decode_error_returns_codex_down(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    def behavior(
        all_arguments: list[str],
    ) -> subprocess.CompletedProcess[str] | BaseException:
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

    _install_recorder(monkeypatch, behavior)

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    assert review_outcome.outcome_class == OUTCOME_CLASS_CODEX_DOWN
    assert review_outcome.exit_code == SUBPROCESS_DECODE_EXIT_CODE
    assert review_outcome.jsonl_path is None


def test_timeout_returns_codex_down(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    def behavior(
        all_arguments: list[str],
    ) -> subprocess.CompletedProcess[str] | BaseException:
        if _is_version_probe(all_arguments):
            return _completed(all_arguments, 0, stdout=VERSION_STDOUT)
        if _is_shape_probe(all_arguments):
            return _completed(all_arguments, 0, stdout=HELP_TEXT_WITH_TARGETS)
        if _is_review_run(all_arguments):
            return subprocess.TimeoutExpired(cmd=all_arguments, timeout=1)
        raise AssertionError(f"unexpected invocation: {all_arguments!r}")

    _install_recorder(monkeypatch, behavior)

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
        timeout_seconds=1,
    )

    assert review_outcome.outcome_class == OUTCOME_CLASS_CODEX_DOWN
    assert review_outcome.exit_code == TIMEOUT_EXIT_CODE


def test_codex_home_env_is_passed_through_when_set(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    codex_home_directory = tmp_path / "codex_home"
    codex_home_directory.mkdir()
    monkeypatch.setenv(CODEX_HOME_ENV_VAR, str(codex_home_directory))
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())

    wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    for each_keyword_arguments in recorder.all_keyword_arguments:
        process_environment = each_keyword_arguments.get("env")
        assert process_environment is not None
        assert isinstance(process_environment, dict)
        assert process_environment[CODEX_HOME_ENV_VAR] == str(codex_home_directory)


def test_rejects_multiple_targets(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())

    with pytest.raises(ValueError):
        wrapper.run_codex_review(
            repository_directory=repository_directory,
            run_state_directory=run_state_directory,
            is_uncommitted=True,
            base_branch="main",
        )

    assert recorder.all_invocations == []


def test_rejects_missing_target(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())

    with pytest.raises(ValueError):
        wrapper.run_codex_review(
            repository_directory=repository_directory,
            run_state_directory=run_state_directory,
        )

    assert recorder.all_invocations == []


def test_shape_probe_missing_json_flag_returns_codex_down(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    help_without_json = (
        "Usage: codex exec review [OPTIONS]\n"
        "      --uncommitted\n"
        "      --base <BRANCH>\n"
        "      --commit <SHA>\n"
    )
    recorder = _install_recorder(
        monkeypatch, _healthy_probe_then_failing_shape(help_without_json)
    )

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    assert review_outcome.outcome_class == OUTCOME_CLASS_CODEX_DOWN
    assert review_outcome.jsonl_path is None
    assert not any(
        _is_review_run(each_invocation)
        for each_invocation in recorder.all_invocations
    )
    assert JSON_FLAG not in help_without_json
    assert JSON_FLAG in ALL_SHAPE_PROBE_REQUIRED_FLAGS


def test_missing_repository_directory_raises_value_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    run_state_directory: Path,
) -> None:
    missing_repository_directory = tmp_path / "missing-repo"
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())

    with pytest.raises(ValueError, match="repository_directory"):
        wrapper.run_codex_review(
            repository_directory=missing_repository_directory,
            run_state_directory=run_state_directory,
            is_uncommitted=True,
        )

    assert recorder.all_invocations == []


def test_missing_run_state_directory_raises_before_any_codex_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    repository_directory: Path,
) -> None:
    missing_run_state_directory = tmp_path / "missing-run-state"
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())

    with pytest.raises(ValueError, match="run_state_directory"):
        wrapper.run_codex_review(
            repository_directory=repository_directory,
            run_state_directory=missing_run_state_directory,
            is_uncommitted=True,
        )

    assert recorder.all_invocations == []


def test_custom_instructions_prompt_demands_finding_bullet_format() -> None:
    assert "- [P1]" in CUSTOM_INSTRUCTIONS_PROMPT
    assert "Review comment:" in CUSTOM_INSTRUCTIONS_PROMPT
    assert "fenced JSON" not in CUSTOM_INSTRUCTIONS_PROMPT
    assert "JSON array" not in CUSTOM_INSTRUCTIONS_PROMPT


def test_model_pin_assembles_model_flag_before_review_subcommand(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    model_pin = "gpt-5-codex"
    monkeypatch.setattr(wrapper, "CODEX_MODEL_PIN", model_pin)
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())

    wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    review_invocation = _only_review_invocation(recorder)
    model_flag_index = review_invocation.index(MODEL_FLAG)
    review_subcommand_index = review_invocation.index(REVIEW_SUBCOMMAND)
    assert review_invocation[model_flag_index : model_flag_index + 2] == [
        MODEL_FLAG,
        model_pin,
    ]
    assert model_flag_index < review_subcommand_index


def test_review_exit_1_config_error_classifies_codex_down(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    config_error_stderr = (
        "Error loading config.toml: unknown variant 'default', "
        "expected 'fast' or 'flex' in 'service_tier'\n"
    )
    recorder = _install_recorder(
        monkeypatch,
        _healthy_probe_then_review(
            review_returncode=1,
            review_stdout="",
            review_stderr=config_error_stderr,
        ),
    )

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    assert review_outcome.outcome_class == OUTCOME_CLASS_CODEX_DOWN
    assert review_outcome.exit_code == 1
    assert review_outcome.agent_message == config_error_stderr
    assert review_outcome.jsonl_path is not None
    assert review_outcome.jsonl_path.read_text(encoding=UTF8_ENCODING) == ""
    assert any(
        _is_review_run(each_invocation)
        for each_invocation in recorder.all_invocations
    )


def test_review_exit_2_argument_error_classifies_codex_down(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    argument_error_stderr = (
        "error: the argument '--uncommitted' cannot be used with '[PROMPT]'\n"
        "Usage: codex exec review --json --uncommitted [PROMPT]\n"
    )
    recorder = _install_recorder(
        monkeypatch,
        _healthy_probe_then_review(
            review_returncode=2,
            review_stdout="",
            review_stderr=argument_error_stderr,
        ),
    )

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    assert review_outcome.outcome_class == OUTCOME_CLASS_CODEX_DOWN
    assert review_outcome.exit_code == 2
    assert review_outcome.agent_message == argument_error_stderr
    assert review_outcome.jsonl_path is not None
    assert review_outcome.jsonl_path.read_text(encoding=UTF8_ENCODING) == ""
    assert any(
        _is_review_run(each_invocation)
        for each_invocation in recorder.all_invocations
    )


def test_review_exit_0_stays_completed(
    monkeypatch: pytest.MonkeyPatch,
    repository_directory: Path,
    run_state_directory: Path,
) -> None:
    _install_recorder(
        monkeypatch,
        _healthy_probe_then_review(review_returncode=0, review_stdout=SUCCESS_JSONL),
    )

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    assert review_outcome.outcome_class == OUTCOME_CLASS_COMPLETED
    assert review_outcome.exit_code == 0
    assert review_outcome.agent_message == AGENT_MESSAGE_BODY


def test_resolve_prefix_wraps_windows_shim(monkeypatch: pytest.MonkeyPatch) -> None:
    shim_path = r"C:\\Users\\dev\\AppData\\Roaming\\npm\\codex.CMD"
    monkeypatch.setattr(wrapper.shutil, "which", lambda _name: shim_path)
    monkeypatch.setattr(wrapper.os, "name", "nt")

    assert wrapper._resolve_codex_command_prefix() == ["cmd", "/c", shim_path]


def test_resolve_prefix_uses_resolved_path_on_posix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolved_path = "/usr/local/bin/codex"
    monkeypatch.setattr(wrapper.shutil, "which", lambda _name: resolved_path)
    monkeypatch.setattr(wrapper.os, "name", "posix")

    assert wrapper._resolve_codex_command_prefix() == [resolved_path]


def test_resolve_prefix_falls_back_to_bare_name_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(wrapper.shutil, "which", lambda _name: None)

    assert wrapper._resolve_codex_command_prefix() == [CODEX_BINARY_NAME]


def _is_process_running(process_identifier: int) -> bool:
    if sys.platform == "win32":
        process_listing = subprocess.run(
            ["tasklist", "/FI", f"PID eq {process_identifier}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return str(process_identifier) in process_listing.stdout
    liveness_probe = subprocess.run(
        ["kill", "-0", str(process_identifier)],
        capture_output=True,
        check=False,
    )
    return liveness_probe.returncode == 0


def _wait_until_process_stops(
    process_identifier: int, deadline_seconds: float
) -> bool:
    poll_interval_seconds = 0.5
    deadline = time.monotonic() + deadline_seconds
    while time.monotonic() < deadline:
        if not _is_process_running(process_identifier):
            return True
        time.sleep(poll_interval_seconds)
    return not _is_process_running(process_identifier)


def _grandchild_spawn_source(grandchild_pid_path: Path, lifetime_seconds: int) -> str:
    """Python source that spawns a grandchild and records its PID before sleeping.

    ::

        Popen(grandchild) -> write grandchild.pid -> sleep    grandchild holds pipe
    """
    return (
        "import subprocess, sys, time, pathlib; "
        "grandchild = subprocess.Popen([sys.executable, '-c', "
        f"'import time; time.sleep({lifetime_seconds})']); "
        f"pathlib.Path(r'{grandchild_pid_path}').write_text(str(grandchild.pid)); "
        f"time.sleep({lifetime_seconds})"
    )


def test_run_command_kills_grandchild_tree_on_timeout_without_hanging(
    tmp_path: Path,
) -> None:
    """The timeout kills the grandchild that inherited the capture pipe.

    ::

        middle -> grandchild, timeout at 2s    ok: grandchild PID stops running
        kill only the middle child             flag: grandchild lives on 30s

    A direct-child-only kill leaves the grandchild alive on POSIX, so asserting
    the recorded grandchild PID stops running guards the regression in CI.
    """
    grandchild_lifetime_seconds = 30
    review_timeout_seconds = 2
    wall_clock_ceiling_seconds = 20
    grandchild_pid_path = tmp_path / "grandchild.pid"
    grandchild_source = _grandchild_spawn_source(
        grandchild_pid_path, grandchild_lifetime_seconds
    )
    start_time = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        wrapper._run_command(
            [sys.executable, "-c", grandchild_source],
            working_directory=tmp_path,
            timeout_seconds=review_timeout_seconds,
        )
    assert time.monotonic() - start_time < wall_clock_ceiling_seconds
    grandchild_identifier = int(grandchild_pid_path.read_text())
    assert _wait_until_process_stops(grandchild_identifier, wall_clock_ceiling_seconds)


def test_windows_process_tree_kill_builds_taskkill_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The Windows kill path issues taskkill /T /F /PID for the given process id."""
    target_process_identifier = 4242
    recorded_argv: list[list[str]] = []

    def record_argv(all_arguments: list[str], **_keywords: object) -> None:
        recorded_argv.append(all_arguments)

    monkeypatch.setattr(wrapper.subprocess, "run", record_argv)
    wrapper._kill_windows_process_tree(target_process_identifier)

    assert recorded_argv == [
        ["taskkill", "/T", "/F", "/PID", str(target_process_identifier)]
    ]


def test_run_command_surfaces_timeout_when_tree_kill_is_noop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """An incomplete tree kill still raises TimeoutExpired inside a wall ceiling.

    ::

        terminate is a no-op, child sleeps 60s    ok: TimeoutExpired < 25s wall
        no post-kill drain / fallback kill        flag: hang past ceiling on wait

    The post-kill grace drain and direct-child kill fallback keep the caller
    from blocking forever when taskkill/killpg leave the direct child alive.
    """
    review_timeout_seconds = 1
    wall_clock_ceiling_seconds = 25
    sleep_source = "import time; time.sleep(60)"

    def leave_process_alive(_review_process: object) -> None:
        return None

    monkeypatch.setattr(wrapper, "_terminate_process_tree", leave_process_alive)
    start_time = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        wrapper._run_command(
            [sys.executable, "-c", sleep_source],
            working_directory=tmp_path,
            timeout_seconds=review_timeout_seconds,
        )
    assert time.monotonic() - start_time < wall_clock_ceiling_seconds
