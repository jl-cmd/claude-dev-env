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

The ``sys.path`` baseline (repo root, ``.github/scripts``, hook tree) is
established declaratively via ``pytest.ini``'s ``pythonpath``, so CI targeted
runs that don't collect hook-local tests do not need this hook at all.

In production the two imports never overlap: the git-hook shim runs
``pre_push.py`` / ``pre_commit.py`` as scripts with only ``git-hooks/`` on
``sys.path``, and the sync listener runs ``sync_ai_rules.py`` with only the
repo root on ``sys.path``. Only pytest's single-process collection mixes them.
"""

from __future__ import annotations

import importlib
import os
import sys

import pytest


_SYNC_AI_RULES_TEST_FILENAME = "test_sync_ai_rules.py"
_HOOK_LOCAL_DIRECTORY_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "packages", "claude-dev-env", "hooks", "git-hooks",
)


def pytest_collectstart(collector: pytest.Collector) -> None:
    collected_path = getattr(collector, "path", None)
    if collected_path is None:
        return
    if collected_path.name != _SYNC_AI_RULES_TEST_FILENAME:
        return
    sys.modules.pop("config", None)
    sys.modules.pop("config.sync_ai_rules_paths", None)
    importlib.invalidate_caches()
    while _HOOK_LOCAL_DIRECTORY_PATH in sys.path:
        sys.path.remove(_HOOK_LOCAL_DIRECTORY_PATH)
