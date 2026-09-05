"""Fail-closed orchestration for committed-tree repository checks."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path

from repository_checks import tracked_tree
from repository_checks.claude_md import collect_claude_md_orphan_findings
from repository_checks.config import constants as repository_constants
from repository_checks.env_var_documentation import (
    collect_env_var_documentation_findings,
)
from repository_checks.models import RepositoryCheckReport, RepositoryFinding
from repository_checks.package_inventory import collect_package_inventory_findings
from repository_checks.pytest_testpaths import collect_pytest_testpath_findings
from repository_checks.tracked_secrets import collect_tracked_secret_findings

RepositoryCollector = Callable[[Path, Sequence[str]], list[RepositoryFinding]]


def run_repository_checks(repository_root: Path) -> RepositoryCheckReport:
    """Run every committed-tree check and fail closed on collector errors.

    Args:
        repository_root: Git repository root whose tracked files are scanned.

    Returns:
        Sorted findings and any check identifiers that failed closed.
    """
    try:
        all_tracked_paths = tracked_tree.tracked_relative_paths(repository_root)
    except repository_constants.ALL_FAIL_CLOSED_EXCEPTION_TYPES:
        return RepositoryCheckReport((), repository_constants.ALL_CHECK_IDS)
    all_findings, all_failed_check_ids = _run_collectors(
        repository_root, all_tracked_paths
    )
    return RepositoryCheckReport(
        _sort_findings(all_findings), tuple(all_failed_check_ids)
    )


def _run_collectors(
    repository_root: Path, all_tracked_paths: Sequence[str]
) -> tuple[list[RepositoryFinding], list[str]]:
    all_findings: list[RepositoryFinding] = []
    all_failed_check_ids: list[str] = []
    for each_check_id, each_collector in _all_collectors():
        try:
            all_findings.extend(each_collector(repository_root, all_tracked_paths))
        except repository_constants.ALL_FAIL_CLOSED_EXCEPTION_TYPES:
            all_failed_check_ids.append(each_check_id)
    return all_findings, all_failed_check_ids


def _sort_findings(
    all_findings: list[RepositoryFinding],
) -> tuple[RepositoryFinding, ...]:
    return tuple(
        sorted(
            all_findings,
            key=lambda each_finding: (
                each_finding.check_id,
                each_finding.relative_path,
                each_finding.message,
            ),
        )
    )


def _all_collectors() -> tuple[tuple[str, RepositoryCollector], ...]:
    return (
        (
            repository_constants.CHECK_ID_CLAUDE_MD_ORPHANS,
            collect_claude_md_orphan_findings,
        ),
        (
            repository_constants.CHECK_ID_ENV_VAR_DOCUMENTATION,
            collect_env_var_documentation_findings,
        ),
        (
            repository_constants.CHECK_ID_PACKAGE_INVENTORY,
            collect_package_inventory_findings,
        ),
        (
            repository_constants.CHECK_ID_PYTEST_TESTPATHS,
            collect_pytest_testpath_findings,
        ),
        (
            repository_constants.CHECK_ID_TRACKED_PERSONAL_DATA,
            collect_tracked_secret_findings,
        ),
    )
