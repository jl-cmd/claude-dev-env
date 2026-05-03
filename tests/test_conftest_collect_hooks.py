"""Specifications for the root conftest pytest_collectstart/pytest_collectreport pairing.

The root conftest temporarily modifies sys.path while test_sync_ai_rules.py is
being collected and restores it when collection finishes. The matching logic
between collectstart (which captures the snapshot) and collectreport (which
pops it) must be symmetric: if collectstart fires for a given collector, its
paired collectreport must fire for the same collector. These tests exercise
that symmetry across standard and nested nodeids.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest


REPOSITORY_ROOT_PATH = Path(__file__).resolve().parent.parent
ROOT_CONFTEST_PATH = REPOSITORY_ROOT_PATH / "conftest.py"
ROOT_CONFTEST_MODULE_NAME = "_root_conftest_under_test"


def _load_root_conftest_module():
    module_spec = importlib.util.spec_from_file_location(
        ROOT_CONFTEST_MODULE_NAME, ROOT_CONFTEST_PATH
    )
    assert module_spec is not None, f"cannot locate root conftest at {ROOT_CONFTEST_PATH}"
    loaded_module = importlib.util.module_from_spec(module_spec)
    assert module_spec.loader is not None
    module_spec.loader.exec_module(loaded_module)
    return loaded_module


conftest = _load_root_conftest_module()


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

    def should_remove_shared_pr_loop_scripts_from_sys_path_for_sync_ai_rules(
        self, isolated_collect_hook_state: None
    ) -> None:
        leaked_shared_scripts_entry = str(
            conftest._SHARED_PR_LOOP_SCRIPTS_DIRECTORY_PATH.resolve()
        )
        sys.path.insert(0, leaked_shared_scripts_entry)

        conftest.pytest_collectstart(
            _make_module_collector(nodeid=STANDARD_NODEID)
        )

        assert leaked_shared_scripts_entry not in sys.path, (
            "sync_ai_rules collection must evict the shared-scripts sys.path entry "
            "so `from config import ...` resolves to the repository's top-level "
            "config/ package, not _shared/pr-loop/scripts/config/"
        )

    def should_remove_pr_converge_scripts_from_sys_path_for_git_hooks_collection(
        self, isolated_collect_hook_state: None
    ) -> None:
        leaked_pr_converge_entry = str(
            conftest._PR_CONVERGE_SCRIPTS_DIRECTORY_PATH.resolve()
        )
        sys.path.insert(0, leaked_pr_converge_entry)

        git_hooks_test_file_path = (
            conftest._GIT_HOOKS_DIRECTORY_PATH / "test_example_hook.py"
        )
        fake_git_hooks_collector = MagicMock(spec=pytest.Module)
        fake_git_hooks_collector.nodeid = (
            "packages/claude-dev-env/hooks/git-hooks/test_example_hook.py"
        )
        fake_git_hooks_collector.path = git_hooks_test_file_path

        conftest.pytest_collectstart(fake_git_hooks_collector)

        assert leaked_pr_converge_entry not in sys.path, (
            "git-hooks collection must evict the pr-converge scripts sys.path entry "
            "so `from config import ...` resolves to the flat git-hooks config, not "
            "skills/pr-converge/scripts/config/"
        )

    def should_remove_pr_converge_scripts_from_sys_path_for_shared_pr_loop_collection(
        self, isolated_collect_hook_state: None
    ) -> None:
        leaked_pr_converge_entry = str(
            conftest._PR_CONVERGE_SCRIPTS_DIRECTORY_PATH.resolve()
        )
        sys.path.insert(0, leaked_pr_converge_entry)

        shared_scripts_test_file_path = (
            conftest._SHARED_PR_LOOP_SCRIPTS_DIRECTORY_PATH
            / "tests"
            / "test_gh_util.py"
        )
        fake_shared_scripts_collector = MagicMock(spec=pytest.Module)
        fake_shared_scripts_collector.nodeid = (
            "packages/claude-dev-env/_shared/pr-loop/scripts/tests/test_gh_util.py"
        )
        fake_shared_scripts_collector.path = shared_scripts_test_file_path

        conftest.pytest_collectstart(fake_shared_scripts_collector)

        assert leaked_pr_converge_entry not in sys.path, (
            "shared pr-loop scripts collection must evict the pr-converge scripts "
            "sys.path entry so `from config import ...` resolves to "
            "_shared/pr-loop/scripts/config/, not skills/pr-converge/scripts/config/"
        )

    def should_remove_shared_pr_loop_scripts_from_sys_path_for_pr_converge_collection(
        self, isolated_collect_hook_state: None
    ) -> None:
        leaked_shared_scripts_entry = str(
            conftest._SHARED_PR_LOOP_SCRIPTS_DIRECTORY_PATH.resolve()
        )
        sys.path.insert(0, leaked_shared_scripts_entry)

        pr_converge_test_file_path = (
            conftest._PR_CONVERGE_SCRIPTS_DIRECTORY_PATH
            / "tests"
            / "test_pr_converge.py"
        )
        fake_pr_converge_collector = MagicMock(spec=pytest.Module)
        fake_pr_converge_collector.nodeid = (
            "packages/claude-dev-env/skills/pr-converge/scripts/tests/test_pr_converge.py"
        )
        fake_pr_converge_collector.path = pr_converge_test_file_path

        conftest.pytest_collectstart(fake_pr_converge_collector)

        assert leaked_shared_scripts_entry not in sys.path, (
            "pr-converge scripts collection must evict the shared pr-loop scripts "
            "sys.path entry so `from config import ...` resolves to "
            "skills/pr-converge/scripts/config/, not _shared/pr-loop/scripts/config/"
        )
