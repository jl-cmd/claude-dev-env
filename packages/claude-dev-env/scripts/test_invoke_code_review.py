"""Behavioral tests for the host-aware ``/code-review`` invoker."""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import claude_chain_runner as chain_runner  # noqa: E402
import invoke_code_review as invoker  # noqa: E402
from claude_chain_runner import (  # noqa: E402
    ChainAttempt,
    ChainConfigurationError,
    ChainInvocationOutcome,
)
from dev_env_scripts_constants.claude_chain_constants import (  # noqa: E402
    CHAIN_CONFIG_ERROR_EXIT_CODE,
)
from dev_env_scripts_constants.code_review_constants import (  # noqa: E402
    CLI_SESSION_MODEL_FLAG,
    CODE_REVIEW_EFFORT,
    CODE_REVIEW_MODEL_ALIAS,
    CODE_REVIEW_PROMPT,
    GIT_BINARY,
    GIT_PORCELAIN_FLAG,
    GIT_STATUS_SUBCOMMAND,
    HOST_PROFILE_ERROR_RETURNCODE,
    IN_SESSION_RETURNCODE,
    MODE_CHAIN,
    MODE_IN_SESSION,
    PERMISSION_MODE_BYPASS,
    PERMISSION_MODE_FLAG,
    RESULT_KEY_DIRTY_TREE,
    RESULT_KEY_MODE,
    RESULT_KEY_RETURNCODE,
    RESULT_KEY_SERVED_COMMAND,
)
from dev_env_scripts_constants.grok_worker_constants import (  # noqa: E402
    CLI_TIMEOUT_FLAG,
    CWD_FLAG,
    MODEL_FLAG,
    OUTPUT_FORMAT_FLAG,
    OUTPUT_FORMAT_JSON,
    SINGLE_TURN_FLAG,
)
from dev_env_scripts_constants.timing import (  # noqa: E402
    DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
)

HOST_PROFILE_CLAUDE = "Claude"
HOST_PROFILE_THIRD_PARTY = "ThirdParty"

FIXTURE_SERVED_COMMAND = "claude"
FIXTURE_CHAIN_RETURNCODE = 0
FIXTURE_FAILED_RETURNCODE = 1
FIXTURE_GIT_STATUS_FAILURE_RETURNCODE = 128
FIXTURE_CHAIN_STDOUT = '{"result":"review done"}'
FIXTURE_SESSION_OPUS = "opus"
FIXTURE_SESSION_OPUS_UPPER = "Opus"
FIXTURE_SESSION_SONNET = "sonnet"
FIXTURE_SESSION_HAIKU = "haiku"
FIXTURE_CHAIN_CONFIG_ERROR_MESSAGE = "chain config missing"
FIXTURE_HOST_PROFILE_ERROR_MESSAGE = "unknown host profile"
DIRTY_FILE_NAME = "review_fix.txt"
DIRTY_FILE_CONTENTS = "applied fix\n"
GIT_INIT_TIMEOUT_SECONDS = 30


def _claude_served(
    *,
    returncode: int = FIXTURE_CHAIN_RETURNCODE,
    stdout: str = FIXTURE_CHAIN_STDOUT,
) -> ChainInvocationOutcome:
    return ChainInvocationOutcome(
        served_command=FIXTURE_SERVED_COMMAND,
        returncode=returncode,
        stdout=stdout,
        stderr="",
        attempts=(
            ChainAttempt(command=FIXTURE_SERVED_COMMAND, status="served"),
        ),
    )


def _claude_failed() -> ChainInvocationOutcome:
    return ChainInvocationOutcome(
        served_command=None,
        returncode=FIXTURE_FAILED_RETURNCODE,
        stdout="",
        stderr="chain exhausted",
        attempts=(
            ChainAttempt(command=FIXTURE_SERVED_COMMAND, status="usage_limited"),
        ),
    )


def _init_git_repository(repository_directory: Path) -> Path:
    repository_directory.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [GIT_BINARY, "init"],
        cwd=str(repository_directory),
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_INIT_TIMEOUT_SECONDS,
    )
    subprocess.run(
        [GIT_BINARY, "config", "user.email", "reviewer@example.com"],
        cwd=str(repository_directory),
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_INIT_TIMEOUT_SECONDS,
    )
    subprocess.run(
        [GIT_BINARY, "config", "user.name", "Reviewer"],
        cwd=str(repository_directory),
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_INIT_TIMEOUT_SECONDS,
    )
    tracked_file = repository_directory / "README.md"
    tracked_file.write_text("baseline\n", encoding="utf-8")
    subprocess.run(
        [GIT_BINARY, "add", "README.md"],
        cwd=str(repository_directory),
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_INIT_TIMEOUT_SECONDS,
    )
    subprocess.run(
        [GIT_BINARY, "commit", "-m", "baseline"],
        cwd=str(repository_directory),
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_INIT_TIMEOUT_SECONDS,
    )
    return repository_directory


@dataclass
class SeamCallLog:
    claude_calls: int = 0
    claude_arguments: list[str] | None = None
    host_profile_calls: int = 0
    is_stdin_empty: bool = False
    claude_working_directory: Path | None = None
    all_observed_working_directories: list[Path] = field(default_factory=list)
    all_git_status_commands: list[list[str]] = field(default_factory=list)


def _install_seams(
    monkeypatch: pytest.MonkeyPatch,
    *,
    host_profile: str = HOST_PROFILE_CLAUDE,
    claude_outcome: ChainInvocationOutcome | BaseException | None = None,
    should_dirty_tree_on_chain: bool = False,
    working_directory: Path | None = None,
) -> SeamCallLog:
    call_log = SeamCallLog()

    def fake_host_profile(
        setting_by_name: object | None = None,
    ) -> str:
        del setting_by_name
        call_log.host_profile_calls += 1
        return host_profile

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
        if should_dirty_tree_on_chain and working_directory is not None:
            dirty_file = working_directory / DIRTY_FILE_NAME
            dirty_file.write_text(DIRTY_FILE_CONTENTS, encoding="utf-8")
        if isinstance(claude_outcome, BaseException):
            raise claude_outcome
        assert isinstance(claude_outcome, ChainInvocationOutcome)
        return claude_outcome

    def _tracking_subprocess_runner(
        all_invocation_tokens: Sequence[str],
        *all_positionals: object,
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_positionals
        maybe_stdin = all_keywords.get("stdin")
        if maybe_stdin is subprocess.DEVNULL:
            call_log.is_stdin_empty = True
        elif maybe_stdin is not None:
            maybe_read = getattr(maybe_stdin, "read", None)
            if callable(maybe_read):
                call_log.is_stdin_empty = maybe_read() == ""
                maybe_seek = getattr(maybe_stdin, "seek", None)
                if callable(maybe_seek):
                    maybe_seek(0)
        maybe_cwd = all_keywords.get("cwd")
        if maybe_cwd is not None:
            resolved_directory = Path(str(maybe_cwd))
            call_log.claude_working_directory = resolved_directory
            call_log.all_observed_working_directories.append(resolved_directory)
        return subprocess.CompletedProcess(
            args=list(all_invocation_tokens),
            returncode=0,
            stdout="{}",
            stderr="",
        )

    monkeypatch.setattr(invoker, "review_host_profile_detector", fake_host_profile)
    monkeypatch.setattr(invoker, "review_claude_runner", fake_claude)
    monkeypatch.setattr(
        chain_runner, "chain_subprocess_runner", _tracking_subprocess_runner
    )
    return call_log


@pytest.mark.parametrize(
    ("host_profile", "session_model", "expected_mode"),
    [
        (HOST_PROFILE_CLAUDE, FIXTURE_SESSION_OPUS, MODE_IN_SESSION),
        (HOST_PROFILE_CLAUDE, FIXTURE_SESSION_OPUS_UPPER, MODE_IN_SESSION),
        (HOST_PROFILE_CLAUDE, FIXTURE_SESSION_SONNET, MODE_CHAIN),
        (HOST_PROFILE_CLAUDE, FIXTURE_SESSION_HAIKU, MODE_CHAIN),
        (HOST_PROFILE_THIRD_PARTY, FIXTURE_SESSION_OPUS, MODE_CHAIN),
        (HOST_PROFILE_THIRD_PARTY, FIXTURE_SESSION_SONNET, MODE_CHAIN),
    ],
)
def test_mode_decision_host_and_model_matrix(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    host_profile: str,
    session_model: str,
    expected_mode: str,
) -> None:
    working_directory = _init_git_repository(tmp_path / "repo")
    claude_outcome = _claude_served() if expected_mode == MODE_CHAIN else None
    call_log = _install_seams(
        monkeypatch,
        host_profile=host_profile,
        claude_outcome=claude_outcome,
        working_directory=working_directory,
    )

    review_outcome = invoker.invoke_code_review(
        working_directory=working_directory,
        session_model=session_model,
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
    )

    assert review_outcome.mode == expected_mode
    assert call_log.host_profile_calls == 1
    if expected_mode == MODE_IN_SESSION:
        assert call_log.claude_calls == 0
        assert review_outcome.served_command is None
        assert review_outcome.returncode == IN_SESSION_RETURNCODE
        assert review_outcome.is_dirty_tree is False
    else:
        assert call_log.claude_calls == 1


def test_chain_argv_assembly(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = _init_git_repository(tmp_path / "repo")
    call_log = _install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=_claude_served(),
        working_directory=working_directory,
    )

    invoker.invoke_code_review(
        working_directory=working_directory,
        session_model=FIXTURE_SESSION_SONNET,
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
    )

    assert call_log.claude_arguments == [
        SINGLE_TURN_FLAG,
        CODE_REVIEW_PROMPT,
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
    working_directory = _init_git_repository(tmp_path / "repo")
    call_log = _install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=_claude_served(),
        working_directory=working_directory,
    )

    invoker.invoke_code_review(
        working_directory=working_directory,
        session_model=FIXTURE_SESSION_OPUS,
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
    )

    assert call_log.is_stdin_empty is True
    assert call_log.claude_working_directory == working_directory


def test_dirty_tree_true_after_chain_writes_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = _init_git_repository(tmp_path / "repo")
    _install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=_claude_served(),
        should_dirty_tree_on_chain=True,
        working_directory=working_directory,
    )

    review_outcome = invoker.invoke_code_review(
        working_directory=working_directory,
        session_model=FIXTURE_SESSION_OPUS,
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
    )

    assert review_outcome.mode == MODE_CHAIN
    assert review_outcome.is_dirty_tree is True
    assert review_outcome.served_command == FIXTURE_SERVED_COMMAND
    assert review_outcome.returncode == FIXTURE_CHAIN_RETURNCODE


def test_dirty_tree_false_when_chain_leaves_tree_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = _init_git_repository(tmp_path / "repo")
    _install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=_claude_served(),
        should_dirty_tree_on_chain=False,
        working_directory=working_directory,
    )

    review_outcome = invoker.invoke_code_review(
        working_directory=working_directory,
        session_model=FIXTURE_SESSION_OPUS,
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
    )

    assert review_outcome.is_dirty_tree is False


def test_cli_prints_result_json_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    working_directory = _init_git_repository(tmp_path / "repo")
    _install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_CLAUDE,
        claude_outcome=None,
        working_directory=working_directory,
    )

    exit_code = invoker.main(
        [
            CWD_FLAG,
            str(working_directory),
            CLI_SESSION_MODEL_FLAG,
            FIXTURE_SESSION_OPUS,
            CLI_TIMEOUT_FLAG,
            str(DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS),
        ]
    )

    assert exit_code == IN_SESSION_RETURNCODE
    captured = capsys.readouterr()
    assert captured.err == ""
    parsed_payload = json.loads(captured.out)
    assert parsed_payload == {
        RESULT_KEY_MODE: MODE_IN_SESSION,
        RESULT_KEY_SERVED_COMMAND: None,
        RESULT_KEY_RETURNCODE: IN_SESSION_RETURNCODE,
        RESULT_KEY_DIRTY_TREE: False,
    }


def test_code_review_prompt_uses_xhigh_effort() -> None:
    assert CODE_REVIEW_EFFORT == "xhigh"
    assert CODE_REVIEW_PROMPT == "/code-review xhigh --fix"


def test_build_code_review_arguments_matches_contract() -> None:
    all_arguments = invoker.build_code_review_arguments()
    assert all_arguments == [
        SINGLE_TURN_FLAG,
        CODE_REVIEW_PROMPT,
        MODEL_FLAG,
        CODE_REVIEW_MODEL_ALIAS,
        OUTPUT_FORMAT_FLAG,
        OUTPUT_FORMAT_JSON,
        PERMISSION_MODE_FLAG,
        PERMISSION_MODE_BYPASS,
    ]
    assert CODE_REVIEW_PROMPT in all_arguments
    assert all_arguments[all_arguments.index(SINGLE_TURN_FLAG) + 1] == (
        "/code-review xhigh --fix"
    )


def test_is_working_tree_dirty_against_real_git_repo(tmp_path: Path) -> None:
    working_directory = _init_git_repository(tmp_path / "repo")
    assert invoker.is_working_tree_dirty(working_directory) is False
    (working_directory / DIRTY_FILE_NAME).write_text(
        DIRTY_FILE_CONTENTS, encoding="utf-8"
    )
    assert invoker.is_working_tree_dirty(working_directory) is True


def test_git_status_command_uses_porcelain(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = _init_git_repository(tmp_path / "repo")
    all_commands: list[list[str]] = []

    def fake_git_status(
        all_command_tokens: Sequence[str],
        *all_positionals: object,
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_positionals, all_keywords
        all_commands.append(list(all_command_tokens))
        return subprocess.CompletedProcess(
            args=list(all_command_tokens),
            returncode=0,
            stdout="",
            stderr="",
        )

    monkeypatch.setattr(invoker, "review_git_status_runner", fake_git_status)
    invoker.is_working_tree_dirty(working_directory)
    assert all_commands == [
        [GIT_BINARY, GIT_STATUS_SUBCOMMAND, GIT_PORCELAIN_FLAG]
    ]


def test_chain_failure_preserves_returncode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = _init_git_repository(tmp_path / "repo")
    _install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=_claude_failed(),
        working_directory=working_directory,
    )

    review_outcome = invoker.invoke_code_review(
        working_directory=working_directory,
        session_model=FIXTURE_SESSION_OPUS,
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
    )

    assert review_outcome.mode == MODE_CHAIN
    assert review_outcome.served_command is None
    assert review_outcome.returncode == FIXTURE_FAILED_RETURNCODE
    assert review_outcome.is_dirty_tree is False
    assert invoker.is_successful_code_review(review_outcome) is False
    assert invoker.is_code_review_clean_stamp_allowed(review_outcome) is False


def test_is_working_tree_dirty_nonzero_returncode_is_not_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = _init_git_repository(tmp_path / "repo")

    def fake_git_status(
        all_command_tokens: Sequence[str],
        *all_positionals: object,
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_positionals, all_keywords
        return subprocess.CompletedProcess(
            args=list(all_command_tokens),
            returncode=FIXTURE_GIT_STATUS_FAILURE_RETURNCODE,
            stdout="",
            stderr="fatal: not a git repository",
        )

    monkeypatch.setattr(invoker, "review_git_status_runner", fake_git_status)
    assert invoker.is_working_tree_dirty(working_directory) is True


def test_cli_emits_json_on_chain_configuration_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    working_directory = _init_git_repository(tmp_path / "repo")
    _install_seams(
        monkeypatch,
        host_profile=HOST_PROFILE_THIRD_PARTY,
        claude_outcome=ChainConfigurationError(FIXTURE_CHAIN_CONFIG_ERROR_MESSAGE),
        working_directory=working_directory,
    )

    exit_code = invoker.main(
        [
            CWD_FLAG,
            str(working_directory),
            CLI_SESSION_MODEL_FLAG,
            FIXTURE_SESSION_OPUS,
            CLI_TIMEOUT_FLAG,
            str(DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS),
        ]
    )

    assert exit_code == CHAIN_CONFIG_ERROR_EXIT_CODE
    captured = capsys.readouterr()
    parsed_payload = json.loads(captured.out)
    assert parsed_payload == {
        RESULT_KEY_MODE: MODE_CHAIN,
        RESULT_KEY_SERVED_COMMAND: None,
        RESULT_KEY_RETURNCODE: CHAIN_CONFIG_ERROR_EXIT_CODE,
        RESULT_KEY_DIRTY_TREE: False,
    }
    assert invoker.is_code_review_clean_stamp_allowed(
        invoker.CodeReviewOutcome(
            mode=MODE_CHAIN,
            served_command=None,
            returncode=CHAIN_CONFIG_ERROR_EXIT_CODE,
            is_dirty_tree=False,
        )
    ) is False


def test_cli_emits_json_on_host_profile_value_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    working_directory = _init_git_repository(tmp_path / "repo")

    def fake_host_profile_raises(
        setting_by_name: object | None = None,
    ) -> str:
        del setting_by_name
        raise ValueError(FIXTURE_HOST_PROFILE_ERROR_MESSAGE)

    monkeypatch.setattr(
        invoker, "review_host_profile_detector", fake_host_profile_raises
    )

    exit_code = invoker.main(
        [
            CWD_FLAG,
            str(working_directory),
            CLI_SESSION_MODEL_FLAG,
            FIXTURE_SESSION_OPUS,
            CLI_TIMEOUT_FLAG,
            str(DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS),
        ]
    )

    assert exit_code == HOST_PROFILE_ERROR_RETURNCODE
    captured = capsys.readouterr()
    parsed_payload = json.loads(captured.out)
    assert parsed_payload == {
        RESULT_KEY_MODE: MODE_CHAIN,
        RESULT_KEY_SERVED_COMMAND: None,
        RESULT_KEY_RETURNCODE: HOST_PROFILE_ERROR_RETURNCODE,
        RESULT_KEY_DIRTY_TREE: False,
    }


def test_clean_stamp_allowed_only_on_successful_clean_serve() -> None:
    clean_success = invoker.CodeReviewOutcome(
        mode=MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
        returncode=FIXTURE_CHAIN_RETURNCODE,
        is_dirty_tree=False,
    )
    dirty_success = invoker.CodeReviewOutcome(
        mode=MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
        returncode=FIXTURE_CHAIN_RETURNCODE,
        is_dirty_tree=True,
    )
    failed_serve = invoker.CodeReviewOutcome(
        mode=MODE_CHAIN,
        served_command=None,
        returncode=FIXTURE_FAILED_RETURNCODE,
        is_dirty_tree=False,
    )
    in_session_ready = invoker.CodeReviewOutcome(
        mode=MODE_IN_SESSION,
        served_command=None,
        returncode=IN_SESSION_RETURNCODE,
        is_dirty_tree=False,
    )

    assert invoker.is_code_review_clean_stamp_allowed(clean_success) is True
    assert invoker.is_code_review_clean_stamp_allowed(dirty_success) is False
    assert invoker.is_code_review_clean_stamp_allowed(failed_serve) is False
    assert invoker.is_code_review_clean_stamp_allowed(in_session_ready) is True
    assert invoker.is_successful_code_review(failed_serve) is False
    assert invoker.is_successful_code_review(clean_success) is True


@pytest.mark.parametrize(
    ("session_model", "expected_is_opus"),
    [
        (FIXTURE_SESSION_OPUS, True),
        (FIXTURE_SESSION_OPUS_UPPER, True),
        (FIXTURE_SESSION_SONNET, False),
        ("  opus  ", True),
    ],
)
def test_is_opus_session_model(
    session_model: str, expected_is_opus: bool
) -> None:
    assert invoker.is_opus_session_model(session_model) is expected_is_opus


@pytest.mark.parametrize(
    ("host_profile", "session_model", "expected_mode"),
    [
        (HOST_PROFILE_CLAUDE, FIXTURE_SESSION_OPUS, MODE_IN_SESSION),
        (HOST_PROFILE_CLAUDE, FIXTURE_SESSION_SONNET, MODE_CHAIN),
        (HOST_PROFILE_THIRD_PARTY, FIXTURE_SESSION_OPUS, MODE_CHAIN),
    ],
)
def test_decide_review_mode(
    host_profile: str, session_model: str, expected_mode: str
) -> None:
    assert (
        invoker.decide_review_mode(
            host_profile=host_profile,
            session_model=session_model,
        )
        == expected_mode
    )


def test_encode_code_review_outcome_shape() -> None:
    review_outcome = invoker.CodeReviewOutcome(
        mode=MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
        returncode=FIXTURE_CHAIN_RETURNCODE,
        is_dirty_tree=True,
    )
    encoded_payload = invoker.encode_code_review_outcome(review_outcome)
    assert encoded_payload == {
        RESULT_KEY_MODE: MODE_CHAIN,
        RESULT_KEY_SERVED_COMMAND: FIXTURE_SERVED_COMMAND,
        RESULT_KEY_RETURNCODE: FIXTURE_CHAIN_RETURNCODE,
        RESULT_KEY_DIRTY_TREE: True,
    }
