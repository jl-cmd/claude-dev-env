"""Named constants for the host-neutral Grok run ledger and patch artifacts."""

from __future__ import annotations

LEDGER_SCHEMA_VERSION: str = "1.0.0"
"""Schema version stamped on every ledger document and task record."""

LEDGER_FILENAME: str = "grok-run-ledger.json"
"""Default ledger filename under a run-state directory."""

PATCH_MANIFEST_FILENAME: str = "patch-manifest.json"
"""Default patch-manifest filename under a run-state directory."""

TASK_STATUS_PENDING: str = "pending"
"""Task is recorded and waiting for dispatch."""

TASK_STATUS_IN_PROGRESS: str = "in_progress"
"""Task has exactly one live owner and is being worked."""

TASK_STATUS_COMPLETED: str = "completed"
"""Task reached a successful terminal state."""

TASK_STATUS_ADVISOR_BLOCKED: str = "advisor_blocked"
"""Task stopped because the advisor bind or verdict failed closed."""

TASK_STATUS_PENDING_REVIEW: str = "pending_review"
"""Task was invalidated by snapshot drift and needs re-review."""

ALL_LEGAL_TASK_STATUSES: frozenset[str] = frozenset(
    {
        TASK_STATUS_PENDING,
        TASK_STATUS_IN_PROGRESS,
        TASK_STATUS_COMPLETED,
        TASK_STATUS_ADVISOR_BLOCKED,
        TASK_STATUS_PENDING_REVIEW,
    }
)
"""Every legal task status the ledger accepts."""

UTF8_ENCODING: str = "utf-8"
"""Text encoding for ledger and patch-manifest files."""

JSON_INDENT: int = 2
"""Indent width for pretty-printed ledger and patch-manifest JSON."""

TEMPORARY_LEDGER_PREFIX: str = ".ledger-"
"""Prefix for atomic ledger temp files before replace."""

TEMPORARY_LEDGER_SUFFIX: str = ".tmp"
"""Suffix for atomic ledger temp files before replace."""
