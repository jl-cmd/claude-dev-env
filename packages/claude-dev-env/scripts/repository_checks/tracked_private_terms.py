"""Tracked-file check for private organization names."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from dev_env_scripts_constants.private_term_constants import (
    ALL_PRIVATE_TERM_DIGESTS,
    PRIVATE_TERM_MESSAGE_TEMPLATE,
)
from policy_lint.config import constants as policy_constants
from private_terms import private_term_line_numbers

from repository_checks.config import constants as repository_constants
from repository_checks.models import RepositoryFinding


def _read_text_or_none(absolute_path: Path) -> str | None:
    if not absolute_path.is_file():
        return None
    try:
        return absolute_path.read_text(encoding=policy_constants.UTF8_ENCODING)
    except UnicodeDecodeError:
        return None


def collect_tracked_private_term_findings(
    repository_root: Path, all_tracked_paths: Sequence[str]
) -> list[RepositoryFinding]:
    """Return one finding for each tracked line that names a private organization.

    Args:
        repository_root: Git repository root.
        all_tracked_paths: Repository-relative tracked paths.

    Returns:
        Findings that carry the path and line number, never the name.
    """
    all_findings: list[RepositoryFinding] = []
    for each_relative_path in all_tracked_paths:
        if (content := _read_text_or_none(repository_root / each_relative_path)) is None:
            continue
        posix_relative_path = each_relative_path.replace(
            repository_constants.WINDOWS_PATH_SEPARATOR, policy_constants.PATH_SEPARATOR
        )
        all_findings.extend(
            RepositoryFinding(
                repository_constants.CHECK_ID_TRACKED_PRIVATE_TERMS,
                posix_relative_path,
                PRIVATE_TERM_MESSAGE_TEMPLATE.format(line_number=each_line_number),
            )
            for each_line_number in private_term_line_numbers(
                content, ALL_PRIVATE_TERM_DIGESTS
            )
        )
    return all_findings
