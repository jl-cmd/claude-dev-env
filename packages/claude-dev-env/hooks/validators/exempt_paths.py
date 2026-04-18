"""Canonical path-exemption helpers shared between validator hooks.

Single source of truth for CONFIG / TEST / HOOK-INFRASTRUCTURE /
WORKFLOW-REGISTRY / MIGRATION path pattern sets. Both Pre-Write
(``code-rules-enforcer.py``) and pre-push (``magic_value_checks.py``)
scanners must short-circuit on the same file categories; drift between
the two produced the "inconsistent verdicts" bug this module prevents.

Matching is case-insensitive so paths like ``Config/foo.py`` or
``src/Tests/test_x.py`` are treated the same on case-preserving
filesystems (macOS default, Windows NTFS) as on case-sensitive ones.
"""

from __future__ import annotations


CONFIG_PATH_PATTERNS: frozenset[str] = frozenset(
    {
        "config/",
        "config\\",
        "/config.",
        "\\config.",
        "settings.py",
    }
)

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


def is_config_file(file_path: str) -> bool:
    path_lower = file_path.lower()
    return any(pattern in path_lower for pattern in CONFIG_PATH_PATTERNS)


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
