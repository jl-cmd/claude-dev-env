"""Root pytest configuration: evicts conflicting ``config`` imports during collection.

Three different objects share the top-level name ``config``:

- Repository package ``config/`` (for example ``config.sync_ai_rules_paths``).
- ``packages/claude-dev-env/hooks/config/`` (hook messages and shared hook tests).
- ``packages/claude-dev-env/hooks/git-hooks/config.py`` (flat constants for shims).

``pytest.ini`` puts ``packages/claude-dev-env/hooks`` before ``.`` on ``pythonpath``
so hook tests resolve ``hooks/config`` instead of the repository package. Only one
binding can live in ``sys.modules["config"]`` at a time, so ``pytest_collectstart``
evicts it before each incompatible test file is collected.

``sync_ai_rules.py`` only prepends the repository root when it is not already on
``sys.path``; with ``hooks`` ahead of ``.``, that insert is skipped and ``config``
would incorrectly resolve to ``hooks/config``. For ``tests/test_sync_ai_rules.py``
collection only, this module removes the hooks tree from ``sys.path`` and evicts
``config``; ``pytest_collectreport`` then restores the prior ``sys.path`` snapshot
so later hook tests continue to resolve ``config`` to the hook-local package as
``pytest.ini``'s ``pythonpath`` intends.

To keep the start/report hooks symmetric across rootdir shifts and nested
collection layouts, ``pytest_collectstart`` pushes a single
``_PendingSysPathRestore`` tuple — pairing the matched collector's ``nodeid``
with the pre-modification ``sys.path`` snapshot — and ``pytest_collectreport``
pops only when ``report.nodeid`` equals the top-of-stack entry's nodeid.
Bundling both fields in one tuple keeps the nodeid and snapshot invariantly in
sync, so a future refactor cannot drift one ahead of the other and leave
``pytest_collectreport`` popping a snapshot that never had a matching
collectstart.

In production the imports do not overlap: shims prepend only ``git-hooks/``, and
the sync script prepends only the repository root. Only pytest mixes them.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

_SYNC_AI_RULES_TEST_FILENAME = "test_sync_ai_rules.py"
_REPOSITORY_ROOT_PATH = Path(__file__).resolve().parent
_GIT_HOOKS_DIRECTORY_PATH = _REPOSITORY_ROOT_PATH / "packages" / "claude-dev-env" / "hooks" / "git-hooks"
_HOOKS_ROOT_DIRECTORY_PATH = _REPOSITORY_ROOT_PATH / "packages" / "claude-dev-env" / "hooks"


class _PendingSysPathRestore(NamedTuple):
    matched_module_nodeid: str
    sys_path_snapshot: list[str]


_pending_sys_path_restores: list[_PendingSysPathRestore] = []


def _evict_config_module() -> None:
    sys.modules.pop("config", None)
    sys.modules.pop("config.sync_ai_rules_paths", None)
    importlib.invalidate_caches()


def _resolved_path_matches_sys_path_entry(directory_path: Path, entry: str) -> bool:
    try:
        return Path(entry).resolve() == directory_path.resolve()
    except OSError:
        return False


def _remove_path_if_present(directory_path: Path) -> None:
    target = directory_path.resolve()
    sys.path[:] = [
        entry for entry in sys.path if not _resolved_path_matches_sys_path_entry(target, entry)
    ]


def _hooks_root_is_on_sys_path() -> bool:
    target = _HOOKS_ROOT_DIRECTORY_PATH.resolve()
    return any(_resolved_path_matches_sys_path_entry(target, entry) for entry in sys.path)


def _ensure_hooks_root_on_sys_path() -> None:
    if _hooks_root_is_on_sys_path():
        return
    sys.path.insert(0, str(_HOOKS_ROOT_DIRECTORY_PATH.resolve()))


def _is_sync_ai_rules_module_collector(collector: pytest.Collector) -> bool:
    if not isinstance(collector, pytest.Module):
        return False
    collected_path = getattr(collector, "path", None)
    if collected_path is None:
        return False
    return collected_path.name == _SYNC_AI_RULES_TEST_FILENAME


def _record_pending_sys_path_restore(collector_nodeid: str) -> None:
    _pending_sys_path_restores.append(
        _PendingSysPathRestore(
            matched_module_nodeid=collector_nodeid,
            sys_path_snapshot=list(sys.path),
        )
    )


def pytest_collectstart(collector: pytest.Collector) -> None:
    collected_path = getattr(collector, "path", None)
    if collected_path is None:
        return
    resolved_collected_path = collected_path.resolve()

    if _is_sync_ai_rules_module_collector(collector):
        _record_pending_sys_path_restore(collector.nodeid)
        _evict_config_module()
        _remove_path_if_present(_GIT_HOOKS_DIRECTORY_PATH)
        _remove_path_if_present(_HOOKS_ROOT_DIRECTORY_PATH)
        return

    _ensure_hooks_root_on_sys_path()

    try:
        resolved_collected_path.relative_to(_GIT_HOOKS_DIRECTORY_PATH.resolve())
    except ValueError:
        pass
    else:
        if collected_path.name.startswith("test_"):
            _evict_config_module()
        return

    try:
        resolved_collected_path.relative_to(_HOOKS_ROOT_DIRECTORY_PATH.resolve())
    except ValueError:
        return

    if collected_path.name.startswith("test_") or collected_path.name.startswith(
        "should_"
    ):
        _evict_config_module()


def pytest_collectreport(report: pytest.CollectReport) -> None:
    if not _pending_sys_path_restores:
        return
    if report.nodeid != _pending_sys_path_restores[-1].matched_module_nodeid:
        return
    pending_restore = _pending_sys_path_restores.pop()
    sys.path[:] = pending_restore.sys_path_snapshot
    _evict_config_module()
