"""Test fixtures for _shared/pr-loop/scripts/.

Two unrelated Python packages live under the name ``config`` in this repo:
  - ``_shared/pr-loop/scripts/config/`` (constants for grant/revoke/gate/preflight scripts)
  - ``hooks/config/`` (constants for the code-rules enforcer and other hooks)

When tests under this directory exercise the gate (which loads
``hooks/blocking/code_rules_enforcer.py``) and also load the grant/revoke
scripts in the same pytest process, ``sys.modules['config']`` and
``sys.modules['config.<submodule>']`` cache entries from one package leak
into the other. The next ``from config.<submodule> import ...`` then fails
with ``ModuleNotFoundError`` because the cached parent package does not
expose that submodule.

Independently, several scripts in this folder do
``Path(__file__).resolve()`` then prepend the resulting directory to
``sys.path``. On Windows when the working tree lives under a mapped drive
backed by a UNC share (``Y:`` -> ``\\\\server\\share\\...``), ``.resolve()``
returns the UNC form, and Python's import machinery on this host cannot
locate ``config`` packages from a UNC ``sys.path`` entry. The Y:-form entry
gets pushed to a later index by subsequent inserts, making ``from
config.<submodule> import ...`` fail.

This autouse fixture restores both invariants before each test:
  1. evict every ``config`` and ``config.*`` entry from ``sys.modules``
  2. prepend the drive-letter (``.absolute()``) form of the scripts
     directory to ``sys.path`` so package resolution always has a
     non-UNC path to search first
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY_DRIVE_LETTER_FORM = str(Path(__file__).absolute().parent.parent)


@pytest.fixture(autouse=True)
def _evict_config_namespace_between_tests() -> None:
    for each_module_name in [
        each_key
        for each_key in list(sys.modules)
        if each_key == "config" or each_key.startswith("config.")
    ]:
        sys.modules.pop(each_module_name, None)
    if SCRIPTS_DIRECTORY_DRIVE_LETTER_FORM in sys.path:
        sys.path.remove(SCRIPTS_DIRECTORY_DRIVE_LETTER_FORM)
    sys.path.insert(0, SCRIPTS_DIRECTORY_DRIVE_LETTER_FORM)
