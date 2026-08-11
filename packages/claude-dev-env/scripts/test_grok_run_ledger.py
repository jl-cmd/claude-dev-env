"""Behavioral tests for the host-neutral Grok run ledger."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from dev_env_scripts_constants.grok_run_ledger_constants import (  # noqa: E402
    TASK_STATUS_ADVISOR_BLOCKED,
    TASK_STATUS_COMPLETED,
    TASK_STATUS_PENDING,
    TASK_STATUS_PENDING_REVIEW,
)
from grok_run_ledger import GrokRunLedger, is_legal_status  # noqa: E402


def test_register_task_persists_atomically(tmp_path: Path) -> None:
    ledger = GrokRunLedger(tmp_path)
    ledger.register_task(task_id="O-04", all_dependencies=())
    reloaded = GrokRunLedger(tmp_path)
    record = reloaded.get_task("O-04")
    assert record.status == TASK_STATUS_PENDING
    assert is_legal_status(record.status)
    payload = json.loads((tmp_path / "grok-run-ledger.json").read_text(encoding="utf-8"))
    assert payload["tasks"][0]["task_id"] == "O-04"


def test_dependencies_block_dispatch(tmp_path: Path) -> None:
    ledger = GrokRunLedger(tmp_path)
    ledger.register_task(task_id="dep", all_dependencies=())
    ledger.register_task(task_id="child", all_dependencies=("dep",))
    assert ledger.can_dispatch("child") is False
    with pytest.raises(ValueError, match="dependencies"):
        ledger.mark_in_progress(
            task_id="child",
            owner_id="w1",
            advisor_session_id="s1",
            base_sha="aaa",
        )
    ledger.mark_in_progress(
        task_id="dep", owner_id="w0", advisor_session_id="s0", base_sha="aaa"
    )
    ledger.mark_completed(
        task_id="dep",
        reviewed_head="bbb",
        all_changed_paths=(),
        advisor_verdict="ENDORSE",
        all_acceptance_mapping={},
        all_test_evidence=["ok"],
    )
    assert ledger.can_dispatch("child") is True


def test_one_live_owner_and_unique_advisor_session(tmp_path: Path) -> None:
    ledger = GrokRunLedger(tmp_path)
    ledger.register_task(task_id="a", all_dependencies=())
    ledger.register_task(task_id="b", all_dependencies=())
    ledger.mark_in_progress(
        task_id="a", owner_id="owner", advisor_session_id="sess-a", base_sha="1"
    )
    with pytest.raises(ValueError, match="owner already live"):
        ledger.mark_in_progress(
            task_id="b", owner_id="owner", advisor_session_id="sess-b", base_sha="1"
        )
    with pytest.raises(ValueError, match="advisor session already bound"):
        ledger.mark_in_progress(
            task_id="b", owner_id="other", advisor_session_id="sess-a", base_sha="1"
        )


def test_snapshot_drift_moves_to_pending_review(tmp_path: Path) -> None:
    ledger = GrokRunLedger(tmp_path)
    ledger.register_task(task_id="t", all_dependencies=())
    ledger.mark_in_progress(
        task_id="t", owner_id="w", advisor_session_id="s", base_sha="base"
    )
    record = ledger.invalidate_on_snapshot_drift(task_id="t", current_sha="drifted")
    assert record.status == TASK_STATUS_PENDING_REVIEW
    assert record.owner_id is None


def test_advisor_blocked_terminal(tmp_path: Path) -> None:
    ledger = GrokRunLedger(tmp_path)
    ledger.register_task(task_id="t", all_dependencies=())
    ledger.mark_in_progress(
        task_id="t", owner_id="w", advisor_session_id="s", base_sha="base"
    )
    record = ledger.mark_advisor_blocked(task_id="t", reason="bind failed")
    assert record.status == TASK_STATUS_ADVISOR_BLOCKED
    assert "bind failed" in record.test_evidence[0]


def test_completed_records_acceptance_and_head(tmp_path: Path) -> None:
    ledger = GrokRunLedger(tmp_path)
    ledger.register_task(task_id="t", all_dependencies=())
    ledger.mark_in_progress(
        task_id="t", owner_id="w", advisor_session_id="s", base_sha="base"
    )
    record = ledger.mark_completed(
        task_id="t",
        reviewed_head="head",
        all_changed_paths=("a.py",),
        advisor_verdict="ENDORSE",
        all_acceptance_mapping={"criterion": "evidence"},
        all_test_evidence=["pytest -q"],
    )
    assert record.status == TASK_STATUS_COMPLETED
    assert record.reviewed_head == "head"
    assert record.changed_paths == ("a.py",)
