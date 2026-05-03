"""Root pytest configuration: evicts conflicting ``config`` imports during collection.

Five different objects share the top-level name ``config``:

- Repository package ``config/`` (for example ``config.sync_ai_rules_paths``).
- ``packages/claude-dev-env/hooks/config/`` (hook messages and shared hook tests).
- ``packages/claude-dev-env/hooks/git-hooks/config.py`` (flat constants for shims).
- ``packages/claude-dev-env/_shared/pr-loop/scripts/config/`` (shared PR-loop
  script constants).
- ``packages/claude-dev-env/skills/pr-converge/scripts/config/`` (pr-converge
  skill script constants). The shared scripts insert their own directory on
  ``sys.path`` at module-load time so they can ``from config.X import Y`` when
  installed under ``~/.claude/_shared/``; under pytest that insert leaks across
  collection boundaries unless this conftest evicts it.

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
_HOOK_LOCAL_DIRECTORY_PATH = str(_GIT_HOOKS_DIRECTORY_PATH)
_SHARED_PR_LOOP_SCRIPTS_DIRECTORY_PATH = (
    _REPOSITORY_ROOT_PATH
    / "packages"
    / "claude-dev-env"
    / "_shared"
    / "pr-loop"
    / "scripts"
)
_PR_CONVERGE_SCRIPTS_DIRECTORY_PATH = (
    _REPOSITORY_ROOT_PATH
    / "packages"
    / "claude-dev-env"
    / "skills"
    / "pr-converge"
    / "scripts"
)


class _PendingSysPathRestore(NamedTuple):
    matched_module_nodeid: str
    sys_path_snapshot: list[str]


_pending_sys_path_restores: list[_PendingSysPathRestore] = []


def _evict_config_module() -> None:
    for each_cached_module_name in list(sys.modules):
        is_config_root = each_cached_module_name == "config"
        is_config_submodule = each_cached_module_name.startswith("config.")
        if is_config_root or is_config_submodule:
            sys.modules.pop(each_cached_module_name, None)
    importlib.invalidate_caches()


def _resolved_path_matches_sys_path_entry(directory_path: Path, entry: str) -> bool:
    try:
        return Path(entry).resolve() == directory_path.resolve()
    except OSError:
        return False


def _remove_path_if_present(directory_path: Path) -> bool:
    target = directory_path.resolve()
    filtered_entries = [
        entry for entry in sys.path if not _resolved_path_matches_sys_path_entry(target, entry)
    ]
    any_entry_was_removed = len(filtered_entries) != len(sys.path)
    sys.path[:] = filtered_entries
    return any_entry_was_removed


def _cached_config_module_resolves_inside(directory_path: Path) -> bool:
    cached_config_module = sys.modules.get("config")
    if cached_config_module is None:
        return False
    cached_module_file = getattr(cached_config_module, "__file__", None)
    if cached_module_file is None:
        return False
    try:
        cached_module_path = Path(cached_module_file).resolve()
    except OSError:
        return False
    return _path_is_inside_directory(cached_module_path, directory_path.resolve())


def _cached_config_is_flat_git_hooks_module() -> bool:
    return _cached_config_module_resolves_inside(_GIT_HOOKS_DIRECTORY_PATH)


def _cached_config_resolves_inside_shared_pr_loop_scripts() -> bool:
    return _cached_config_module_resolves_inside(_SHARED_PR_LOOP_SCRIPTS_DIRECTORY_PATH)


def _cached_config_resolves_inside_pr_converge_scripts() -> bool:
    return _cached_config_module_resolves_inside(_PR_CONVERGE_SCRIPTS_DIRECTORY_PATH)


def _config_module_is_currently_cached() -> bool:
    return "config" in sys.modules


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


def _path_is_inside_directory(path_to_check: Path, containing_directory: Path) -> bool:
    try:
        path_to_check.relative_to(containing_directory)
    except ValueError:
        return False
    return True


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
        _remove_path_if_present(_SHARED_PR_LOOP_SCRIPTS_DIRECTORY_PATH)
        _remove_path_if_present(_PR_CONVERGE_SCRIPTS_DIRECTORY_PATH)
        return

    _ensure_hooks_root_on_sys_path()

    resolved_git_hooks_directory_path = _GIT_HOOKS_DIRECTORY_PATH.resolve()
    resolved_shared_pr_loop_scripts_path = (
        _SHARED_PR_LOOP_SCRIPTS_DIRECTORY_PATH.resolve()
    )

    is_inside_git_hooks = _path_is_inside_directory(
        resolved_collected_path, resolved_git_hooks_directory_path
    )
    if is_inside_git_hooks:
        collector_expects_flat_config = collected_path.name.startswith("test_")
        cached_config_binding_is_wrong_for_git_hooks = (
            _config_module_is_currently_cached()
            and not _cached_config_is_flat_git_hooks_module()
        )
        if collector_expects_flat_config and cached_config_binding_is_wrong_for_git_hooks:
            _evict_config_module()
        _remove_path_if_present(_SHARED_PR_LOOP_SCRIPTS_DIRECTORY_PATH)
        _remove_path_if_present(_PR_CONVERGE_SCRIPTS_DIRECTORY_PATH)
        return

    is_inside_shared_pr_loop_scripts = _path_is_inside_directory(
        resolved_collected_path, resolved_shared_pr_loop_scripts_path
    )
    if is_inside_shared_pr_loop_scripts:
        cached_config_binding_is_wrong_for_shared_scripts = (
            _config_module_is_currently_cached()
            and not _cached_config_resolves_inside_shared_pr_loop_scripts()
        )
        if cached_config_binding_is_wrong_for_shared_scripts:
            _evict_config_module()
        _remove_path_if_present(_PR_CONVERGE_SCRIPTS_DIRECTORY_PATH)
        return

    resolved_pr_converge_scripts_path = _PR_CONVERGE_SCRIPTS_DIRECTORY_PATH.resolve()
    is_inside_pr_converge_scripts = _path_is_inside_directory(
        resolved_collected_path, resolved_pr_converge_scripts_path
    )
    if is_inside_pr_converge_scripts:
        cached_config_binding_is_wrong_for_pr_converge_scripts = (
            _config_module_is_currently_cached()
            and not _cached_config_resolves_inside_pr_converge_scripts()
        )
        if cached_config_binding_is_wrong_for_pr_converge_scripts:
            _evict_config_module()
        _remove_path_if_present(_SHARED_PR_LOOP_SCRIPTS_DIRECTORY_PATH)
        return

    any_git_hooks_entry_was_removed = _remove_path_if_present(_GIT_HOOKS_DIRECTORY_PATH)
    any_shared_scripts_entry_was_removed = _remove_path_if_present(
        _SHARED_PR_LOOP_SCRIPTS_DIRECTORY_PATH
    )
    any_pr_converge_scripts_entry_was_removed = _remove_path_if_present(
        _PR_CONVERGE_SCRIPTS_DIRECTORY_PATH
    )
    if (
        any_git_hooks_entry_was_removed
        or any_shared_scripts_entry_was_removed
        or any_pr_converge_scripts_entry_was_removed
        or _cached_config_is_flat_git_hooks_module()
        or _cached_config_resolves_inside_shared_pr_loop_scripts()
        or _cached_config_resolves_inside_pr_converge_scripts()
    ):
        _evict_config_module()


def pytest_collectreport(report: pytest.CollectReport) -> None:
    if not _pending_sys_path_restores:
        return
    if report.nodeid != _pending_sys_path_restores[-1].matched_module_nodeid:
        return
    pending_restore = _pending_sys_path_restores.pop()
    sys.path[:] = pending_restore.sys_path_snapshot
    _remove_path_if_present(_SHARED_PR_LOOP_SCRIPTS_DIRECTORY_PATH)
    _remove_path_if_present(_PR_CONVERGE_SCRIPTS_DIRECTORY_PATH)
    _evict_config_module()
