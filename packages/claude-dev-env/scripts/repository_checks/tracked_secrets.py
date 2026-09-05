"""Tracked-secret checks for committed trees."""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

from policy_lint.config import constants as policy_constants

from repository_checks.config import constants as repository_constants
from repository_checks.hook_modules import load_hooks_module
from repository_checks.models import RepositoryFinding


def collect_tracked_secret_findings(
    repository_root: Path, all_tracked_paths: Sequence[str]
) -> list[RepositoryFinding]:
    """Return non-exempt secrets found in tracked UTF-8 files.

    Args:
        repository_root: Git repository root.
        all_tracked_paths: Repository-relative tracked paths.

    Returns:
        Findings with redacted previews for non-exempt secrets.
    """
    scanner = load_hooks_module(repository_constants.PII_SCANNER_MODULE_NAME)
    exemption = load_hooks_module(repository_constants.REPOSITORY_EXEMPTION_MODULE_NAME)
    all_allowlisted_literals = exemption.repository_allowlisted_values(repository_root)
    all_findings: list[RepositoryFinding] = []
    for each_relative_path in all_tracked_paths:
        all_findings.extend(
            _find_secrets_for_path(
                repository_root,
                each_relative_path,
                scanner,
                all_allowlisted_literals,
            )
        )
    return all_findings


def _find_secrets_for_path(
    repository_root: Path,
    relative_path: str,
    scanner: ModuleType,
    all_allowlisted_literals: frozenset[str],
) -> list[RepositoryFinding]:
    posix_relative_path = relative_path.replace(
        repository_constants.WINDOWS_PATH_SEPARATOR,
        policy_constants.PATH_SEPARATOR,
    )
    if scanner.is_path_exempt_from_pii_scan(posix_relative_path):
        return []
    maybe_content = _read_utf8_text(
        repository_root,
        repository_root / relative_path,
    )
    if maybe_content is None:
        return []
    return _find_secret_matches(
        posix_relative_path,
        maybe_content,
        scanner,
        all_allowlisted_literals,
    )


def _find_secret_matches(
    posix_relative_path: str,
    content: str,
    scanner: ModuleType,
    all_allowlisted_literals: frozenset[str],
) -> list[RepositoryFinding]:
    return [
        _build_finding(
            posix_relative_path,
            category=each_match.category,
            preview=each_match.preview,
        )
        for each_match in scanner.scan_text_for_pii(content)
        if _should_report_match(
            posix_relative_path,
            each_match.category,
            each_match.matched_text,
            all_allowlisted_literals,
        )
    ]


def _read_utf8_text(repository_root: Path, absolute_path: Path) -> str | None:
    if not absolute_path.is_file():
        return None
    _require_path_inside_repository(repository_root, absolute_path)
    try:
        return absolute_path.read_text(encoding=policy_constants.UTF8_ENCODING)
    except UnicodeDecodeError:
        return None


def _require_path_inside_repository(repository_root: Path, absolute_path: Path) -> None:
    resolved_repository_root = repository_root.resolve(strict=True)
    resolved_absolute_path = absolute_path.resolve(strict=True)
    try:
        resolved_absolute_path.relative_to(resolved_repository_root)
    except ValueError as e:
        raise OSError(absolute_path) from e


def _build_finding(
    posix_relative_path: str, category: str, preview: str
) -> RepositoryFinding:
    return RepositoryFinding(
        repository_constants.CHECK_ID_TRACKED_PERSONAL_DATA,
        posix_relative_path,
        repository_constants.TRACKED_MATCH_MESSAGE_TEMPLATE.format(
            category=category,
            preview=preview,
        ),
    )


def _should_report_match(
    posix_relative_path: str,
    category: str,
    matched_text: str,
    all_allowlisted_literals: frozenset[str],
) -> bool:
    exact_exemption_identity = (
        posix_relative_path,
        category,
        _secret_digest(matched_text),
    )
    if (
        exact_exemption_identity
        in repository_constants.ALL_TRACKED_SECRET_EXACT_EXEMPTIONS
    ):
        return False
    return matched_text not in all_allowlisted_literals


def _secret_digest(matched_text: str) -> str:
    return hashlib.sha256(
        matched_text.encode(policy_constants.UTF8_ENCODING)
    ).hexdigest()
