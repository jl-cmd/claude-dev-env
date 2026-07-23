"""Put the hooks directory on sys.path so hooks_constants tests import the package."""

import sys
from pathlib import Path

_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)
