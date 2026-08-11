#!/usr/bin/env python3
"""Host-neutral file-backed ledger for Grok orchestration task state.

Records every delegated unit before dispatch, enforces one live owner and one
unique advisor session per in-progress task, blocks on unfinished dependencies,
and reopens tasks when the base snapshot drifts.

::

    ledger = GrokRunLedger(run_state_directory)
    ledger.register_task(task_id="O-04", dependencies=())
    ledger.mark_in_progress(
        task_id="O-04",
        owner_id="worker-1",
        advisor_session_id="sess-1",
        base_sha="abc",
    )
    ok: task status becomes in_progress with that owner and session
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from dev_env_scripts_constants.grok_run_ledger_constants import (
    ALL_LEGAL_TASK_STATUSES,
    JSON_INDENT,
    LEDGER_FILENAME,
    LEDGER_SCHEMA_VERSION,
    TASK_STATUS_ADVISOR_BLOCKED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_IN_PROGRESS,
    TASK_STATUS_PENDING,
    TASK_STATUS_PENDING_REVIEW,
    TEMPORARY_LEDGER_PREFIX,
    TEMPORARY_LEDGER_SUFFIX,
    UTF8_ENCODING,
)


@dataclass
class LedgerTaskRecord:
    """One delegated unit tracked in the run ledger."""

    task_id: str
    status: str = TASK_STATUS_PENDING
    dependencies: tuple[str, ...] = ()
    owner_id: str | None = None
    advisor_session_id: str | None = None
    advisor_verdict: str | None = None
    base_sha: str | None = None
    reviewed_head: str | None = None
    changed_paths: tuple[str, ...] = ()
    acceptance_mapping: dict[str, str] = field(default_factory=dict)
    test_evidence: list[str] = field(default_factory=list)


class GrokRunLedger:
    """Atomic file-backed ledger: register_task, get_task, can_dispatch, mark_in_progress, mark_completed, mark_advisor_blocked, invalidate_on_snapshot_drift, all_tasks."""

    def __init__(self, run_state_directory: Path) -> None:
        self.run_state_directory = Path(run_state_directory)
        self.ledger_path = self.run_state_directory / LEDGER_FILENAME
        self._task_by_id: dict[str, LedgerTaskRecord] = {}
        self.run_state_directory.mkdir(parents=True, exist_ok=True)
        if self.ledger_path.is_file():
            self._load()

    def _load(self) -> None:
        payload = json.loads(self.ledger_path.read_text(encoding=UTF8_ENCODING))
        for each_task in payload.get("tasks", []):
            record = LedgerTaskRecord(
                task_id=each_task["task_id"],
                status=each_task["status"],
                dependencies=tuple(each_task.get("dependencies") or ()),
                owner_id=each_task.get("owner_id"),
                advisor_session_id=each_task.get("advisor_session_id"),
                advisor_verdict=each_task.get("advisor_verdict"),
                base_sha=each_task.get("base_sha"),
                reviewed_head=each_task.get("reviewed_head"),
                changed_paths=tuple(each_task.get("changed_paths") or ()),
                acceptance_mapping=dict(each_task.get("acceptance_mapping") or {}),
                test_evidence=list(each_task.get("test_evidence") or []),
            )
            self._task_by_id[record.task_id] = record

    def _atomic_write(self) -> None:
        document = {
            "schema_version": LEDGER_SCHEMA_VERSION,
            "tasks": [
                {
                    **asdict(each_record),
                    "dependencies": list(each_record.dependencies),
                    "changed_paths": list(each_record.changed_paths),
                }
                for each_record in sorted(
                    self._task_by_id.values(), key=lambda item: item.task_id
                )
            ],
        }
        encoded = json.dumps(document, indent=JSON_INDENT) + "\n"
        file_descriptor, temporary_path = tempfile.mkstemp(
            dir=self.run_state_directory,
            prefix=TEMPORARY_LEDGER_PREFIX,
            suffix=TEMPORARY_LEDGER_SUFFIX,
        )
        try:
            with os.fdopen(file_descriptor, "w", encoding=UTF8_ENCODING) as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.ledger_path)
        except (OSError, TypeError, ValueError):
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)
            raise

    def register_task(
        self,
        *,
        task_id: str,
        all_dependencies: tuple[str, ...] = (),
    ) -> LedgerTaskRecord:
        """Record a delegated unit before dispatch.

        Args:
            task_id: Stable task identifier.
            all_dependencies: Task ids that must complete before dispatch.

        Returns:
            The registered pending task record.

        Raises:
            ValueError: When the task id already exists.
        """
        if task_id in self._task_by_id:
            raise ValueError(f"task already registered: {task_id}")
        record = LedgerTaskRecord(
            task_id=task_id,
            status=TASK_STATUS_PENDING,
            dependencies=all_dependencies,
        )
        self._task_by_id[task_id] = record
        self._atomic_write()
        return record

    def get_task(self, task_id: str) -> LedgerTaskRecord:
        """Return one task record.

        Args:
            task_id: Stable task identifier.

        Returns:
            The stored task record.

        Raises:
            KeyError: When the task id is unknown.
        """
        return self._task_by_id[task_id]

    def can_dispatch(self, task_id: str) -> bool:
        """Return whether every dependency has completed successfully.

        Args:
            task_id: Task to evaluate.

        Returns:
            True when every dependency is ``completed``.
        """
        record = self.get_task(task_id)
        for each_dependency in record.dependencies:
            dependency_record = self._task_by_id.get(each_dependency)
            if dependency_record is None:
                return False
            if dependency_record.status != TASK_STATUS_COMPLETED:
                return False
        return True

    def mark_in_progress(
        self,
        *,
        task_id: str,
        owner_id: str,
        advisor_session_id: str,
        base_sha: str,
    ) -> LedgerTaskRecord:
        """Assign one owner and unique advisor session and start the task.

        Args:
            task_id: Task to start.
            owner_id: Live owner identity.
            advisor_session_id: Unique advisor session for this worker.
            base_sha: Snapshot SHA at dispatch.

        Returns:
            The updated task record.

        Raises:
            ValueError: When dispatch is blocked, another owner is live, the
                advisor session is reused, or status is illegal.
        """
        if not self.can_dispatch(task_id):
            raise ValueError(f"dependencies incomplete for {task_id}")
        for each_record in self._task_by_id.values():
            if (
                each_record.status == TASK_STATUS_IN_PROGRESS
                and each_record.owner_id == owner_id
                and each_record.task_id != task_id
            ):
                raise ValueError(f"owner already live on {each_record.task_id}")
            if (
                each_record.advisor_session_id == advisor_session_id
                and each_record.task_id != task_id
            ):
                raise ValueError(
                    f"advisor session already bound to {each_record.task_id}"
                )
        record = self.get_task(task_id)
        if record.status not in {TASK_STATUS_PENDING, TASK_STATUS_PENDING_REVIEW}:
            raise ValueError(f"cannot start task from status {record.status}")
        record.status = TASK_STATUS_IN_PROGRESS
        record.owner_id = owner_id
        record.advisor_session_id = advisor_session_id
        record.base_sha = base_sha
        self._atomic_write()
        return record

    def mark_completed(
        self,
        *,
        task_id: str,
        reviewed_head: str,
        all_changed_paths: tuple[str, ...],
        advisor_verdict: str,
        all_acceptance_mapping: dict[str, str],
        all_test_evidence: list[str],
    ) -> LedgerTaskRecord:
        """Record successful terminal state for an in-progress task.

        Args:
            task_id: Task to complete.
            reviewed_head: Final reviewed commit SHA.
            all_changed_paths: Paths changed by the worker.
            advisor_verdict: Opening advisor signal (for example ENDORSE).
            all_acceptance_mapping: Acceptance criterion to evidence map.
            all_test_evidence: Commands or artifacts proving tests.

        Returns:
            The completed task record.

        Raises:
            ValueError: When the task is not in progress.
        """
        record = self.get_task(task_id)
        if record.status != TASK_STATUS_IN_PROGRESS:
            raise ValueError(f"cannot complete task from status {record.status}")
        record.status = TASK_STATUS_COMPLETED
        record.reviewed_head = reviewed_head
        record.changed_paths = all_changed_paths
        record.advisor_verdict = advisor_verdict
        record.acceptance_mapping = dict(all_acceptance_mapping)
        record.test_evidence = list(all_test_evidence)
        self._atomic_write()
        return record

    def mark_advisor_blocked(self, *, task_id: str, reason: str) -> LedgerTaskRecord:
        """Stop a task because the advisor path failed closed.

        Args:
            task_id: Task to block.
            reason: Short failure reason stored in test evidence.

        Returns:
            The blocked task record.
        """
        record = self.get_task(task_id)
        record.status = TASK_STATUS_ADVISOR_BLOCKED
        record.test_evidence = [reason]
        self._atomic_write()
        return record

    def invalidate_on_snapshot_drift(
        self,
        *,
        task_id: str,
        current_sha: str,
    ) -> LedgerTaskRecord:
        """Move a task back to pending review when the base snapshot drifts.

        Args:
            task_id: Task to invalidate.
            current_sha: Live SHA compared to the recorded base.

        Returns:
            The updated task record (unchanged when SHAs match).
        """
        record = self.get_task(task_id)
        if record.base_sha is None or record.base_sha == current_sha:
            return record
        record.status = TASK_STATUS_PENDING_REVIEW
        record.owner_id = None
        self._atomic_write()
        return record

    def all_tasks(self) -> tuple[LedgerTaskRecord, ...]:
        """Return every task record sorted by task id."""
        return tuple(
            sorted(self._task_by_id.values(), key=lambda item: item.task_id)
        )


def is_legal_status(status: str) -> bool:
    """Return whether a status token is in the legal set."""
    return status in ALL_LEGAL_TASK_STATUSES
