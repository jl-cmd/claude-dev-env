"""Put the session and hooks directories on sys.path for the session tests."""

import sys
from pathlib import Path

_SESSION_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
for each_bootstrap_directory in (_SESSION_DIRECTORY, _HOOKS_DIRECTORY):
    if each_bootstrap_directory not in sys.path:
        sys.path.insert(0, each_bootstrap_directory)
