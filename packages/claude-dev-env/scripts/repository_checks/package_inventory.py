"""Package inventory checks for committed trees."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from types import ModuleType

from policy_lint.config.constants import PATH_SEPARATOR, UTF8_ENCODING

from repository_checks.config.constants import (
    ALL_ARCHIVED_SKILL_DIRECTORY_SEGMENTS,
    CHECK_ID_PACKAGE_INVENTORY,
    PACKAGE_INVENTORY_CONSTANTS_MODULE_NAME,
    PACKAGE_INVENTORY_DETECTION_MODULE_NAME,
    PACKAGE_INVENTORY_MESSAGE_TEMPLATE,
    WINDOWS_PATH_SEPARATOR,
)
from repository_checks.hook_modules import load_hooks_module
from repository_checks.models import RepositoryFinding


def collect_package_inventory_findings(
    repository_root: Path, all_tracked_paths: Sequence[str]
) -> list[RepositoryFinding]:
    """Return tracked production files missing from package inventories.

    Args:
        repository_root: Git repository root.
        all_tracked_paths: Repository-relative tracked paths.

    Returns:
        Findings for production files absent from their inventories.
    """
    detection = load_hooks_module(PACKAGE_INVENTORY_DETECTION_MODULE_NAME)
    inventory_constants = load_hooks_module(PACKAGE_INVENTORY_CONSTANTS_MODULE_NAME)
    all_findings: list[RepositoryFinding] = []
    for each_relative_path in all_tracked_paths:
        maybe_finding = find_inventory_finding_for_path(
            repository_root,
            each_relative_path,
            detection,
            inventory_constants,
        )
        if maybe_finding is not None:
            all_findings.append(maybe_finding)
    return all_findings


def find_inventory_finding_for_path(
    repository_root: Path,
    relative_path: str,
    detection: ModuleType,
    inventory_constants: ModuleType,
) -> RepositoryFinding | None:
    """Return an inventory finding for one tracked production file.

    Args:
        repository_root: Git repository root.
        relative_path: Repository-relative production path.
        detection: Existing inventory detector module.
        inventory_constants: Existing detector constants module.

    Returns:
        The finding when the file is missing from its inventory.
    """
    if _is_archived_skill_path(relative_path):
        return None
    absolute_path = repository_root / relative_path
    if not absolute_path.is_file():
        return None
    if not detection.is_inventoried_production_file(str(absolute_path)):
        return None
    _require_readable_inventory_documents(absolute_path.parent, inventory_constants)
    if detection.find_stale_inventory(str(absolute_path)) is None:
        return None
    return _build_finding(relative_path)


def _build_finding(relative_path: str) -> RepositoryFinding:
    return RepositoryFinding(
        CHECK_ID_PACKAGE_INVENTORY,
        relative_path.replace(WINDOWS_PATH_SEPARATOR, PATH_SEPARATOR),
        PACKAGE_INVENTORY_MESSAGE_TEMPLATE,
    )


def _is_archived_skill_path(relative_path: str) -> bool:
    all_path_segments = relative_path.replace(
        WINDOWS_PATH_SEPARATOR, PATH_SEPARATOR
    ).split(PATH_SEPARATOR)
    segment_count = len(ALL_ARCHIVED_SKILL_DIRECTORY_SEGMENTS)
    last_start_index = len(all_path_segments) - segment_count
    for each_start_index in range(max(last_start_index + 1, 0)):
        compared_segments = tuple(
            all_path_segments[each_start_index : each_start_index + segment_count]
        )
        if compared_segments == ALL_ARCHIVED_SKILL_DIRECTORY_SEGMENTS:
            return True
    return False


def _require_readable_inventory_documents(
    package_directory: Path, inventory_constants: ModuleType
) -> None:
    for each_inventory_name in inventory_constants.ALL_INVENTORY_DOCUMENT_NAMES:
        inventory_path = package_directory / each_inventory_name
        if not inventory_path.is_file():
            continue
        inventory_path.read_text(encoding=UTF8_ENCODING)
    if package_directory.name != inventory_constants.SCRIPTS_SUBDIRECTORY_NAME:
        return
    skill_inventory_path = (
        package_directory.parent / inventory_constants.SKILL_INVENTORY_DOCUMENT_NAME
    )
    if not skill_inventory_path.is_file():
        return
    skill_inventory_path.read_text(encoding=UTF8_ENCODING)
