"""Add hooks/blocking and hooks/ to sys.path for every test collected under this directory."""

import sys
from pathlib import Path

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(_BLOCKING_DIRECTORY).parent)
for each_directory in (_BLOCKING_DIRECTORY, _HOOKS_DIRECTORY):
    if each_directory not in sys.path:
        sys.path.insert(0, each_directory)
