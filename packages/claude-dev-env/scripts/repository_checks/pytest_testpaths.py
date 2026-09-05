"""Pytest testpath checks for committed trees."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

import tomllib
from policy_lint.config import constants as policy_constants

from repository_checks.config import constants as repository_constants
from repository_checks.hook_modules import load_hooks_module
from repository_checks.models import RepositoryFinding


def collect_pytest_testpath_findings(
    repository_root: Path, all_tracked_paths: Sequence[str]
) -> list[RepositoryFinding]:
    """Return tracked tests outside explicit package testpaths.

    Args:
        repository_root: Git repository root.
        all_tracked_paths: Repository-relative tracked paths.

    Returns:
        Findings for tests excluded by their package testpaths.
    """
    pytest_module = load_hooks_module(repository_constants.PYTEST_TESTPATHS_MODULE_NAME)
    all_findings: list[RepositoryFinding] = []
    for each_relative_path in all_tracked_paths:
        maybe_finding = _find_testpath_finding(
            repository_root, each_relative_path, pytest_module
        )
        if maybe_finding is not None:
            all_findings.append(maybe_finding)
    return all_findings


def _find_testpath_finding(
    repository_root: Path,
    relative_path: str,
    pytest_module: ModuleType,
) -> RepositoryFinding | None:
    if not pytest_module.is_test_file(relative_path):
        return None
    absolute_path = repository_root / relative_path
    if not absolute_path.is_file():
        return None
    _require_readable_inputs(absolute_path, repository_root)
    if pytest_module.find_unregistered_test_directory(str(absolute_path)) is None:
        return None
    return RepositoryFinding(
        repository_constants.CHECK_ID_PYTEST_TESTPATHS,
        _to_posix_path(relative_path),
        repository_constants.PYTEST_TESTPATH_MESSAGE_TEMPLATE,
    )


def _to_posix_path(relative_path: str) -> str:
    return relative_path.replace(
        repository_constants.WINDOWS_PATH_SEPARATOR,
        policy_constants.PATH_SEPARATOR,
    )


def _require_readable_inputs(test_file: Path, repository_root: Path) -> None:
    test_file.read_bytes()
    resolved_repository_root = repository_root.resolve()
    for each_directory in test_file.parents:
        if not _is_inside_repository(each_directory, resolved_repository_root):
            break
        pyproject_path = each_directory / repository_constants.PYPROJECT_FILENAME
        if not pyproject_path.is_file():
            continue
        tomllib.loads(pyproject_path.read_text(encoding=policy_constants.UTF8_ENCODING))


def _is_inside_repository(directory: Path, resolved_repository_root: Path) -> bool:
    try:
        directory.resolve().relative_to(resolved_repository_root)
    except ValueError:
        return False
    return True
