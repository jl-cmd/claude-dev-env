from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias

from .config import (
    CHECK_FAILED_EXIT_CODE,
    FAILED_STATUS,
    INCOMPLETE_EXIT_CODE,
    INCOMPLETE_STATUS,
    PASSED_STATUS,
    SUCCESS_EXIT_CODE,
)

CheckStatus: TypeAlias = str
AggregateStatus: TypeAlias = str


@dataclass(frozen=True)
class CheckSpec:
    check_id: str
    command_arguments: tuple[str, ...]
    cwd: str
    timeout_seconds: float
    minimum_tests: int | None = None


@dataclass(frozen=True)
class ExclusionSpec:
    selector: str
    reason: str


@dataclass(frozen=True)
class VerificationManifest:
    version: int
    checks: tuple[CheckSpec, ...]
    exclusions: tuple[ExclusionSpec, ...]


@dataclass(frozen=True)
class CommandCapture:
    exit_code: int | None
    stdout_text: str
    stderr_text: str
    error_kind: str | None
    error_message: str | None


@dataclass(frozen=True)
class CheckLogPaths:
    stdout: Path
    stderr: Path
    collection_stdout: Path
    collection_stderr: Path


@dataclass(frozen=True)
class CheckRecord:
    check_id: str
    status: CheckStatus
    command_arguments: tuple[str, ...]
    cwd: str
    exit_code: int | None
    duration_seconds: float
    stdout_log: Path
    stderr_log: Path
    error_kind: str | None = None
    error_message: str | None = None
    minimum_tests: int | None = None
    collected_tests: int | None = None
    collection_exit_code: int | None = None

    def as_dict(self) -> dict[str, object]:
        """Return the JSON record for this check.

        Returns:
            A JSON-compatible check record using the manifest argv key.
        """
        return {
            "id": self.check_id,
            "status": self.status,
            "argv": list(self.command_arguments),
            "cwd": self.cwd,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "stdout_log": str(self.stdout_log),
            "stderr_log": str(self.stderr_log),
            "error_kind": self.error_kind,
            "error_message": self.error_message,
            "minimum_tests": self.minimum_tests,
            "collected_tests": self.collected_tests,
            "collection_exit_code": self.collection_exit_code,
        }


@dataclass(frozen=True)
class VerificationReport:
    version: int
    repository: Path
    base_revision: str | None
    checks: tuple[CheckRecord, ...]
    exclusions: tuple[ExclusionSpec, ...]
    head_revision: str | None = None
    manifest_digest: str = ""
    is_worktree_clean: bool = False
    is_inputs_unchanged: bool = False
    is_publishable: bool = False

    @property
    def worktree_clean(self) -> bool:
        return self.is_worktree_clean

    @property
    def inputs_unchanged(self) -> bool:
        return self.is_inputs_unchanged

    @property
    def publishable(self) -> bool:
        return self.is_publishable

    @property
    def aggregate_status(self) -> AggregateStatus:
        if any(each_record.status == FAILED_STATUS for each_record in self.checks):
            return FAILED_STATUS
        if any(each_record.status == INCOMPLETE_STATUS for each_record in self.checks):
            return INCOMPLETE_STATUS
        return PASSED_STATUS

    @property
    def exit_code(self) -> int:
        if self.aggregate_status == FAILED_STATUS:
            return CHECK_FAILED_EXIT_CODE
        if self.aggregate_status == INCOMPLETE_STATUS:
            return INCOMPLETE_EXIT_CODE
        return SUCCESS_EXIT_CODE

    def _aggregate_fields(self, all_statuses: list[str]) -> dict[str, object]:
        return {
            "status": self.aggregate_status,
            "total": len(self.checks),
            "passed": all_statuses.count(PASSED_STATUS),
            "failed": all_statuses.count(FAILED_STATUS),
            "incomplete": all_statuses.count(INCOMPLETE_STATUS),
            "exit_code": self.exit_code,
        }

    def as_dict(self) -> dict[str, object]:
        """Return the JSON report for this verification run.

        Returns:
            A JSON-compatible report with aggregate check counts.
        """
        all_statuses = [each_record.status for each_record in self.checks]
        return {
            "version": self.version,
            "schema_version": self.version,
            "repository": str(self.repository),
            "head": self.head_revision,
            "base": self.base_revision,
            "manifest_digest": self.manifest_digest,
            "worktree_clean": self.is_worktree_clean,
            "inputs_unchanged": self.is_inputs_unchanged,
            "publishable": self.is_publishable,
            "checks": [each_record.as_dict() for each_record in self.checks],
            "exclusions": [
                {"selector": each_exclusion.selector, "reason": each_exclusion.reason}
                for each_exclusion in self.exclusions
            ],
            "aggregate": self._aggregate_fields(all_statuses),
            "status": self.aggregate_status,
            "exit_code": self.exit_code,
        }
