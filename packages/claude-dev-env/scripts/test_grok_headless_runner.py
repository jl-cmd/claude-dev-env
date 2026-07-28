"""Behavioral tests for the headless grok worker runner.

Classification fixtures use phrasing observed against grok binary version
0.2.99 (b1b49ccb71) [stable] — usage-limit and auth-failure text shapes that
include the signature substrings the constants module lists.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import grok_headless_runner as runner  # noqa: E402
from dev_env_scripts_constants.grok_worker_constants import (  # noqa: E402
    AGENT_FLAG,
    ALWAYS_APPROVE_FLAG,
    CLASSIFICATION_AUTH_FAILURE,
    CLASSIFICATION_ERROR,
    CLASSIFICATION_OK,
    CLASSIFICATION_TIMEOUT,
    CLASSIFICATION_USAGE_LIMIT,
    CWD_FLAG,
    GROK_BINARY_NAME,
    GROK_BINARY_NOT_FOUND_STDERR,
    KILL_GRACE_TIMEOUT_SECONDS,
    LAUNCH_FAILURE_RETURN_CODE,
    LAUNCH_FAILURE_STDERR_PREFIX,
    LEADER_SOCKET_FILENAME_PREFIX,
    LEADER_SOCKET_FILENAME_SUFFIX,
    LEADER_SOCKET_FLAG,
    MAX_TURNS_FLAG,
    MIN_WORKER_TIMEOUT_SECONDS,
    MISSING_BINARY_RETURN_CODE,
    OUTPUT_FORMAT_FLAG,
    OUTPUT_FORMAT_JSON,
    PROCESS_TREE_KILL_TIMEOUT_SECONDS,
    PROMPT_FILE_FLAG,
    TIMEOUT_RETURN_CODE,
    UTF8_DECODE_ERRORS,
    UTF8_ENCODING,
    WINDOWS_OS_NAME,
    WINDOWS_TASKKILL_COMMAND,
    WINDOWS_TASKKILL_FORCE_FLAG,
    WINDOWS_TASKKILL_PID_FLAG,
    WINDOWS_TASKKILL_TREE_FLAG,
)

FIXTURE_GROK_BINARY_VERSION = "0.2.99 (b1b49ccb71) [stable]"

FIXTURE_USAGE_LIMIT_STDERR = (
    f"grok {FIXTURE_GROK_BINARY_VERSION}: Error: rate limit exceeded "
    "(HTTP 429): quota exceeded, insufficient credit for this request"
)

FIXTURE_AUTH_FAILURE_STDERR = (
    f"grok {FIXTURE_GROK_BINARY_VERSION}: Error: unauthorized "
    "(HTTP 401): invalid key — authentication failed"
)

FIXTURE_GENERIC_FAILURE_STDERR = (
    f"grok {FIXTURE_GROK_BINARY_VERSION}: Error: internal failure"
)

FIXTURE_TURN_CAP_CANCELLED_STDERR = (
    f"grok {FIXTURE_GROK_BINARY_VERSION}: run ended with stopReason Cancelled "
    "after the turn cap was reached"
)

FIXTURE_MULTI_TURN_REPORT = '{"turns_used":16,"status":"done"}'

DEFAULT_TIMEOUT_SECONDS = 30
TINY_TURN_CAP = 8
FAKE_PROCESS_IDENTIFIER = 424242
TINY_TIMEOUT_SECONDS = 1
NON_POSITIVE_TIMEOUT_SECONDS = 0
GRANDCHILD_SETTLE_SECONDS = 1.0
GRANDCHILD_OBSERVATION_SECONDS = 2.0

GRANDCHILD_HEARTBEAT_SOURCE = (
    "import sys, time\n"
    "heartbeat_path = sys.argv[1]\n"
    "for each_beat in range(600):\n"
    "    with open(heartbeat_path, 'a', encoding='utf-8') as heartbeat_handle:\n"
    "        heartbeat_handle.write('beat\\n')\n"
    "    time.sleep(0.1)\n"
)

PARENT_SPAWNS_GRANDCHILD_SOURCE = (
    "import subprocess, sys, time\n"
    "subprocess.Popen([sys.executable, '-c', sys.argv[1], sys.argv[2]])\n"
    "time.sleep(600)\n"
)


class _FakeProcess:
    def __init__(
        self,
        *,
        returncode: int,
        stdout: str = "",
        stderr: str = "",
        should_timeout: bool = False,
        returncode_after_kill: int | None = None,
    ) -> None:
        self.returncode = returncode
        self.pid = FAKE_PROCESS_IDENTIFIER
        self._stdout = stdout
        self._stderr = stderr
        self._should_timeout = should_timeout
        self._returncode_after_kill = returncode_after_kill
        self.was_killed = False
        self.communicate_calls = 0
        self.last_communicate_timeout: float | None = None

    def communicate(self, timeout: float | None = None) -> tuple[str, str]:
        self.communicate_calls += 1
        self.last_communicate_timeout = timeout
        if self._should_timeout and not self.was_killed:
            raise subprocess.TimeoutExpired(
                cmd=[GROK_BINARY_NAME], timeout=timeout or 0
            )
        return self._stdout, self._stderr

    def poll(self) -> int | None:
        if not self.was_killed:
            return None
        return self.returncode

    def kill(self) -> None:
        self.was_killed = True
        if self._returncode_after_kill is not None:
            self.returncode = self._returncode_after_kill
            return
        self.returncode = -9


class _TreeKillRecorder:
    """Stands in for ``subprocess.run`` so no real taskkill leaves the test."""

    def __init__(self) -> None:
        self.all_invocations: list[list[str]] = []
        self.all_keyword_arguments: list[dict[str, object]] = []

    def __call__(
        self, invocation: list[str], **keyword_arguments: object
    ) -> subprocess.CompletedProcess[str]:
        self.all_invocations.append(list(invocation))
        self.all_keyword_arguments.append(dict(keyword_arguments))
        return subprocess.CompletedProcess(args=invocation, returncode=0)


class _TurnCapSensitiveLauncher:
    """Fake grok: cancels when argv carries a turn cap, completes without one."""

    def __init__(self) -> None:
        self.all_invocations: list[list[str]] = []

    def __call__(
        self, invocation: list[str], **keyword_arguments: object
    ) -> _FakeProcess:
        del keyword_arguments
        self.all_invocations.append(list(invocation))
        if MAX_TURNS_FLAG in invocation:
            return _FakeProcess(
                returncode=1, stderr=FIXTURE_TURN_CAP_CANCELLED_STDERR
            )
        return _FakeProcess(returncode=0, stdout=FIXTURE_MULTI_TURN_REPORT)


class _PopenRecorder:
    def __init__(self, all_processes: list[_FakeProcess]) -> None:
        self.all_processes = list(all_processes)
        self.invocations: list[list[str]] = []
        self.all_keyword_arguments: list[dict[str, object]] = []

    def __call__(
        self,
        invocation: list[str],
        **keyword_arguments: object,
    ) -> _FakeProcess:
        self.invocations.append(list(invocation))
        self.all_keyword_arguments.append(dict(keyword_arguments))
        if not self.all_processes:
            raise AssertionError(f"unexpected invocation: {invocation}")
        return self.all_processes.pop(0)


def _run_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fake_process: _FakeProcess,
    *,
    agent_name: str | None = None,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    should_install_tree_kill_recorder: bool = True,
) -> tuple[runner.GrokRunnerOutcome, _PopenRecorder, Path, Path, Path]:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the work", encoding="utf-8")
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    run_state_directory.mkdir()
    recorder = _PopenRecorder([fake_process])
    monkeypatch.setattr(runner, "runner_popen", recorder)
    if should_install_tree_kill_recorder:
        monkeypatch.setattr(runner, "runner_subprocess_run", _TreeKillRecorder())
    outcome = runner.run_headless_worker(
        prompt_file=prompt_file,
        working_directory=working_directory,
        run_state_directory=run_state_directory,
        timeout_seconds=timeout_seconds,
        agent_name=agent_name,
    )
    return outcome, recorder, prompt_file, working_directory, run_state_directory


def test_argv_assembly_includes_required_flags(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_process = _FakeProcess(returncode=0, stdout='{"ok":true}')
    outcome, recorder, prompt_file, working_directory, run_state_directory = _run_once(
        monkeypatch, tmp_path, fake_process
    )

    assert outcome.is_ok is True
    assert len(recorder.invocations) == 1
    invocation = recorder.invocations[0]
    assert invocation[0] == GROK_BINARY_NAME
    assert PROMPT_FILE_FLAG in invocation
    assert str(prompt_file) in invocation
    assert CWD_FLAG in invocation
    assert str(working_directory) in invocation
    assert OUTPUT_FORMAT_FLAG in invocation
    assert OUTPUT_FORMAT_JSON in invocation
    assert ALWAYS_APPROVE_FLAG in invocation
    assert MAX_TURNS_FLAG not in invocation
    assert LEADER_SOCKET_FLAG in invocation
    leader_socket_path = Path(invocation[invocation.index(LEADER_SOCKET_FLAG) + 1])
    assert leader_socket_path.parent == run_state_directory
    assert leader_socket_path.name.startswith(LEADER_SOCKET_FILENAME_PREFIX)
    assert leader_socket_path.name.endswith(LEADER_SOCKET_FILENAME_SUFFIX)
    assert AGENT_FLAG not in invocation


def test_argv_includes_agent_when_named(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_process = _FakeProcess(returncode=0, stdout='{"ok":true}')
    agent_name = "code-quality-agent"
    outcome, recorder, _, _, _ = _run_once(
        monkeypatch, tmp_path, fake_process, agent_name=agent_name
    )

    assert outcome.is_ok is True
    invocation = recorder.invocations[0]
    assert AGENT_FLAG in invocation
    assert agent_name in invocation


def test_unique_leader_socket_path_per_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the work", encoding="utf-8")
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    run_state_directory.mkdir()
    first_process = _FakeProcess(returncode=0, stdout="first")
    second_process = _FakeProcess(returncode=0, stdout="second")
    recorder = _PopenRecorder([first_process, second_process])
    monkeypatch.setattr(runner, "runner_popen", recorder)

    runner.run_headless_worker(
        prompt_file=prompt_file,
        working_directory=working_directory,
        run_state_directory=run_state_directory,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )
    runner.run_headless_worker(
        prompt_file=prompt_file,
        working_directory=working_directory,
        run_state_directory=run_state_directory,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )

    first_socket = Path(
        recorder.invocations[0][recorder.invocations[0].index(LEADER_SOCKET_FLAG) + 1]
    )
    second_socket = Path(
        recorder.invocations[1][recorder.invocations[1].index(LEADER_SOCKET_FLAG) + 1]
    )
    assert first_socket != second_socket
    assert first_socket.parent == run_state_directory
    assert second_socket.parent == run_state_directory


def test_timeout_kills_process(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake_process = _FakeProcess(
        returncode=0, stderr="still running", should_timeout=True
    )
    outcome, recorder, _, _, _ = _run_once(
        monkeypatch, tmp_path, fake_process, timeout_seconds=DEFAULT_TIMEOUT_SECONDS
    )

    assert fake_process.was_killed is True
    assert fake_process.communicate_calls >= 2
    assert fake_process.last_communicate_timeout == KILL_GRACE_TIMEOUT_SECONDS
    assert outcome.is_ok is False
    assert outcome.classification == CLASSIFICATION_TIMEOUT
    assert recorder.all_keyword_arguments[0].get("stdout") is subprocess.PIPE
    assert recorder.all_keyword_arguments[0].get("stderr") is subprocess.PIPE
    assert recorder.all_keyword_arguments[0].get("encoding") == UTF8_ENCODING
    assert recorder.all_keyword_arguments[0].get("errors") == UTF8_DECODE_ERRORS
    assert recorder.all_keyword_arguments[0].get("start_new_session") is (
        os.name != WINDOWS_OS_NAME
    )


def test_classifies_usage_limit_from_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_process = _FakeProcess(returncode=1, stderr=FIXTURE_USAGE_LIMIT_STDERR)
    outcome, _, _, _, _ = _run_once(monkeypatch, tmp_path, fake_process)

    assert outcome.is_ok is False
    assert outcome.returncode == 1
    assert outcome.classification == CLASSIFICATION_USAGE_LIMIT
    assert "429" in outcome.stderr
    assert outcome.stdout == ""


def test_classifies_auth_failure_from_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_process = _FakeProcess(returncode=1, stderr=FIXTURE_AUTH_FAILURE_STDERR)
    outcome, _, _, _, _ = _run_once(monkeypatch, tmp_path, fake_process)

    assert outcome.is_ok is False
    assert outcome.returncode == 1
    assert outcome.classification == CLASSIFICATION_AUTH_FAILURE
    assert "401" in outcome.stderr


def test_classifies_ok_on_zero_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_process = _FakeProcess(returncode=0, stdout='{"status":"done"}')
    outcome, _, _, _, _ = _run_once(monkeypatch, tmp_path, fake_process)

    assert outcome.is_ok is True
    assert outcome.returncode == 0
    assert outcome.classification == CLASSIFICATION_OK
    assert outcome.stdout == '{"status":"done"}'


def test_classifies_error_on_unknown_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_process = _FakeProcess(returncode=2, stderr=FIXTURE_GENERIC_FAILURE_STDERR)
    outcome, _, _, _, _ = _run_once(monkeypatch, tmp_path, fake_process)

    assert outcome.is_ok is False
    assert outcome.returncode == 2
    assert outcome.classification == CLASSIFICATION_ERROR


def test_scratch_paths_stay_under_run_state_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    fake_process = _FakeProcess(returncode=0, stdout="ok")
    outcome, recorder, _, _, run_state_directory = _run_once(
        monkeypatch, tmp_path, fake_process
    )

    assert outcome.is_ok is True
    invocation = recorder.invocations[0]
    leader_socket_path = Path(invocation[invocation.index(LEADER_SOCKET_FLAG) + 1])
    assert leader_socket_path.is_relative_to(run_state_directory)
    assert not leader_socket_path.is_relative_to(repo_root)
    written_inside_repo = list(repo_root.rglob("*"))
    assert written_inside_repo == []


def test_classifies_usage_limit_still_matches_real_fixture(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_process = _FakeProcess(
        returncode=1, stderr=FIXTURE_USAGE_LIMIT_STDERR
    )
    outcome, _, _, _, _ = _run_once(monkeypatch, tmp_path, fake_process)

    assert outcome.classification == CLASSIFICATION_USAGE_LIMIT


def test_credit_card_text_is_error_not_usage_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_process = _FakeProcess(
        returncode=1,
        stderr="invalid credit card field mapping on invoice line",
    )
    outcome, _, _, _, _ = _run_once(monkeypatch, tmp_path, fake_process)

    assert outcome.is_ok is False
    assert outcome.classification == CLASSIFICATION_ERROR
    assert outcome.classification != CLASSIFICATION_USAGE_LIMIT


def test_bare_near_miss_tokens_are_not_usage_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    all_near_miss_stderr = (
        "vendor code 42901 rejected the payload",
        "please verify credit before retry",
        "adjust disk quota on volume",
        "disk quota exceeded on volume",
    )
    for each_index, each_stderr in enumerate(all_near_miss_stderr):
        each_case_directory = tmp_path / f"near-miss-{each_index}"
        each_case_directory.mkdir()
        fake_process = _FakeProcess(returncode=1, stderr=each_stderr)
        outcome, _, _, _, _ = _run_once(
            monkeypatch, each_case_directory, fake_process
        )
        assert outcome.classification == CLASSIFICATION_ERROR, each_stderr
        assert outcome.classification != CLASSIFICATION_USAGE_LIMIT, each_stderr


def test_auth_near_miss_text_is_error_not_auth_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    all_near_miss_stderr = (
        "invalid keyword argument for helper",
        "invalid key mapping on invoice line",
        "unauthorized resource access by policy engine",
        "unauthorized",
    )
    for each_index, each_stderr in enumerate(all_near_miss_stderr):
        each_case_directory = tmp_path / f"auth-near-miss-{each_index}"
        each_case_directory.mkdir()
        fake_process = _FakeProcess(returncode=1, stderr=each_stderr)
        outcome, _, _, _, _ = _run_once(
            monkeypatch, each_case_directory, fake_process
        )
        assert outcome.classification == CLASSIFICATION_ERROR, each_stderr
        assert outcome.classification != CLASSIFICATION_AUTH_FAILURE, each_stderr


def test_tightened_usage_phrases_still_classify_usage_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    all_usage_stderr = (
        "api quota exceeded for this request",
        "usage quota exceeded on plan",
        "rate quota exceeded for endpoint",
    )
    for each_index, each_stderr in enumerate(all_usage_stderr):
        each_case_directory = tmp_path / f"usage-phrase-{each_index}"
        each_case_directory.mkdir()
        fake_process = _FakeProcess(returncode=1, stderr=each_stderr)
        outcome, _, _, _, _ = _run_once(
            monkeypatch, each_case_directory, fake_process
        )
        assert outcome.classification == CLASSIFICATION_USAGE_LIMIT, each_stderr


def test_tightened_auth_phrases_still_classify_auth_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    all_auth_stderr = (
        "error: unauthorized — please re-authenticate",
        "invalid api key supplied for this request",
        "client is not authenticated",
    )
    for each_index, each_stderr in enumerate(all_auth_stderr):
        each_case_directory = tmp_path / f"auth-phrase-{each_index}"
        each_case_directory.mkdir()
        fake_process = _FakeProcess(returncode=1, stderr=each_stderr)
        outcome, _, _, _, _ = _run_once(
            monkeypatch, each_case_directory, fake_process
        )
        assert outcome.classification == CLASSIFICATION_AUTH_FAILURE, each_stderr


def test_missing_binary_returns_dedicated_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the work", encoding="utf-8")
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    run_state_directory.mkdir()

    def _raise_file_not_found(
        invocation: list[str], **keyword_arguments: object
    ) -> object:
        del invocation, keyword_arguments
        raise FileNotFoundError(GROK_BINARY_NAME)

    monkeypatch.setattr(runner, "runner_popen", _raise_file_not_found)
    outcome = runner.run_headless_worker(
        prompt_file=prompt_file,
        working_directory=working_directory,
        run_state_directory=run_state_directory,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )

    assert outcome.is_ok is False
    assert outcome.classification == CLASSIFICATION_ERROR
    assert outcome.returncode == MISSING_BINARY_RETURN_CODE
    assert outcome.returncode != TIMEOUT_RETURN_CODE
    assert outcome.stderr != ""
    assert GROK_BINARY_NAME in outcome.stderr
    assert "not found" in outcome.stderr
    assert outcome.stderr == GROK_BINARY_NOT_FOUND_STDERR


def test_dual_match_prefers_auth_failure_over_usage_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dual_match_stderr = "HTTP 401 rate limit exceeded: unauthorized"
    fake_process = _FakeProcess(returncode=1, stderr=dual_match_stderr)
    outcome, _, _, _, _ = _run_once(monkeypatch, tmp_path, fake_process)

    assert outcome.is_ok is False
    assert outcome.classification == CLASSIFICATION_AUTH_FAILURE
    assert outcome.returncode == 1


def test_incidental_credit_word_is_error_not_usage_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_process = _FakeProcess(
        returncode=1,
        stdout="Finished auditing credit card picker skill",
        stderr="Error: ENOSPC disk full",
    )
    outcome, _, _, _, _ = _run_once(monkeypatch, tmp_path, fake_process)

    assert outcome.is_ok is False
    assert outcome.classification == CLASSIFICATION_ERROR
    assert "credit card" in outcome.stdout


def test_incidental_port_429_is_error_not_usage_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_process = _FakeProcess(
        returncode=1,
        stderr="connection refused: port 429 refused by peer",
    )
    outcome, _, _, _, _ = _run_once(monkeypatch, tmp_path, fake_process)

    assert outcome.is_ok is False
    assert outcome.classification == CLASSIFICATION_ERROR


def test_incidental_quota_of_tools_is_error_not_usage_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_process = _FakeProcess(
        returncode=1,
        stderr="configured quota of tools exceeded for this role",
    )
    outcome, _, _, _, _ = _run_once(monkeypatch, tmp_path, fake_process)

    assert outcome.is_ok is False
    assert outcome.classification == CLASSIFICATION_ERROR


def test_incidental_accreditation_failed_is_error_not_usage_limit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_process = _FakeProcess(
        returncode=1,
        stderr="accreditation failed for partner token",
    )
    outcome, _, _, _, _ = _run_once(monkeypatch, tmp_path, fake_process)

    assert outcome.is_ok is False
    assert outcome.classification == CLASSIFICATION_ERROR


def test_incidental_room_401_is_error_not_auth_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_process = _FakeProcess(
        returncode=1,
        stderr="meeting room 401 is unavailable",
    )
    outcome, _, _, _, _ = _run_once(monkeypatch, tmp_path, fake_process)

    assert outcome.is_ok is False
    assert outcome.classification == CLASSIFICATION_ERROR


def test_permission_error_on_launch_returns_structured_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the work", encoding="utf-8")
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    run_state_directory.mkdir()

    def _raise_permission_denied(
        invocation: list[str], **keyword_arguments: object
    ) -> object:
        del invocation, keyword_arguments
        raise PermissionError(13, "Permission denied", GROK_BINARY_NAME)

    monkeypatch.setattr(runner, "runner_popen", _raise_permission_denied)
    outcome = runner.run_headless_worker(
        prompt_file=prompt_file,
        working_directory=working_directory,
        run_state_directory=run_state_directory,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )

    assert outcome.is_ok is False
    assert outcome.classification == CLASSIFICATION_ERROR
    assert outcome.returncode == LAUNCH_FAILURE_RETURN_CODE
    assert outcome.returncode != TIMEOUT_RETURN_CODE
    assert outcome.returncode != MISSING_BINARY_RETURN_CODE
    assert outcome.stderr != ""
    assert outcome.stderr.startswith(LAUNCH_FAILURE_STDERR_PREFIX)


def test_invalid_utf8_child_stdout_is_replace_decoded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the work", encoding="utf-8")
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    run_state_directory.mkdir()
    invalid_byte_script = (
        "import sys; sys.stdout.buffer.write(b'\\xff\\xfe'); sys.exit(1)"
    )

    def _spawn_invalid_utf8_child(
        invocation: list[str], **keyword_arguments: object
    ) -> subprocess.Popen[str]:
        del invocation
        return subprocess.Popen(
            [sys.executable, "-c", invalid_byte_script],
            **keyword_arguments,
        )

    monkeypatch.setattr(runner, "runner_popen", _spawn_invalid_utf8_child)
    outcome = runner.run_headless_worker(
        prompt_file=prompt_file,
        working_directory=working_directory,
        run_state_directory=run_state_directory,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )

    assert outcome.is_ok is False
    assert outcome.stdout is not None
    assert isinstance(outcome.stdout, str)
    assert outcome.stdout != ""
    assert "\ufffd" in outcome.stdout
    assert outcome.classification == CLASSIFICATION_ERROR


def test_timeout_race_successful_exit_classifies_ok(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake_process = _FakeProcess(
        returncode=0,
        stdout='{"done":true}',
        should_timeout=True,
        returncode_after_kill=0,
    )
    outcome, _, _, _, _ = _run_once(
        monkeypatch, tmp_path, fake_process, timeout_seconds=DEFAULT_TIMEOUT_SECONDS
    )

    assert fake_process.was_killed is True
    assert outcome.is_ok is True
    assert outcome.classification == CLASSIFICATION_OK
    assert outcome.returncode == 0
    assert outcome.stdout == '{"done":true}'


def test_turn_capped_worker_cancels_and_uncapped_worker_completes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A turn cap cancels the multi-turn task; the same task completes without one.

    ::

        argv carries --max-turns 8   flag: stopReason Cancelled, is_ok False
        argv carries no turn cap     ok:   completes in 16 turns, is_ok True
    """
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the work", encoding=UTF8_ENCODING)
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    run_state_directory.mkdir()
    launcher = _TurnCapSensitiveLauncher()
    monkeypatch.setattr(runner, "runner_popen", launcher)

    capped_outcome = runner.run_headless_worker(
        prompt_file=prompt_file,
        working_directory=working_directory,
        run_state_directory=run_state_directory,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        all_extra_arguments=(MAX_TURNS_FLAG, str(TINY_TURN_CAP)),
    )
    uncapped_outcome = runner.run_headless_worker(
        prompt_file=prompt_file,
        working_directory=working_directory,
        run_state_directory=run_state_directory,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
    )

    assert capped_outcome.is_ok is False
    assert capped_outcome.classification == CLASSIFICATION_ERROR
    assert "cancelled" in capped_outcome.stderr.lower()
    assert uncapped_outcome.is_ok is True
    assert uncapped_outcome.classification == CLASSIFICATION_OK
    assert uncapped_outcome.stdout == FIXTURE_MULTI_TURN_REPORT
    assert MAX_TURNS_FLAG not in launcher.all_invocations[1]


def test_windows_timeout_kill_issues_the_taskkill_tree_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tree_kill_recorder = _TreeKillRecorder()
    monkeypatch.setattr(runner, "runner_subprocess_run", tree_kill_recorder)

    runner._kill_windows_process_tree(FAKE_PROCESS_IDENTIFIER)

    assert tree_kill_recorder.all_invocations == [
        [
            WINDOWS_TASKKILL_COMMAND,
            WINDOWS_TASKKILL_TREE_FLAG,
            WINDOWS_TASKKILL_FORCE_FLAG,
            WINDOWS_TASKKILL_PID_FLAG,
            str(FAKE_PROCESS_IDENTIFIER),
        ]
    ]
    assert (
        tree_kill_recorder.all_keyword_arguments[0].get("timeout")
        == PROCESS_TREE_KILL_TIMEOUT_SECONDS
    )


@pytest.mark.parametrize(
    "raised_error",
    [
        subprocess.TimeoutExpired(
            cmd=[WINDOWS_TASKKILL_COMMAND], timeout=PROCESS_TREE_KILL_TIMEOUT_SECONDS
        ),
        OSError("taskkill is not on PATH"),
    ],
    ids=["taskkill_times_out", "taskkill_cannot_launch"],
)
def test_windows_tree_kill_absorbs_a_failing_taskkill(
    monkeypatch: pytest.MonkeyPatch, raised_error: Exception
) -> None:
    """A taskkill that never completes leaves the caller free to fall back."""

    def raise_on_tree_kill(
        invocation: list[str], **keyword_arguments: object
    ) -> subprocess.CompletedProcess[str]:
        del invocation, keyword_arguments
        raise raised_error

    monkeypatch.setattr(runner, "runner_subprocess_run", raise_on_tree_kill)

    runner._kill_windows_process_tree(FAKE_PROCESS_IDENTIFIER)


def test_tree_kill_falls_back_to_direct_kill_when_taskkill_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A failed tree kill still ends the direct child, so no caller waits on it."""

    def raise_on_tree_kill(
        invocation: list[str], **keyword_arguments: object
    ) -> subprocess.CompletedProcess[str]:
        del invocation, keyword_arguments
        raise OSError("taskkill is not on PATH")

    fake_process = _FakeProcess(
        returncode=0, stderr="still running", should_timeout=True
    )
    monkeypatch.setattr(runner, "runner_subprocess_run", raise_on_tree_kill)
    outcome, _, _, _, _ = _run_once(
        monkeypatch,
        tmp_path,
        fake_process,
        timeout_seconds=DEFAULT_TIMEOUT_SECONDS,
        should_install_tree_kill_recorder=False,
    )

    assert fake_process.was_killed is True
    assert outcome.classification == CLASSIFICATION_TIMEOUT


def test_timed_out_worker_leaves_no_surviving_grandchild(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A timed-out worker takes its whole process tree, not just the direct child.

    ::

        parent spawns grandchild, runner times out
        ok:   heartbeat file stops growing after the kill
        flag: grandchild keeps writing, orphaned by a direct-child-only kill
    """
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the work", encoding=UTF8_ENCODING)
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    run_state_directory.mkdir()
    heartbeat_path = tmp_path / "grandchild-heartbeat.txt"
    heartbeat_path.write_text("", encoding=UTF8_ENCODING)

    def _spawn_parent_with_grandchild(
        invocation: list[str], **keyword_arguments: object
    ) -> subprocess.Popen[str]:
        del invocation
        return subprocess.Popen(
            [
                sys.executable,
                "-c",
                PARENT_SPAWNS_GRANDCHILD_SOURCE,
                GRANDCHILD_HEARTBEAT_SOURCE,
                str(heartbeat_path),
            ],
            **keyword_arguments,
        )

    monkeypatch.setattr(runner, "runner_popen", _spawn_parent_with_grandchild)
    outcome = runner.run_headless_worker(
        prompt_file=prompt_file,
        working_directory=working_directory,
        run_state_directory=run_state_directory,
        timeout_seconds=TINY_TIMEOUT_SECONDS,
    )
    time.sleep(GRANDCHILD_SETTLE_SECONDS)
    beats_after_kill = heartbeat_path.read_bytes()
    time.sleep(GRANDCHILD_OBSERVATION_SECONDS)
    beats_after_observation = heartbeat_path.read_bytes()

    assert outcome.classification == CLASSIFICATION_TIMEOUT
    assert beats_after_kill != b""
    assert beats_after_observation == beats_after_kill


def test_non_positive_timeout_is_refused_before_any_launch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("do the work", encoding=UTF8_ENCODING)
    working_directory = tmp_path / "project"
    working_directory.mkdir()
    run_state_directory = tmp_path / "run-state"
    run_state_directory.mkdir()
    recorder = _PopenRecorder([_FakeProcess(returncode=0, stdout="ok")])
    monkeypatch.setattr(runner, "runner_popen", recorder)

    with pytest.raises(ValueError, match="MIN_WORKER_TIMEOUT_SECONDS"):
        runner.run_headless_worker(
            prompt_file=prompt_file,
            working_directory=working_directory,
            run_state_directory=run_state_directory,
            timeout_seconds=NON_POSITIVE_TIMEOUT_SECONDS,
        )
    with pytest.raises(ValueError, match="MIN_WORKER_TIMEOUT_SECONDS"):
        runner.run_headless_worker(
            prompt_file=prompt_file,
            working_directory=working_directory,
            run_state_directory=run_state_directory,
            timeout_seconds=None,  # type: ignore[arg-type] # a JSON null timeout must be refused
        )
    assert recorder.invocations == []

    surviving_outcome = runner.run_headless_worker(
        prompt_file=prompt_file,
        working_directory=working_directory,
        run_state_directory=run_state_directory,
        timeout_seconds=MIN_WORKER_TIMEOUT_SECONDS,
    )

    assert surviving_outcome.is_ok is True
    assert len(recorder.invocations) == 1
