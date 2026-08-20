"""Put the scripts directory on sys.path so tests import the script by name."""

import sys
from pathlib import Path

_script_directory = str(Path(__file__).resolve().parent)
if _script_directory not in sys.path:
    sys.path.insert(0, _script_directory)
