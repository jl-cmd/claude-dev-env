"""Put the blocking and hooks directories on sys.path for the skip-token tests."""

import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parents[2])
_hooks_directory = str(Path(__file__).resolve().parents[3])
for each_bootstrap_directory in (_blocking_directory, _hooks_directory):
    if each_bootstrap_directory not in sys.path:
        sys.path.insert(0, each_bootstrap_directory)
