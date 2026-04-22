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
for each nested class and function.

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

import pytest


_SYNC_AI_RULES_TEST_FILENAME = "test_sync_ai_rules.py"
_REPO_ROOT_DIRECTORY_PATH = os.path.dirname(os.path.abspath(__file__))
_HOOK_LOCAL_DIRECTORY_PATH = os.path.join(
    _REPO_ROOT_DIRECTORY_PATH,
    "packages", "claude-dev-env", "hooks", "git-hooks",
)
_sys_path_snapshot_before_repo_root_insert: list[list[str]] = []


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
    _sys_path_snapshot_before_repo_root_insert.append(list(sys.path))
    if not sys.path or sys.path[0] != _REPO_ROOT_DIRECTORY_PATH:
        sys.path.insert(0, _REPO_ROOT_DIRECTORY_PATH)


def pytest_collectreport(report: pytest.CollectReport) -> None:
    if not _sys_path_snapshot_before_repo_root_insert:
        return
    if report.nodeid != f"tests/{_SYNC_AI_RULES_TEST_FILENAME}":
        return
    sys.path[:] = _sys_path_snapshot_before_repo_root_insert.pop()
    _evict_cached_config_bindings()
