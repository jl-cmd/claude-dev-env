"""Behavioral tests for the host-aware ``/code-review`` invoker and stamps."""

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
    CODE_REVIEW_MODEL_ALIAS,
    DEFAULT_CODE_REVIEW_EFFORT,
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


def test_build_code_review_arguments_matches_contract() -> None:
    all_arguments = invoker.build_code_review_arguments()
    assert all_arguments == [
        SINGLE_TURN_FLAG,
        invoker.build_code_review_prompt(DEFAULT_CODE_REVIEW_EFFORT),
        MODEL_FLAG,
        CODE_REVIEW_MODEL_ALIAS,
        OUTPUT_FORMAT_FLAG,
        OUTPUT_FORMAT_JSON,
        PERMISSION_MODE_FLAG,
        PERMISSION_MODE_BYPASS,
    ]


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


EFFORT_LOW = "low"
REJECTED_ULTRA_EFFORT = "ultra"
RECORD_STAMP_MINT_CAP = 3
SINGLE_PASS_CAP = 1
INVALID_EFFORT_EXIT_CODE = 2
DID_NOT_CONVERGE_EXIT_CODE = 1
RECORD_STAMP_CLI_FLAG = "--record-stamp"
RESULT_STAMP_MINTED_KEY = "stamp_minted"
RESULT_PASS_COUNT_KEY = "pass_count"
RESULT_BOUND_HASH_KEY = "bound_hash"
MISSING_STORE_FILE_NAME = "code_review_stamp_store_absent.py"
SURFACE_SOURCE = "def add(left: int, right: int) -> int:\n    return left + right\n"
SURFACE_CHANGE_SOURCE = "def add(left: int, right: int) -> int:\n    return left - right\n"


def _run_git(repository_directory: Path, *git_arguments: str) -> None:
    subprocess.run(
        [GIT_BINARY, "-C", str(repository_directory), *git_arguments],
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_INIT_TIMEOUT_SECONDS,
    )


def _make_repo_with_change_surface(tmp_path: Path) -> Path:
    origin_directory = tmp_path / "origin.git"
    work_directory = tmp_path / "work"
    work_directory.mkdir()
    subprocess.run(
        [GIT_BINARY, "init", "--bare", "--initial-branch=main", str(origin_directory)],
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_INIT_TIMEOUT_SECONDS,
    )
    _run_git(work_directory, "init", "--initial-branch=main")
    _run_git(work_directory, "config", "user.email", "tests@example.com")
    _run_git(work_directory, "config", "user.name", "Reviewer")
    (work_directory / "app.py").write_text(SURFACE_SOURCE, encoding="utf-8")
    _run_git(work_directory, "add", "-A")
    _run_git(work_directory, "commit", "-m", "base")
    _run_git(work_directory, "remote", "add", "origin", str(origin_directory))
    _run_git(work_directory, "push", "-u", "origin", "main")
    (work_directory / "app.py").write_text(SURFACE_CHANGE_SOURCE, encoding="utf-8")
    return work_directory


def _isolate_home(monkeypatch: pytest.MonkeyPatch, fake_home: Path) -> None:
    home_text = str(fake_home)
    monkeypatch.setenv("HOME", home_text)
    monkeypatch.setenv("USERPROFILE", home_text)
    monkeypatch.delenv("HOMEDRIVE", raising=False)
    monkeypatch.delenv("HOMEPATH", raising=False)


def _prepared_surface_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    return _make_repo_with_change_surface(tmp_path)


def _chain_clean_outcome() -> invoker.CodeReviewOutcome:
    return invoker.CodeReviewOutcome(
        mode=MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
        returncode=FIXTURE_CHAIN_RETURNCODE,
        is_dirty_tree=True,
    )


def _stable_clean_review(**_review_keywords: object) -> invoker.CodeReviewOutcome:
    return _chain_clean_outcome()


def _surface_changing_review(
    *, working_directory: Path, **_review_keywords: object
) -> invoker.CodeReviewOutcome:
    applied_fix_path = working_directory / DIRTY_FILE_NAME
    applied_fix_path.write_text(DIRTY_FILE_CONTENTS, encoding="utf-8")
    return _chain_clean_outcome()


class _DriftingReview:
    def __init__(self) -> None:
        self.pass_count = 0

    def __call__(
        self, *, working_directory: Path, **_review_keywords: object
    ) -> invoker.CodeReviewOutcome:
        self.pass_count += 1
        drift_path = working_directory / f"fix_{self.pass_count}.txt"
        drift_path.write_text(str(self.pass_count), encoding="utf-8")
        return _chain_clean_outcome()


@pytest.mark.parametrize("valid_effort", ["low", "medium", "high", "xhigh", "max"])
def test_validate_effort_token_accepts_known_tokens(valid_effort: str) -> None:
    assert invoker.validate_effort_token(valid_effort) is None


def test_validate_effort_token_rejects_ultra_loudly() -> None:
    error_message = invoker.validate_effort_token(REJECTED_ULTRA_EFFORT)
    assert error_message is not None
    assert REJECTED_ULTRA_EFFORT in error_message


def test_validate_effort_token_rejects_unknown_token() -> None:
    error_message = invoker.validate_effort_token("bogus")
    assert error_message is not None
    assert "bogus" in error_message


def test_build_code_review_prompt_reads_as_slash_command() -> None:
    assert invoker.build_code_review_prompt(EFFORT_LOW) == "/code-review low --fix"
    assert invoker.build_code_review_prompt("xhigh") == "/code-review xhigh --fix"


def test_cli_rejects_ultra_effort_with_nonzero_exit(
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
            REJECTED_ULTRA_EFFORT,
        ]
    )
    assert exit_code == INVALID_EFFORT_EXIT_CODE
    assert REJECTED_ULTRA_EFFORT in capsys.readouterr().err


def test_record_stamp_mints_on_surface_stable_clean_pass(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = _prepared_surface_repo(monkeypatch, tmp_path)
    monkeypatch.setattr(invoker, "invoke_code_review", _stable_clean_review)
    mint_outcome = invoker.invoke_code_review_and_record_stamp(
        working_directory=working_directory,
        session_model=CODE_REVIEW_MODEL_ALIAS,
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
        effort=EFFORT_LOW,
    )
    assert mint_outcome.is_stamp_minted is True
    assert mint_outcome.bound_hash is not None
    store_module = invoker.load_code_review_stamp_store()
    assert store_module.stamp_covers_surface(
        str(working_directory), mint_outcome.bound_hash, EFFORT_LOW
    )


def test_record_stamp_does_not_mint_when_review_changes_surface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = _prepared_surface_repo(monkeypatch, tmp_path)
    monkeypatch.setattr(invoker, "invoke_code_review", _surface_changing_review)
    mint_outcome = invoker.invoke_code_review_and_record_stamp(
        working_directory=working_directory,
        session_model=CODE_REVIEW_MODEL_ALIAS,
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
        effort=EFFORT_LOW,
        maximum_passes=SINGLE_PASS_CAP,
    )
    assert mint_outcome.is_stamp_minted is False
    assert mint_outcome.pass_count == SINGLE_PASS_CAP
    assert mint_outcome.bound_hash is None


def test_record_stamp_hits_cap_without_minting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = _prepared_surface_repo(monkeypatch, tmp_path)
    monkeypatch.setattr(invoker, "invoke_code_review", _DriftingReview())
    mint_outcome = invoker.invoke_code_review_and_record_stamp(
        working_directory=working_directory,
        session_model=CODE_REVIEW_MODEL_ALIAS,
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
        effort=EFFORT_LOW,
        maximum_passes=RECORD_STAMP_MINT_CAP,
    )
    assert mint_outcome.is_stamp_minted is False
    assert mint_outcome.pass_count == RECORD_STAMP_MINT_CAP


def test_cli_record_stamp_returns_non_convergence_code_on_cap(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    working_directory = _prepared_surface_repo(monkeypatch, tmp_path)
    monkeypatch.setattr(invoker, "invoke_code_review", _DriftingReview())
    exit_code = invoker.main(
        [
            CWD_FLAG,
            str(working_directory),
            CLI_SESSION_MODEL_FLAG,
            CODE_REVIEW_MODEL_ALIAS,
            RECORD_STAMP_CLI_FLAG,
            EFFORT_LOW,
        ]
    )
    assert exit_code == DID_NOT_CONVERGE_EXIT_CODE
    parsed_payload = json.loads(capsys.readouterr().out)
    assert parsed_payload[RESULT_STAMP_MINTED_KEY] is False
    assert parsed_payload[RESULT_PASS_COUNT_KEY] == RECORD_STAMP_MINT_CAP
    assert parsed_payload[RESULT_BOUND_HASH_KEY] is None


def test_load_code_review_stamp_store_records_and_covers_surface(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    working_directory = _prepared_surface_repo(monkeypatch, tmp_path)
    store_module = invoker.load_code_review_stamp_store()
    surface_hash = store_module.live_surface_hash(str(working_directory))
    assert surface_hash is not None
    stamp_path = store_module.record_clean_stamp(
        str(working_directory), surface_hash, EFFORT_LOW
    )
    assert stamp_path.exists()
    assert store_module.stamp_covers_surface(
        str(working_directory), surface_hash, EFFORT_LOW
    )


def test_load_code_review_stamp_store_raises_when_file_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        invoker, "STAMP_STORE_MODULE_FILE_NAME", MISSING_STORE_FILE_NAME
    )
    with pytest.raises(ModuleNotFoundError):
        invoker.load_code_review_stamp_store()


def test_cli_record_stamp_reports_missing_store_dependency(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    working_directory = _init_git_repository(tmp_path / "repo")

    def raise_missing_store(*all_args: object, **all_keywords: object) -> object:
        del all_args, all_keywords
        raise ModuleNotFoundError("store missing", name="code_review_stamp_store")

    monkeypatch.setattr(invoker, "load_code_review_stamp_store", raise_missing_store)
    exit_code = invoker.main(
        [
            CWD_FLAG,
            str(working_directory),
            CLI_SESSION_MODEL_FLAG,
            CODE_REVIEW_MODEL_ALIAS,
            RECORD_STAMP_CLI_FLAG,
            EFFORT_LOW,
        ]
    )
    assert exit_code == INVALID_EFFORT_EXIT_CODE
    captured = capsys.readouterr()
    assert "stamp store" in captured.err
    parsed_payload = json.loads(captured.out)
    assert parsed_payload[RESULT_STAMP_MINTED_KEY] is False


def test_encode_stamp_mint_outcome_includes_mint_metadata() -> None:
    review_outcome = invoker.CodeReviewOutcome(
        mode=MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
        returncode=FIXTURE_CHAIN_RETURNCODE,
        is_dirty_tree=False,
    )
    mint_outcome = invoker.StampMintOutcome(
        review_outcome=review_outcome,
        is_stamp_minted=True,
        pass_count=SINGLE_PASS_CAP,
        bound_hash="abc123",
    )
    encoded_payload = invoker.encode_stamp_mint_outcome(mint_outcome)
    assert encoded_payload[RESULT_STAMP_MINTED_KEY] is True
    assert encoded_payload[RESULT_PASS_COUNT_KEY] == SINGLE_PASS_CAP
    assert encoded_payload[RESULT_BOUND_HASH_KEY] == "abc123"
