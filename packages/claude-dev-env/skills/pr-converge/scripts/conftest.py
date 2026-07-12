"""Put the pr-converge scripts directory on sys.path for the test suite."""

import sys
from pathlib import Path

_scripts_directory = Path(__file__).resolve().parent
if str(_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_scripts_directory))
