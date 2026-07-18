"""Put the blocking and hooks directories on sys.path for the parts tests.

The concern modules import their shared constants as ``from config...`` against
the sibling ``blocking/config/`` package, so the tests need the blocking
directory (which holds that package) and the hooks directory on the path.
"""

import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parents[1])
_hooks_directory = str(Path(__file__).resolve().parents[2])
for each_bootstrap_directory in (_blocking_directory, _hooks_directory):
    if each_bootstrap_directory not in sys.path:
        sys.path.insert(0, each_bootstrap_directory)
