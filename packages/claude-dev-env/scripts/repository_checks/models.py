"""Shared report types for committed-tree repository checks."""

from __future__ import annotations

from dataclasses import dataclass

from repository_checks.config.constants import (
    FAILED_CHECK_EXIT_CODE,
    FINDINGS_EXIT_CODE,
    SUCCESS_EXIT_CODE,
)


@dataclass(frozen=True)
class RepositoryFinding:
    """One committed-tree finding with a stable check id and relative path."""

    check_id: str
    relative_path: str
    message: str


@dataclass(frozen=True)
class RepositoryCheckReport:
    """Sorted findings plus check ids whose own execution failed."""

    all_findings: tuple[RepositoryFinding, ...]
    all_failed_check_ids: tuple[str, ...]

    @property
    def exit_code(self) -> int:
        """Return the process status for this report."""
        if self.all_failed_check_ids:
            return FAILED_CHECK_EXIT_CODE
        if self.all_findings:
            return FINDINGS_EXIT_CODE
        return SUCCESS_EXIT_CODE
