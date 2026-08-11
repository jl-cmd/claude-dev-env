"""Put this directory on ``sys.path`` before the git-hook test modules import.

The git-hook entry points sit beside their constants package rather than inside
an installed package, so ``import pre_push`` resolves only once this directory
leads ``sys.path``. Pytest loads a conftest before the test modules it covers,
so doing the insertion here lets each test module import the hooks at the top
of the file.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path


_GIT_HOOKS_DIRECTORY_STRING = str(Path(__file__).resolve().parent)
_CONFIG_PACKAGE_NAME = "config"
_CONFIG_PACKAGE_PREFIX = "config."

while _GIT_HOOKS_DIRECTORY_STRING in sys.path:
    sys.path.remove(_GIT_HOOKS_DIRECTORY_STRING)
sys.path.insert(0, _GIT_HOOKS_DIRECTORY_STRING)

for each_module_name in list(sys.modules):
    if each_module_name == _CONFIG_PACKAGE_NAME or each_module_name.startswith(
        _CONFIG_PACKAGE_PREFIX
    ):
        del sys.modules[each_module_name]
importlib.invalidate_caches()
