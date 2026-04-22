"""Specifications for the root conftest pytest_collectstart/pytest_collectreport pairing.

The root conftest temporarily modifies sys.path while test_sync_ai_rules.py is
being collected and restores it when collection finishes. The matching logic
between collectstart (which captures the snapshot) and collectreport (which
pops it) must be symmetric: if collectstart fires for a given collector, its
paired collectreport must fire for the same collector. These tests exercise
that symmetry across standard and nested nodeids.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

import conftest


SYNC_AI_RULES_TEST_FILENAME = "test_sync_ai_rules.py"
STANDARD_NODEID = f"tests/{SYNC_AI_RULES_TEST_FILENAME}"
NESTED_SUBTREE_NODEID = f"packages/claude-dev-env/tests/{SYNC_AI_RULES_TEST_FILENAME}"


def _make_module_collector(
    nodeid: str, filename: str = SYNC_AI_RULES_TEST_FILENAME
) -> pytest.Module:
    fake_module_collector = MagicMock(spec=pytest.Module)
    fake_module_collector.nodeid = nodeid
    fake_module_collector.path = MagicMock()
    fake_module_collector.path.name = filename
    return fake_module_collector


def _make_collect_report(nodeid: str) -> pytest.CollectReport:
    fake_report = MagicMock(spec=pytest.CollectReport)
    fake_report.nodeid = nodeid
    return fake_report


def _drop_hook_local_directory_from_sys_path() -> None:
    while conftest._HOOK_LOCAL_DIRECTORY_PATH in sys.path:
        sys.path.remove(conftest._HOOK_LOCAL_DIRECTORY_PATH)


@pytest.fixture
def isolated_collect_hook_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conftest, "_pending_sys_path_restores", [])
    monkeypatch.setattr(sys, "path", list(sys.path))


class TestCollectHookSymmetry:
    def should_restore_sys_path_after_standard_tests_nodeid(
        self, isolated_collect_hook_state: None
    ) -> None:
        _drop_hook_local_directory_from_sys_path()
        baseline_sys_path = list(sys.path)

        conftest.pytest_collectstart(_make_module_collector(nodeid=STANDARD_NODEID))
        conftest.pytest_collectreport(_make_collect_report(nodeid=STANDARD_NODEID))

        assert list(sys.path) == baseline_sys_path
        assert conftest._pending_sys_path_restores == []

    def should_restore_sys_path_after_nested_subtree_nodeid(
        self, isolated_collect_hook_state: None
    ) -> None:
        _drop_hook_local_directory_from_sys_path()
        baseline_sys_path = list(sys.path)

        conftest.pytest_collectstart(
            _make_module_collector(nodeid=NESTED_SUBTREE_NODEID)
        )
        conftest.pytest_collectreport(
            _make_collect_report(nodeid=NESTED_SUBTREE_NODEID)
        )

        assert list(sys.path) == baseline_sys_path
        assert conftest._pending_sys_path_restores == []

    def should_not_pop_pending_restore_for_unrelated_collectreport_nodeid(
        self, isolated_collect_hook_state: None
    ) -> None:
        _drop_hook_local_directory_from_sys_path()

        conftest.pytest_collectstart(
            _make_module_collector(nodeid=NESTED_SUBTREE_NODEID)
        )
        pending_restores_before_unrelated_report = list(
            conftest._pending_sys_path_restores
        )

        unrelated_nodeid = "packages/claude-dev-env/hooks/test_other.py"
        conftest.pytest_collectreport(
            _make_collect_report(nodeid=unrelated_nodeid)
        )
        assert (
            conftest._pending_sys_path_restores
            == pending_restores_before_unrelated_report
        )

        conftest.pytest_collectreport(
            _make_collect_report(nodeid=NESTED_SUBTREE_NODEID)
        )
        assert conftest._pending_sys_path_restores == []

    def should_record_nodeid_and_snapshot_together_on_collectstart(
        self, isolated_collect_hook_state: None
    ) -> None:
        _drop_hook_local_directory_from_sys_path()

        conftest.pytest_collectstart(
            _make_module_collector(nodeid=NESTED_SUBTREE_NODEID)
        )

        assert len(conftest._pending_sys_path_restores) == 1
        pending_restore = conftest._pending_sys_path_restores[-1]
        assert pending_restore.matched_module_nodeid == NESTED_SUBTREE_NODEID
        assert isinstance(pending_restore.sys_path_snapshot, list)
