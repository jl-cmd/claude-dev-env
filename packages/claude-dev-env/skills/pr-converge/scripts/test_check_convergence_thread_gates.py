"""Behavioral tests for the review-thread and pending-reviewer gate leaves.

::

    _is_unresolved_bot_thread(cursor, unresolved) -> True
    _count_unresolved_bot_threads(one cursor thread) -> (False, "1 unresolved ...")
    _format_unresolved_detail(over limit) -> "... and N more"

Each test drives the real leaf, stubbing only the ``gh`` transport helpers.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPTS_DIRECTORY = Path(__file__).absolute().parent


def _load_thread_gates() -> ModuleType:
    if str(_SCRIPTS_DIRECTORY) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIRECTORY))
    module_path = _SCRIPTS_DIRECTORY / "check_convergence_thread_gates.py"
    spec = importlib.util.spec_from_file_location(
        "thread_gates_under_test", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


thread_gates = _load_thread_gates()


def test_is_unresolved_bot_thread_true_for_cursor_authored_open_thread() -> None:
    thread = {
        "isResolved": False,
        "isOutdated": False,
        "comments": {"nodes": [{"author": {"login": "cursor[bot]"}}]},
    }
    logins = (thread_gates.CURSOR_LOGIN_FILTER_SUBSTRING,)
    assert thread_gates._is_unresolved_bot_thread(thread, logins) is True


def test_is_unresolved_bot_thread_false_for_resolved_thread() -> None:
    thread = {
        "isResolved": True,
        "isOutdated": False,
        "comments": {"nodes": [{"author": {"login": "cursor[bot]"}}]},
    }
    logins = (thread_gates.CURSOR_LOGIN_FILTER_SUBSTRING,)
    assert thread_gates._is_unresolved_bot_thread(thread, logins) is False


def test_count_unresolved_bot_threads_counts_a_single_cursor_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    thread = {
        "isResolved": False,
        "isOutdated": False,
        "path": "src/app.py",
        "comments": {"nodes": [{"author": {"login": "cursor[bot]"}}]},
    }
    graphql_payload = {
        "data": {
            "repository": {
                "pullRequest": {
                    "reviewThreads": {
                        "nodes": [thread],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    }
                }
            }
        }
    }

    def _stub_gh_graphql(query: str, variables: dict[str, object]) -> tuple[int, str]:
        return 0, json.dumps(graphql_payload)

    monkeypatch.setattr(thread_gates, "_gh_graphql", _stub_gh_graphql)
    passed, detail = thread_gates._count_unresolved_bot_threads(
        owner="o", repo="r", number=1
    )
    assert passed is False
    assert detail.startswith("1 unresolved")
    assert "src/app.py" in detail


def test_format_unresolved_detail_bounds_the_listed_paths() -> None:
    over_limit = thread_gates.UNRESOLVED_THREAD_DETAIL_MAX + 2
    all_threads = [{"path": f"file{each_index}.py"} for each_index in range(over_limit)]
    detail = thread_gates._format_unresolved_detail(all_threads)
    assert detail.startswith(f"{over_limit} unresolved")
    assert "more" in detail
