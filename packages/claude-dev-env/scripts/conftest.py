"""Put the scripts directory on sys.path so tests import each script by name."""

import sys
from pathlib import Path

_scripts_directory = str(Path(__file__).resolve().parent)
if _scripts_directory not in sys.path:
    sys.path.insert(0, _scripts_directory)
