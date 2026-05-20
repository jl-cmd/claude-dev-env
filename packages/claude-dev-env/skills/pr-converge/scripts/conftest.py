"""Test fixtures for skills/pr-converge/scripts/.

Several Python packages share the name ``config`` across this repo, including:
  - ``skills/pr-converge/config/`` (constants for the pr-converge scripts)
  - ``skills/pr-converge/scripts/config/`` (test-local constants alongside the scripts)
  - ``hooks/config/`` (constants for the code-rules enforcer and other hooks)
  - ``_shared/pr-loop/scripts/config/`` (shared pr-loop constants)
  - ``skills/bugteam/scripts/config/``, ``skills/doc-gist/scripts/config/``,
    ``scripts/config/`` and a repo-root ``config/`` (additional siblings)

This conftest addresses one specific collision pair: the
``skills/pr-converge/config/`` package vs. the ``hooks/config/`` package.
When tests under this directory exercise pr-converge scripts that load
``from config.constants import ...`` and another collected test module in
the same pytest process imports a hook that loads
``from config.<hook_submodule> import ...``, the
``sys.modules['config']`` and ``sys.modules['config.<submodule>']`` cache
entries from the first-imported package leak into the second. The next
``from config.<submodule> import ...`` then fails with
``ModuleNotFoundError`` because the cached parent package does not
expose that submodule.

Independently, several scripts in this folder do
``Path(__file__).resolve()`` then prepend the resulting directory to
``sys.path``. On Windows when the working tree lives under a mapped drive
backed by a UNC share (``Y:`` -> ``\\\\server\\share\\...``), ``.resolve()``
returns the UNC form, and Python's import machinery on this host cannot
locate ``config`` packages from a UNC ``sys.path`` entry. The Y:-form entry
gets pushed to a later index by subsequent inserts, making
``from config.<submodule> import ...`` fail.

This autouse fixture restores both invariants once per pytest session,
immediately before the first test executes (after collection and module
imports have completed; session-scoped fixtures run after import, not
before, so test-module-level ``import`` of pr-converge scripts is
isolated by each module's own ``_load_module()`` helper rather than by
this fixture):
  1. evict every ``config`` and ``config.*`` entry from ``sys.modules``
  2. prepend the drive-letter (``.absolute()``) form of the pr-converge
     directory to ``sys.path`` so package resolution always has a
     non-UNC path to search first

After the session completes, the fixture also restores ``sys.path`` to its
pre-conftest snapshot. Without this restore, the module-top
``sys.path.insert`` above leaks the pr-converge directory into sibling
pytest invocations that share a process (e.g. running
``pytest pr-converge/scripts/ hooks/blocking/`` in one command), causing
the hooks tests to import ``config`` from pr-converge instead of from
hooks.

To prevent the same leak during the *collection* phase (which runs before
any session fixture), this conftest also implements
``pytest_collectstart``: when pytest begins collecting a test module
whose path is outside the pr-converge directory tree, the hook restores
``sys.path`` to its pre-conftest snapshot and evicts cached ``config``
entries from ``sys.modules``. This isolates pr-converge's local
``config`` package from the hook test modules that import their own
``config`` siblings during collection.
"""

from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path

import pytest

PR_CONVERGE_DIRECTORY = Path(__file__).absolute().parent.parent
PR_CONVERGE_DIRECTORY_DRIVE_LETTER_FORM = str(PR_CONVERGE_DIRECTORY)

_ORIGINAL_SYS_PATH = list(sys.path)

if PR_CONVERGE_DIRECTORY_DRIVE_LETTER_FORM not in sys.path:
    sys.path.insert(0, PR_CONVERGE_DIRECTORY_DRIVE_LETTER_FORM)


def _evict_pr_converge_config_namespace() -> None:
    for each_module_name in [
        each_key
        for each_key in list(sys.modules)
        if each_key == "config" or each_key.startswith("config.")
    ]:
        sys.modules.pop(each_module_name, None)


def _isolate_pr_converge_sys_path_for_outside_collection() -> None:
    sys.path[:] = _ORIGINAL_SYS_PATH


def _collector_path_is_outside_pr_converge(collector_path: Path) -> bool:
    try:
        collector_path.absolute().relative_to(PR_CONVERGE_DIRECTORY)
    except ValueError:
        return True
    return False


class _PrConvergeCrossDirectoryIsolationPlugin:
    """Restore sys.path and evict cached config modules when collection
    leaves the pr-converge subtree.

    Registering as a session-wide plugin (not as a conftest hook) lets the
    hook fire for collectors in other parts of the repo, which a child
    conftest's hook scoping would otherwise prevent.
    """

    def pytest_collectstart(self, collector: pytest.Collector) -> None:
        collector_filesystem_path = getattr(collector, "path", None)
        if collector_filesystem_path is None:
            return
        if _collector_path_is_outside_pr_converge(Path(str(collector_filesystem_path))):
            _evict_pr_converge_config_namespace()
            _isolate_pr_converge_sys_path_for_outside_collection()


def pytest_configure(config: pytest.Config) -> None:
    if not config.pluginmanager.hasplugin("pr_converge_cross_directory_isolation"):
        config.pluginmanager.register(
            _PrConvergeCrossDirectoryIsolationPlugin(),
            name="pr_converge_cross_directory_isolation",
        )


@pytest.fixture(scope="session", autouse=True)
def _evict_config_namespace_at_session_start() -> Generator[None, None, None]:
    _evict_pr_converge_config_namespace()
    if PR_CONVERGE_DIRECTORY_DRIVE_LETTER_FORM in sys.path:
        sys.path.remove(PR_CONVERGE_DIRECTORY_DRIVE_LETTER_FORM)
    sys.path.insert(0, PR_CONVERGE_DIRECTORY_DRIVE_LETTER_FORM)
    yield
    sys.path[:] = _ORIGINAL_SYS_PATH
