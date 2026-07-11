"""Canonical path-exemption helpers shared between validator hooks.

Single source of truth for CONFIG / TEST / HOOK-INFRASTRUCTURE /
WORKFLOW-REGISTRY / MIGRATION path pattern sets. Both Pre-Write
(``code_rules_enforcer.py``) and pre-push (``magic_value_checks.py``)
scanners must short-circuit on the same file categories; drift between
the two produced the "inconsistent verdicts" bug this module prevents.

Matching is case-insensitive so paths like ``Config/foo.py`` or
``src/Tests/test_x.py`` are treated the same on case-preserving
filesystems (macOS default, Windows NTFS) as on case-sensitive ones.

``is_config_file`` canonical implementation lives in
``hooks/blocking/code_rules_path_utils.py`` and is re-exported here so
both the pre-write gate and the pre-push validator share identical logic.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _ensure_blocking_package_on_path() -> None:
    blocking_directory = str(Path(__file__).resolve().parent.parent / "blocking")
    if blocking_directory not in sys.path:
        sys.path.insert(0, blocking_directory)


_ensure_blocking_package_on_path()

from code_rules_path_utils import is_config_file  # type: ignore[import-not-found] # noqa: E402


TEST_PATH_PATTERNS: frozenset[str] = frozenset(
    {
        "test_",
        "_test.",
        ".spec.",
        "conftest",
        "/tests/",
        "\\tests\\",
        "/tests.py",
        "\\tests.py",
    }
)

HOOK_INFRASTRUCTURE_PATTERNS: frozenset[str] = frozenset(
    {
        "/.claude/hooks/",
        "\\.claude\\hooks\\",
        "\\.claude/hooks/",
    }
)

WORKFLOW_REGISTRY_PATTERNS: frozenset[str] = frozenset(
    {
        "/workflow/",
        "\\workflow\\",
        "_tab.py",
        "/states.py",
        "\\states.py",
        "/modules.py",
        "\\modules.py",
    }
)

MIGRATION_PATH_PATTERNS: frozenset[str] = frozenset(
    {
        "/migrations/",
        "\\migrations\\",
    }
)


def is_test_file(file_path: str) -> bool:
    path_lower = file_path.lower()
    return any(pattern in path_lower for pattern in TEST_PATH_PATTERNS)


def is_hook_infrastructure(file_path: str) -> bool:
    path_normalized = file_path.lower().replace("\\", "/")
    return any(
        pattern.replace("\\", "/") in path_normalized
        for pattern in HOOK_INFRASTRUCTURE_PATTERNS
    )


def is_workflow_registry_file(file_path: str) -> bool:
    path_normalized = file_path.lower().replace("\\", "/")
    return any(
        pattern.replace("\\", "/") in path_normalized
        for pattern in WORKFLOW_REGISTRY_PATTERNS
    )


def is_migration_file(file_path: str) -> bool:
    path_normalized = file_path.lower().replace("\\", "/")
    return any(
        pattern.replace("\\", "/") in path_normalized
        for pattern in MIGRATION_PATH_PATTERNS
    )
