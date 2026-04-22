"""Root pytest configuration: evicts the hook-local ``config`` shadow before importing ``test_sync_ai_rules.py``.

``packages/claude-dev-env/hooks/git-hooks/config.py`` is a flat module with the
same import name as the repo-root ``config/`` package. During a full local
pytest run, hook-local tests collect first (alphabetical order);
``test_config.py`` and ``test_pre_push.py`` insert ``git-hooks/`` into
``sys.path`` and cache the flat module in ``sys.modules``.

When collection reaches ``tests/test_sync_ai_rules.py``, importing
``.github/scripts/sync_ai_rules.py`` then does
``from config.sync_ai_rules_paths import ...``. Python resolves ``config``
against the cached flat module first and raises ``'config' is not a package``.

``pytest_collectstart`` runs before each file is imported for collection, so
evicting the hook-local ``config`` binding and removing the hook-local
directory from ``sys.path`` just before ``test_sync_ai_rules.py`` is imported
forces Python to resolve ``config`` against the package.

A second shadow exists: ``packages/claude-dev-env/hooks/config/`` is a
regular package (with ``__init__.py``) declared on ``pytest.ini``'s
``pythonpath`` ahead of the repo root. When ``sync_ai_rules`` attempts
``from config.sync_ai_rules_paths``, Python walks ``sys.path`` and matches
the hook-local package first, which has no ``sync_ai_rules_paths`` module.
Prepending the repo root to ``sys.path`` in ``pytest_collectstart`` pins the
repo-root ``config`` package first for the duration of this test's imports,
without removing ``packages/claude-dev-env/hooks`` from ``sys.path`` (later-
collected hook tests still need that directory). ``pytest_collectreport``
then restores ``sys.path`` to its pre-insert state and re-evicts ``config``
from ``sys.modules`` as soon as the module finishes collecting, so hook
tests collected afterwards (including explicit orderings like ``pytest
tests/test_sync_ai_rules.py packages/claude-dev-env/hooks/``) resolve
``config`` to the hook-local package as ``pytest.ini``'s ``pythonpath``
intends. The setup and restore are both gated on ``isinstance(collector,
pytest.Module)`` so they fire exactly once per ``test_sync_ai_rules.py``
collection even though the file also raises ``pytest_collectstart`` events
for each nested class and function. To keep the start/report hooks symmetric
across rootdir shifts and nested collection layouts, ``pytest_collectstart``
pushes a single ``_PendingSysPathRestore`` tuple — pairing the matched
collector's ``nodeid`` with the pre-insert ``sys.path`` snapshot — and
``pytest_collectreport`` pops only when ``report.nodeid`` equals the
top-of-stack entry's nodeid. Bundling both fields in one tuple keeps the
nodeid and snapshot invariantly in sync, so a future refactor cannot drift
one ahead of the other and leave ``pytest_collectreport`` popping a
snapshot that never had a matching collectstart.

The ``sys.path`` baseline (repo root, ``.github/scripts``, hook tree) is
established declaratively via ``pytest.ini``'s ``pythonpath``, so CI targeted
runs that don't collect hook-local tests do not need this hook at all.

In production the three imports never overlap: the git-hook shim runs
``pre_push.py`` / ``pre_commit.py`` as scripts with only ``git-hooks/`` on
``sys.path``, the hook subsystem imports ``hooks/config/`` only when
``packages/claude-dev-env/hooks`` is on ``sys.path``, and the sync listener
runs ``sync_ai_rules.py`` with only the repo root on ``sys.path``. Only
pytest's single-process collection mixes them.
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import NamedTuple

import pytest


_SYNC_AI_RULES_TEST_FILENAME = "test_sync_ai_rules.py"
_REPO_ROOT_DIRECTORY_PATH = os.path.dirname(os.path.abspath(__file__))
_HOOK_LOCAL_DIRECTORY_PATH = os.path.join(
    _REPO_ROOT_DIRECTORY_PATH,
    "packages", "claude-dev-env", "hooks", "git-hooks",
)


class _PendingSysPathRestore(NamedTuple):
    matched_module_nodeid: str
    sys_path_snapshot: list[str]


_pending_sys_path_restores: list[_PendingSysPathRestore] = []


def _evict_cached_config_bindings() -> None:
    sys.modules.pop("config", None)
    sys.modules.pop("config.sync_ai_rules_paths", None)
    importlib.invalidate_caches()


def _is_sync_ai_rules_module_collector(collector: pytest.Collector) -> bool:
    if not isinstance(collector, pytest.Module):
        return False
    collected_path = getattr(collector, "path", None)
    if collected_path is None:
        return False
    return collected_path.name == _SYNC_AI_RULES_TEST_FILENAME


def pytest_collectstart(collector: pytest.Collector) -> None:
    if not _is_sync_ai_rules_module_collector(collector):
        return
    _evict_cached_config_bindings()
    while _HOOK_LOCAL_DIRECTORY_PATH in sys.path:
        sys.path.remove(_HOOK_LOCAL_DIRECTORY_PATH)
    _pending_sys_path_restores.append(
        _PendingSysPathRestore(
            matched_module_nodeid=collector.nodeid,
            sys_path_snapshot=list(sys.path),
        )
    )
    if not sys.path or sys.path[0] != _REPO_ROOT_DIRECTORY_PATH:
        sys.path.insert(0, _REPO_ROOT_DIRECTORY_PATH)


def pytest_collectreport(report: pytest.CollectReport) -> None:
    if not _pending_sys_path_restores:
        return
    if report.nodeid != _pending_sys_path_restores[-1].matched_module_nodeid:
        return
    pending_restore = _pending_sys_path_restores.pop()
    sys.path[:] = pending_restore.sys_path_snapshot
    _evict_cached_config_bindings()
