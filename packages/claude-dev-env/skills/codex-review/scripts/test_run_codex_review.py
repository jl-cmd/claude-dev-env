"""Behavioral tests for the headless codex review wrapper."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import run_codex_review as wrapper  # noqa: E402
from codex_review_scripts_constants.classifier_constants import (  # noqa: E402
    FAILURE_CLASS_CONFIG_ERROR,
    FAILURE_CLASS_UNKNOWN,
)
from codex_review_scripts_constants.run_constants import (  # noqa: E402
    BASE_TARGET_FLAG,
    CODEX_BINARY_NAME,
    CODEX_HOME_ENV_VAR,
    COMMIT_TARGET_FLAG,
    CUSTOM_INSTRUCTIONS_PROMPT,
    DECODE_ERROR_EXIT_CODE,
    DEFAULT_TIMEOUT_SECONDS,
    EXEC_SUBCOMMAND,
    HELP_FLAG,
    JSON_FLAG,
    JSONL_CAPTURE_FILENAME,
    MISSING_BINARY_EXIT_CODE,
    OUTCOME_CLASS_CODEX_DOWN,
    OUTCOME_CLASS_COMPLETED,
    REVIEW_SUBCOMMAND,
    SUBPROCESS_TEXT_ERRORS,
    TIMEOUT_EXIT_CODE,
    UNCOMMITTED_TARGET_FLAG,
    UNSUPPORTED_SHAPE_EXIT_CODE,
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
AGENT_MESSAGE_BODY = (
    "No issues found.\n\n```json\n[]\n```"
)
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


def test_argv_assembly_for_uncommitted_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    review_invocation = next(
        each_invocation
        for each_invocation in recorder.all_invocations
        if _is_review_run(each_invocation)
    )
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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())
    base_branch = "origin/main"

    wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        base_branch=base_branch,
    )

    review_invocation = next(
        each_invocation
        for each_invocation in recorder.all_invocations
        if _is_review_run(each_invocation)
    )
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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())
    commit_sha = "abc123def456"

    wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        commit_sha=commit_sha,
    )

    review_invocation = next(
        each_invocation
        for each_invocation in recorder.all_invocations
        if _is_review_run(each_invocation)
    )
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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_prompt_target=True,
    )

    review_invocation = next(
        each_invocation
        for each_invocation in recorder.all_invocations
        if _is_review_run(each_invocation)
    )
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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()

    def behavior(
        all_arguments: list[str],
    ) -> subprocess.CompletedProcess[str] | BaseException:
        if _is_version_probe(all_arguments):
            return _completed(all_arguments, 0, stdout=VERSION_STDOUT)
        if _is_shape_probe(all_arguments):
            return _completed(
                all_arguments,
                0,
                stdout="Usage: codex exec review\n  --legacy-only\n",
            )
        raise AssertionError("review must not run after a failed shape probe")

    recorder = _install_recorder(monkeypatch, behavior)

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    assert review_outcome.outcome_class == OUTCOME_CLASS_CODEX_DOWN
    assert review_outcome.exit_code == UNSUPPORTED_SHAPE_EXIT_CODE
    assert review_outcome.detail_class == FAILURE_CLASS_UNKNOWN
    assert review_outcome.binary_version == "0.144.3"
    assert review_outcome.agent_message == ""
    assert review_outcome.jsonl_path is None
    assert not any(
        _is_review_run(each_invocation)
        for each_invocation in recorder.all_invocations
    )


def test_shape_probe_nonzero_help_returns_codex_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()

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
    assert review_outcome.outcome_class != OUTCOME_CLASS_COMPLETED


def test_missing_binary_returns_codex_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()

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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()
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
    assert expected_jsonl_path.read_text(encoding="utf-8") == SUCCESS_JSONL
    assert review_outcome.agent_message == AGENT_MESSAGE_BODY
    assert review_outcome.binary_version == "0.144.3"
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
    assert review_keyword_arguments["errors"] == SUBPROCESS_TEXT_ERRORS
    assert review_keyword_arguments["check"] is False


def test_unicode_decode_error_returns_codex_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()

    def behavior(
        all_arguments: list[str],
    ) -> subprocess.CompletedProcess[str] | BaseException:
        if _is_version_probe(all_arguments):
            return _completed(all_arguments, 0, stdout=VERSION_STDOUT)
        if _is_shape_probe(all_arguments):
            return _completed(all_arguments, 0, stdout=HELP_TEXT_WITH_TARGETS)
        if _is_review_run(all_arguments):
            return UnicodeDecodeError(
                "utf-8",
                b"\xff",
                0,
                1,
                "invalid start byte",
            )
        raise AssertionError(f"unexpected invocation: {all_arguments!r}")

    _install_recorder(monkeypatch, behavior)

    review_outcome = wrapper.run_codex_review(
        repository_directory=repository_directory,
        run_state_directory=run_state_directory,
        is_uncommitted=True,
    )

    assert review_outcome.outcome_class == OUTCOME_CLASS_CODEX_DOWN
    assert review_outcome.exit_code == DECODE_ERROR_EXIT_CODE
    assert review_outcome.jsonl_path is None


def test_timeout_returns_codex_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()

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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()
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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()
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
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()
    recorder = _install_recorder(monkeypatch, _healthy_probe_then_review())

    with pytest.raises(ValueError):
        wrapper.run_codex_review(
            repository_directory=repository_directory,
            run_state_directory=run_state_directory,
        )

    assert recorder.all_invocations == []


def test_review_exit_1_config_error_classifies_codex_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()
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
    assert review_outcome.detail_class == FAILURE_CLASS_CONFIG_ERROR
    assert review_outcome.exit_code == 1
    assert review_outcome.agent_message == config_error_stderr
    assert review_outcome.jsonl_path is not None
    assert review_outcome.jsonl_path.read_text(encoding="utf-8") == ""
    assert any(
        _is_review_run(each_invocation)
        for each_invocation in recorder.all_invocations
    )


def test_review_exit_2_argument_error_classifies_codex_down(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()
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
    assert review_outcome.jsonl_path.read_text(encoding="utf-8") == ""
    assert any(
        _is_review_run(each_invocation)
        for each_invocation in recorder.all_invocations
    )


def test_review_exit_0_stays_completed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repository_directory = tmp_path / "repo"
    repository_directory.mkdir()
    run_state_directory = tmp_path / "run_state"
    run_state_directory.mkdir()
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
