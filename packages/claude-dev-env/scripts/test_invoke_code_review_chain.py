"""Chain-invocation argv assembly, empty stdin, working directory, and retry."""

from __future__ import annotations

from pathlib import Path

import pytest

import invoke_code_review as invoker
from _code_review_test_support import (
    FIXTURE_CHAIN_RETURNCODE,
    FIXTURE_CHAIN_STDOUT,
    FIXTURE_FAILED_RETURNCODE,
    FIXTURE_SERVED_COMMAND,
    FIXTURE_SESSION_OPUS,
    FIXTURE_SESSION_SONNET,
    HOST_PROFILE_THIRD_PARTY,
    claude_served,
    init_git_repository,
    install_seams,
    run_review,
)
from claude_chain_runner import ChainAttempt, ChainInvocationOutcome
from dev_env_scripts_constants.code_review_constants import (
    CODE_REVIEW_MODEL_ALIAS,
    DEFAULT_CODE_REVIEW_EFFORT,
    PERMISSION_MODE_BYPASS,
    PERMISSION_MODE_FLAG,
)
from dev_env_scripts_constants.grok_worker_constants import (
    MODEL_FLAG,
    OUTPUT_FORMAT_FLAG,
    OUTPUT_FORMAT_JSON,
    SINGLE_TURN_FLAG,
)

SERVED_ATTEMPT_STATUS = "served"
UNRELATED_FAILURE_STDERR = "Error: the branch has no commits to review"
MEASURED_ROOT_CONTAINER_REJECTION_STDERR = (
    "--dangerously-skip-permissions cannot be used with root/sudo privileges "
    "for security reasons"
)
"""Verbatim stderr a container running as root emits for the bypass mode.

Copied from a live spawn, character for character, and deliberately not built
from the signature list: a text derived from that list agrees with it whatever
it holds, so it can never catch a signature that misses the host's real wording.
This text names the internal flag the mode maps to and carries neither the flag
the invoker sends nor the mode value.
"""
FIRST_SPAWN_INDEX = 0
SECOND_SPAWN_INDEX = 1
SINGLE_SPAWN_COUNT = 1
RETRIED_SPAWN_COUNT = 2


FLAG_NAMED_REJECTION_STDERR = (
    "Error: --permission-mode is not supported in this environment"
)
"""Stderr from a host that refuses the mode by naming the flag it was handed.

Hard-coded for the same reason as the root-container wording above: a text
built from the signature list agrees with that list whatever it holds, so it
can never catch a list that misses what a host really prints.
"""


def _chain_failure(stderr_text: str) -> ChainInvocationOutcome:
    """Build a served chain outcome that exited non-zero with *stderr_text*."""
    return ChainInvocationOutcome(
        served_command=FIXTURE_SERVED_COMMAND,
        returncode=FIXTURE_FAILED_RETURNCODE,
        stdout="",
        stderr=stderr_text,
        attempts=(
            ChainAttempt(command=FIXTURE_SERVED_COMMAND, status=SERVED_ATTEMPT_STATUS),
        ),
    )


def _chain_success() -> ChainInvocationOutcome:
    """Build a served chain outcome that exited clean."""
    return ChainInvocationOutcome(
        served_command=FIXTURE_SERVED_COMMAND,
        returncode=FIXTURE_CHAIN_RETURNCODE,
        stdout=FIXTURE_CHAIN_STDOUT,
        stderr="",
        attempts=(
            ChainAttempt(command=FIXTURE_SERVED_COMMAND, status=SERVED_ATTEMPT_STATUS),
        ),
    )


class _RecordingClaudeRunner:
    """Chain-runner stand-in that records argv and replays queued outcomes.

    ::

        queued = [rejected, clean]
        spawn 1 -> rejected   argv carries --permission-bypass
        spawn 2 -> clean      argv carries no permission-mode pair

    The last queued outcome repeats once the queue drains, so a test expecting
    one spawn still gets a defined answer if an unwanted retry fires.
    """

    def __init__(self, all_queued_outcomes: list[ChainInvocationOutcome]) -> None:
        self.all_queued_outcomes = all_queued_outcomes
        self.all_recorded_arguments: list[list[str]] = []

    def __call__(
        self, all_claude_arguments: list[str], *, timeout_seconds: int
    ) -> ChainInvocationOutcome:
        del timeout_seconds
        self.all_recorded_arguments.append(list(all_claude_arguments))
        last_queued_index = len(self.all_queued_outcomes) - 1
        spawn_index = len(self.all_recorded_arguments) - 1
        return self.all_queued_outcomes[min(spawn_index, last_queued_index)]


def _install_recording_runner(
    monkeypatch: pytest.MonkeyPatch,
    working_directory: Path,
    all_queued_outcomes: list[ChainInvocationOutcome],
) -> _RecordingClaudeRunner:
    """Seat a recording chain runner behind the third-party host seams."""
    install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=claude_served(),
        working_directory=working_directory,
    )
    recording_runner = _RecordingClaudeRunner(all_queued_outcomes)
    monkeypatch.setattr(invoker, "review_claude_runner", recording_runner)
    return recording_runner


def test_chain_retries_without_permission_mode_when_host_rejects_it(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    recording_runner = _install_recording_runner(
        monkeypatch,
        working_directory,
        [_chain_failure(FLAG_NAMED_REJECTION_STDERR), _chain_success()],
    )

    review_outcome = run_review(working_directory, session_model=FIXTURE_SESSION_SONNET)

    assert len(recording_runner.all_recorded_arguments) == RETRIED_SPAWN_COUNT
    first_spawn_arguments = recording_runner.all_recorded_arguments[FIRST_SPAWN_INDEX]
    second_spawn_arguments = recording_runner.all_recorded_arguments[SECOND_SPAWN_INDEX]
    assert PERMISSION_MODE_FLAG in first_spawn_arguments
    assert PERMISSION_MODE_BYPASS in first_spawn_arguments
    assert PERMISSION_MODE_FLAG not in second_spawn_arguments
    assert PERMISSION_MODE_BYPASS not in second_spawn_arguments
    assert review_outcome.returncode == FIXTURE_CHAIN_RETURNCODE
    assert review_outcome.served_command == FIXTURE_SERVED_COMMAND
    assert invoker.is_successful_code_review(review_outcome) is True


def test_chain_retries_for_the_measured_root_container_rejection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    recording_runner = _install_recording_runner(
        monkeypatch,
        working_directory,
        [
            _chain_failure(MEASURED_ROOT_CONTAINER_REJECTION_STDERR),
            _chain_success(),
        ],
    )

    review_outcome = run_review(working_directory, session_model=FIXTURE_SESSION_SONNET)

    assert len(recording_runner.all_recorded_arguments) == RETRIED_SPAWN_COUNT
    second_spawn_arguments = recording_runner.all_recorded_arguments[SECOND_SPAWN_INDEX]
    assert PERMISSION_MODE_FLAG not in second_spawn_arguments
    assert PERMISSION_MODE_BYPASS not in second_spawn_arguments
    assert invoker.is_successful_code_review(review_outcome) is True


def test_chain_keeps_permission_mode_when_failure_is_unrelated(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    recording_runner = _install_recording_runner(
        monkeypatch,
        working_directory,
        [_chain_failure(UNRELATED_FAILURE_STDERR), _chain_success()],
    )

    review_outcome = run_review(working_directory, session_model=FIXTURE_SESSION_SONNET)

    assert len(recording_runner.all_recorded_arguments) == SINGLE_SPAWN_COUNT
    assert PERMISSION_MODE_FLAG in recording_runner.all_recorded_arguments[
        FIRST_SPAWN_INDEX
    ]
    assert review_outcome.returncode == FIXTURE_FAILED_RETURNCODE
    assert invoker.is_successful_code_review(review_outcome) is False


def test_chain_argv_assembly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    call_log = install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=claude_served(),
        working_directory=working_directory,
    )

    run_review(working_directory, session_model=FIXTURE_SESSION_SONNET)

    assert call_log.claude_arguments == [
        SINGLE_TURN_FLAG,
        invoker.build_code_review_prompt(DEFAULT_CODE_REVIEW_EFFORT),
        MODEL_FLAG,
        CODE_REVIEW_MODEL_ALIAS,
        OUTPUT_FORMAT_FLAG,
        OUTPUT_FORMAT_JSON,
        PERMISSION_MODE_FLAG,
        PERMISSION_MODE_BYPASS,
    ]


def test_chain_redirects_empty_stdin_and_sets_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = init_git_repository(tmp_path / "repo")
    call_log = install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=claude_served(),
        working_directory=working_directory,
    )

    run_review(working_directory, session_model=FIXTURE_SESSION_OPUS)

    assert call_log.is_stdin_empty is True
    assert call_log.claude_working_directory == working_directory
