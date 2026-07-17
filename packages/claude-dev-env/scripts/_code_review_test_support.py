"""Shared fixtures and seams for the ``/code-review`` invoker test suite.

Every ``test_invoke_code_review_*`` module imports its fixture values, its
chain-outcome builders, its runner shortcuts, and its seam installer from here
so the behavioral groups stay small and none of the shared support is copied
between them.

The conftest beside this file registers the scripts directory on ``sys.path``,
so the invoker and its constants package resolve by bare name below.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

import pytest

try:
    import claude_chain_runner as chain_runner
    import invoke_code_review as invoker
    from claude_chain_runner import ChainAttempt, ChainInvocationOutcome
    from dev_env_scripts_constants.code_review_constants import (
        CLI_SESSION_MODEL_FLAG,
        CODE_REVIEW_MODEL_ALIAS,
        GIT_BINARY,
        RECORD_STAMP_FLAG,
    )
    from dev_env_scripts_constants.grok_worker_constants import (
        CLI_TIMEOUT_FLAG,
        CWD_FLAG,
    )
    from dev_env_scripts_constants.timing import DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import claude_chain_runner as chain_runner
    import invoke_code_review as invoker
    from claude_chain_runner import ChainAttempt, ChainInvocationOutcome
    from dev_env_scripts_constants.code_review_constants import (
        CLI_SESSION_MODEL_FLAG,
        CODE_REVIEW_MODEL_ALIAS,
        GIT_BINARY,
        RECORD_STAMP_FLAG,
    )
    from dev_env_scripts_constants.grok_worker_constants import (
        CLI_TIMEOUT_FLAG,
        CWD_FLAG,
    )
    from dev_env_scripts_constants.timing import DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS


def run_record_stamp_cli(working_directory: Path, *, effort: str) -> int:
    return invoker.main(
        [
            CWD_FLAG,
            str(working_directory),
            CLI_SESSION_MODEL_FLAG,
            CODE_REVIEW_MODEL_ALIAS,
            RECORD_STAMP_FLAG,
            effort,
        ]
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


def claude_served(
    *,
    returncode: int = FIXTURE_CHAIN_RETURNCODE,
    stdout: str = FIXTURE_CHAIN_STDOUT,
) -> ChainInvocationOutcome:
    return ChainInvocationOutcome(
        served_command=FIXTURE_SERVED_COMMAND,
        returncode=returncode,
        stdout=stdout,
        stderr="",
        attempts=(ChainAttempt(command=FIXTURE_SERVED_COMMAND, status="served"),),
    )


def claude_failed() -> ChainInvocationOutcome:
    return ChainInvocationOutcome(
        served_command=None,
        returncode=FIXTURE_FAILED_RETURNCODE,
        stdout="",
        stderr="chain exhausted",
        attempts=(
            ChainAttempt(command=FIXTURE_SERVED_COMMAND, status="usage_limited"),
        ),
    )


def _run_git_command(repository_directory: Path, *git_arguments: str) -> None:
    subprocess.run(
        [GIT_BINARY, *git_arguments],
        cwd=str(repository_directory),
        check=True,
        capture_output=True,
        text=True,
        timeout=GIT_INIT_TIMEOUT_SECONDS,
    )


def init_git_repository(repository_directory: Path) -> Path:
    repository_directory.mkdir(parents=True, exist_ok=True)
    _run_git_command(repository_directory, "init")
    _run_git_command(
        repository_directory, "config", "user.email", "reviewer@example.com"
    )
    _run_git_command(repository_directory, "config", "user.name", "Reviewer")
    (repository_directory / "README.md").write_text("baseline\n", encoding="utf-8")
    _run_git_command(repository_directory, "add", "README.md")
    _run_git_command(repository_directory, "commit", "-m", "baseline")
    return repository_directory


def run_review(
    working_directory: Path, *, session_model: str
) -> invoker.CodeReviewOutcome:
    return invoker.invoke_code_review(
        working_directory=working_directory,
        session_model=session_model,
        timeout_seconds=DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS,
    )


def run_review_cli(working_directory: Path, *, session_model: str) -> int:
    return invoker.main(
        [
            CWD_FLAG,
            str(working_directory),
            CLI_SESSION_MODEL_FLAG,
            session_model,
            CLI_TIMEOUT_FLAG,
            str(DEFAULT_CODE_REVIEW_TIMEOUT_SECONDS),
        ]
    )


@dataclass
class SeamCallLog:
    claude_calls: int = 0
    claude_arguments: list[str] | None = None
    host_profile_calls: int = 0
    is_stdin_empty: bool = False
    claude_working_directory: Path | None = None
    all_observed_working_directories: list[Path] = field(default_factory=list)


@dataclass
class _SeamConfiguration:
    host_profile: str
    claude_outcome: ChainInvocationOutcome | BaseException | None
    should_dirty_tree_on_chain: bool
    working_directory: Path | None


def _record_dirty_tree(configuration: _SeamConfiguration) -> None:
    if not configuration.should_dirty_tree_on_chain:
        return
    if configuration.working_directory is None:
        return
    dirty_file = configuration.working_directory / DIRTY_FILE_NAME
    dirty_file.write_text(DIRTY_FILE_CONTENTS, encoding="utf-8")


def _detect_empty_stdin(maybe_stdin: object) -> bool | None:
    if maybe_stdin is subprocess.DEVNULL:
        return True
    if maybe_stdin is None:
        return None
    maybe_read = getattr(maybe_stdin, "read", None)
    if not callable(maybe_read):
        return None
    stdin_contents = maybe_read()
    maybe_seek = getattr(maybe_stdin, "seek", None)
    if callable(maybe_seek):
        maybe_seek(0)
    return stdin_contents == ""


def _build_host_profile_seam(
    call_log: SeamCallLog, configuration: _SeamConfiguration
) -> Callable[..., str]:
    def fake_host_profile(setting_by_name: object | None = None) -> str:
        del setting_by_name
        call_log.host_profile_calls += 1
        return configuration.host_profile

    return fake_host_profile


def _build_claude_seam(
    call_log: SeamCallLog, configuration: _SeamConfiguration
) -> Callable[..., ChainInvocationOutcome]:
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
        _record_dirty_tree(configuration)
        if isinstance(configuration.claude_outcome, BaseException):
            raise configuration.claude_outcome
        assert isinstance(configuration.claude_outcome, ChainInvocationOutcome)
        return configuration.claude_outcome

    return fake_claude


def _build_subprocess_seam(
    call_log: SeamCallLog,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def tracking_subprocess_runner(
        all_invocation_tokens: Sequence[str],
        *all_positionals: object,
        **all_keywords: object,
    ) -> subprocess.CompletedProcess[str]:
        del all_positionals
        maybe_empty_stdin = _detect_empty_stdin(all_keywords.get("stdin"))
        if maybe_empty_stdin is not None:
            call_log.is_stdin_empty = maybe_empty_stdin
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

    return tracking_subprocess_runner


def _apply_seams(
    monkeypatch: pytest.MonkeyPatch,
    call_log: SeamCallLog,
    configuration: _SeamConfiguration,
) -> None:
    monkeypatch.setattr(
        invoker,
        "review_host_profile_detector",
        _build_host_profile_seam(call_log, configuration),
    )
    monkeypatch.setattr(
        invoker,
        "review_claude_runner",
        _build_claude_seam(call_log, configuration),
    )
    monkeypatch.setattr(
        chain_runner,
        "chain_subprocess_runner",
        _build_subprocess_seam(call_log),
    )


def install_seams(
    monkeypatch: pytest.MonkeyPatch,
    *,
    host_profile: str = HOST_PROFILE_CLAUDE,
    claude_outcome: ChainInvocationOutcome | BaseException | None = None,
    should_dirty_tree_on_chain: bool = False,
    working_directory: Path | None = None,
) -> SeamCallLog:
    call_log = SeamCallLog()
    configuration = _SeamConfiguration(
        host_profile=host_profile,
        claude_outcome=claude_outcome,
        should_dirty_tree_on_chain=should_dirty_tree_on_chain,
        working_directory=working_directory,
    )
    _apply_seams(monkeypatch, call_log, configuration)
    return call_log


EFFORT_LOW = "low"
REJECTED_ULTRA_EFFORT = "ultra"
RECORD_STAMP_MINT_CAP = 3
SINGLE_PASS_CAP = 1
INVALID_EFFORT_EXIT_CODE = 2
DID_NOT_CONVERGE_EXIT_CODE = 1
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
        [
            GIT_BINARY,
            "init",
            "--bare",
            "--initial-branch=main",
            str(origin_directory),
        ],
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


def prepared_surface_repo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    _isolate_home(monkeypatch, fake_home)
    return _make_repo_with_change_surface(tmp_path)


def _chain_clean_outcome() -> invoker.CodeReviewOutcome:
    return invoker.CodeReviewOutcome(
        mode=invoker.MODE_CHAIN,
        served_command=FIXTURE_SERVED_COMMAND,
        returncode=FIXTURE_CHAIN_RETURNCODE,
        is_dirty_tree=True,
    )


def stable_clean_review(**_review_keywords: object) -> invoker.CodeReviewOutcome:
    return _chain_clean_outcome()


def surface_changing_review(
    *, working_directory: Path, **_review_keywords: object
) -> invoker.CodeReviewOutcome:
    applied_fix_path = working_directory / DIRTY_FILE_NAME
    applied_fix_path.write_text(DIRTY_FILE_CONTENTS, encoding="utf-8")
    return _chain_clean_outcome()


class DriftingReview:
    def __init__(self) -> None:
        self.pass_count = 0

    def __call__(
        self, *, working_directory: Path, **_review_keywords: object
    ) -> invoker.CodeReviewOutcome:
        self.pass_count += 1
        drift_path = working_directory / f"fix_{self.pass_count}.txt"
        drift_path.write_text(str(self.pass_count), encoding="utf-8")
        return _chain_clean_outcome()
