"""Test fixtures for skills/pr-converge/scripts/.

Two unrelated Python packages live under the name ``config`` in this repo:
  - ``skills/pr-converge/config/`` (constants for the pr-converge scripts)
  - ``hooks/config/`` (constants for the code-rules enforcer and other hooks)

When tests under this directory exercise pr-converge scripts that load
``from config.constants import ...`` and other code paths in the same
pytest process also load a different ``config`` package,
``sys.modules['config']`` and ``sys.modules['config.<submodule>']`` cache
entries from one package leak into the other. The next
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
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PR_CONVERGE_DIRECTORY_DRIVE_LETTER_FORM = str(Path(__file__).absolute().parent.parent)

if PR_CONVERGE_DIRECTORY_DRIVE_LETTER_FORM not in sys.path:
    sys.path.insert(0, PR_CONVERGE_DIRECTORY_DRIVE_LETTER_FORM)


@pytest.fixture(scope="session", autouse=True)
def _evict_config_namespace_at_session_start() -> None:
    for each_module_name in [
        each_key
        for each_key in list(sys.modules)
        if each_key == "config" or each_key.startswith("config.")
    ]:
        sys.modules.pop(each_module_name, None)
    if PR_CONVERGE_DIRECTORY_DRIVE_LETTER_FORM in sys.path:
        sys.path.remove(PR_CONVERGE_DIRECTORY_DRIVE_LETTER_FORM)
    sys.path.insert(0, PR_CONVERGE_DIRECTORY_DRIVE_LETTER_FORM)
