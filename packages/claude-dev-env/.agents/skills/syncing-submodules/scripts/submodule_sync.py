from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from submodule_sync_constants.config.constants import (
    ALL_GH_PULL_REQUEST_ARGUMENTS,
    DECODE_ERRORS_POLICY,
    EXIT_CODE_FAILURE,
    EXIT_CODE_SUCCESS,
    GH_COMMAND_TIMEOUT_SECONDS,
    GH_EXECUTABLE_NAME,
    GIT_ADD_SUBCOMMAND,
    GIT_ARGUMENT_SEPARATOR,
    GIT_CACHED_ARGUMENT,
    GIT_COMMAND_TIMEOUT_SECONDS,
    GIT_COMMIT_SUBCOMMAND,
    GIT_DIFF_SUBCOMMAND,
    GIT_EXECUTABLE_NAME,
    GIT_EXIT_FAILURE_MESSAGE_TEMPLATE,
    GIT_HEAD_REFERENCE,
    GIT_LATEST_COMMIT_ARGUMENT,
    GIT_LAUNCH_FAILURE_MESSAGE_TEMPLATE,
    GIT_LITERAL_PATHSPEC_PREFIX,
    GIT_LOG_SUBCOMMAND,
    GIT_MESSAGE_ARGUMENT,
    GIT_ONLY_ARGUMENT,
    GIT_QUIET_ARGUMENT,
    GIT_REV_PARSE_SUBCOMMAND,
    GIT_SHOW_SUPERPROJECT_ARGUMENT,
    GIT_SHOW_TOP_LEVEL_ARGUMENT,
    GIT_SUBJECT_FORMAT_ARGUMENT,
    GIT_TIMEOUT_MESSAGE_TEMPLATE,
    PARENT_COMMIT_MESSAGE_TEMPLATE,
    REPOSITORY_NOT_DIRECTORY_MESSAGE_TEMPLATE,
    REPOSITORY_RESOLUTION_FAILURE_MESSAGE,
    SUBMODULE_COMMIT_MESSAGE_TEMPLATE,
    SUBMODULE_PATH_FAILURE_MESSAGE,
    SYNC_STATUS_ERROR,
    SYNC_STATUS_NOT_SUBMODULE,
    SYNC_STATUS_UNCHANGED,
    SYNC_STATUS_UPDATED,
    UTF8_ENCODING,
)


class SyncStatus(StrEnum):
    """States reported by one parent-pointer sync."""

    UPDATED = SYNC_STATUS_UPDATED
    UNCHANGED = SYNC_STATUS_UNCHANGED
    NOT_SUBMODULE = SYNC_STATUS_NOT_SUBMODULE
    ERROR = SYNC_STATUS_ERROR


@dataclass(frozen=True)
class SyncReport:
    """Serializable facts from one parent-pointer sync."""

    status: SyncStatus
    repository: str
    parent_repository: str | None = None
    submodule_path: str | None = None
    commit: str | None = None
    parent_commit: str | None = None
    pull_request_url: str | None = None
    diagnostic: str | None = None

    def as_record(self) -> dict[str, str | None]:
        """Build the JSON-ready record.

        Returns:
            All report fields with nullable values preserved.
        """
        return {
            "status": self.status.value,
            "repository": self.repository,
            "parent_repository": self.parent_repository,
            "submodule_path": self.submodule_path,
            "commit": self.commit,
            "parent_commit": self.parent_commit,
            "pull_request_url": self.pull_request_url,
            "diagnostic": self.diagnostic,
        }


@dataclass(frozen=True)
class _SyncContext:
    repository: Path
    parent_repository: Path
    submodule_path: str
    literal_pathspec: str
    commit: str
    commit_subject: str


class _GitCommandFailure(RuntimeError):
    pass


def _build_child_environment() -> dict[str, str]:
    return {
        each_name: each_content
        for each_name, each_content in os.environ.items()
        if not each_name.upper().startswith("GIT_")
    }


def _execute_git(
    all_arguments: tuple[str, ...],
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            [GIT_EXECUTABLE_NAME, *all_arguments],
            cwd=cwd,
            check=False,
            capture_output=True,
            encoding=UTF8_ENCODING,
            errors=DECODE_ERRORS_POLICY,
            env=_build_child_environment(),
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as error:
        raise _GitCommandFailure(
            GIT_TIMEOUT_MESSAGE_TEMPLATE.format(seconds=GIT_COMMAND_TIMEOUT_SECONDS)
        ) from error
    except OSError as error:
        raise _GitCommandFailure(
            GIT_LAUNCH_FAILURE_MESSAGE_TEMPLATE.format(error=error)
        ) from error


def _git_failure_diagnostic(
    completed_process: subprocess.CompletedProcess[str],
) -> str:
    diagnostic = completed_process.stderr.strip() or completed_process.stdout.strip()
    if diagnostic:
        return diagnostic
    return GIT_EXIT_FAILURE_MESSAGE_TEMPLATE.format(
        status=completed_process.returncode,
        command=GIT_EXECUTABLE_NAME,
    )


def _read_required_git_text(
    all_arguments: tuple[str, ...],
    cwd: Path,
    empty_text_diagnostic: str,
) -> str:
    completed_process = _execute_git(all_arguments, cwd)
    if completed_process.returncode != EXIT_CODE_SUCCESS:
        raise _GitCommandFailure(_git_failure_diagnostic(completed_process))
    git_text = completed_process.stdout.strip()
    if not git_text:
        raise _GitCommandFailure(empty_text_diagnostic)
    return git_text


def lookup_pull_request_url(repository: Path) -> str | None:
    """Read the open pull request URL when GitHub CLI can provide one.

    Args:
        repository: Child repository to query.

    Returns:
        The pull request URL, or None when the lookup is unavailable.
    """
    try:
        completed_process = subprocess.run(
            [GH_EXECUTABLE_NAME, *ALL_GH_PULL_REQUEST_ARGUMENTS],
            cwd=repository,
            check=False,
            capture_output=True,
            encoding=UTF8_ENCODING,
            errors=DECODE_ERRORS_POLICY,
            env=_build_child_environment(),
            timeout=GH_COMMAND_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed_process.returncode != EXIT_CODE_SUCCESS:
        return None
    return completed_process.stdout.strip() or None


def _build_error_report(repository: Path, diagnostic: str) -> SyncReport:
    return SyncReport(
        status=SyncStatus.ERROR,
        repository=repository.resolve().as_posix(),
        diagnostic=diagnostic,
    )


def _resolve_repository_root(repository: Path) -> Path:
    requested_repository = repository.resolve()
    if not requested_repository.is_dir():
        raise _GitCommandFailure(
            REPOSITORY_NOT_DIRECTORY_MESSAGE_TEMPLATE.format(
                path=requested_repository,
            )
        )
    repository_root_text = _read_required_git_text(
        (GIT_REV_PARSE_SUBCOMMAND, GIT_SHOW_TOP_LEVEL_ARGUMENT),
        requested_repository,
        REPOSITORY_RESOLUTION_FAILURE_MESSAGE,
    )
    return Path(repository_root_text).resolve()


def _find_parent_repository(repository: Path) -> Path | None:
    completed_process = _execute_git(
        (GIT_REV_PARSE_SUBCOMMAND, GIT_SHOW_SUPERPROJECT_ARGUMENT),
        repository,
    )
    if completed_process.returncode != EXIT_CODE_SUCCESS:
        raise _GitCommandFailure(_git_failure_diagnostic(completed_process))
    parent_repository_text = completed_process.stdout.strip()
    if not parent_repository_text:
        return None
    return Path(parent_repository_text).resolve()


def _read_child_commit_subject(repository: Path) -> str:
    completed_process = _execute_git(
        (
            GIT_LOG_SUBCOMMAND,
            GIT_LATEST_COMMIT_ARGUMENT,
            GIT_SUBJECT_FORMAT_ARGUMENT,
        ),
        repository,
    )
    if completed_process.returncode != EXIT_CODE_SUCCESS:
        raise _GitCommandFailure(_git_failure_diagnostic(completed_process))
    return completed_process.stdout.strip()


def _build_sync_context(
    repository: Path,
    parent_repository: Path,
) -> _SyncContext:
    try:
        submodule_relative_path = repository.relative_to(parent_repository)
    except ValueError as error:
        raise _GitCommandFailure(SUBMODULE_PATH_FAILURE_MESSAGE) from error
    commit_hash = _read_required_git_text(
        (GIT_REV_PARSE_SUBCOMMAND, GIT_HEAD_REFERENCE),
        repository,
        REPOSITORY_RESOLUTION_FAILURE_MESSAGE,
    )
    submodule_path = submodule_relative_path.as_posix()
    return _SyncContext(
        repository=repository,
        parent_repository=parent_repository,
        submodule_path=submodule_path,
        literal_pathspec=f"{GIT_LITERAL_PATHSPEC_PREFIX}{submodule_path}",
        commit=commit_hash,
        commit_subject=_read_child_commit_subject(repository),
    )


def _stage_parent_pointer(sync_context: _SyncContext) -> None:
    completed_process = _execute_git(
        (GIT_ADD_SUBCOMMAND, GIT_ARGUMENT_SEPARATOR, sync_context.literal_pathspec),
        sync_context.parent_repository,
    )
    if completed_process.returncode != EXIT_CODE_SUCCESS:
        raise _GitCommandFailure(_git_failure_diagnostic(completed_process))


def _parent_pointer_needs_commit(sync_context: _SyncContext) -> bool:
    completed_process = _execute_git(
        (
            GIT_DIFF_SUBCOMMAND,
            GIT_CACHED_ARGUMENT,
            GIT_QUIET_ARGUMENT,
            GIT_ARGUMENT_SEPARATOR,
            sync_context.literal_pathspec,
        ),
        sync_context.parent_repository,
    )
    if completed_process.returncode == EXIT_CODE_SUCCESS:
        return False
    if completed_process.returncode == EXIT_CODE_FAILURE:
        return True
    raise _GitCommandFailure(_git_failure_diagnostic(completed_process))


def _build_parent_commit_message(sync_context: _SyncContext) -> str:
    parent_message = PARENT_COMMIT_MESSAGE_TEMPLATE.format(
        repository_name=sync_context.repository.name,
        commit_hash=sync_context.commit,
    )
    if not sync_context.commit_subject:
        return parent_message
    return SUBMODULE_COMMIT_MESSAGE_TEMPLATE.format(
        parent_message=parent_message,
        subject=sync_context.commit_subject,
    )


def _read_parent_commit(sync_context: _SyncContext) -> str:
    return _read_required_git_text(
        (GIT_REV_PARSE_SUBCOMMAND, GIT_HEAD_REFERENCE),
        sync_context.parent_repository,
        REPOSITORY_RESOLUTION_FAILURE_MESSAGE,
    )


def _commit_parent_pointer(sync_context: _SyncContext) -> str:
    completed_process = _execute_git(
        (
            GIT_COMMIT_SUBCOMMAND,
            GIT_ONLY_ARGUMENT,
            GIT_MESSAGE_ARGUMENT,
            _build_parent_commit_message(sync_context),
            GIT_ARGUMENT_SEPARATOR,
            sync_context.literal_pathspec,
        ),
        sync_context.parent_repository,
    )
    if completed_process.returncode != EXIT_CODE_SUCCESS:
        raise _GitCommandFailure(_git_failure_diagnostic(completed_process))
    return _read_parent_commit(sync_context)


def _report_from_context(
    sync_context: _SyncContext,
    status: SyncStatus,
    parent_commit: str,
) -> SyncReport:
    return SyncReport(
        status=status,
        repository=sync_context.repository.as_posix(),
        parent_repository=sync_context.parent_repository.as_posix(),
        submodule_path=sync_context.submodule_path,
        commit=sync_context.commit,
        parent_commit=parent_commit,
        pull_request_url=lookup_pull_request_url(sync_context.repository),
    )


def _sync_parent_pointer(sync_context: _SyncContext) -> SyncReport:
    _stage_parent_pointer(sync_context)
    if not _parent_pointer_needs_commit(sync_context):
        return _report_from_context(
            sync_context,
            SyncStatus.UNCHANGED,
            _read_parent_commit(sync_context),
        )
    return _report_from_context(
        sync_context,
        SyncStatus.UPDATED,
        _commit_parent_pointer(sync_context),
    )


def sync_repository(repository: Path) -> SyncReport:
    """Record the child commit in its parent repository.

    Args:
        repository: Child repository or a directory inside it.

    Returns:
        The sync status and every path or commit needed for readback.
    """
    requested_repository = repository.resolve()
    try:
        repository_root = _resolve_repository_root(requested_repository)
        parent_repository = _find_parent_repository(repository_root)
        if parent_repository is None:
            return SyncReport(
                status=SyncStatus.NOT_SUBMODULE,
                repository=repository_root.as_posix(),
                pull_request_url=lookup_pull_request_url(repository_root),
            )
        sync_context = _build_sync_context(repository_root, parent_repository)
        return _sync_parent_pointer(sync_context)
    except (_GitCommandFailure, OSError) as error:
        return _build_error_report(requested_repository, str(error))
