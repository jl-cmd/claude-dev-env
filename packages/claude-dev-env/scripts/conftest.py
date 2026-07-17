import sys
from pathlib import Path

_SCRIPTS_DIRECTORY = str(Path(__file__).resolve().parent)

if _SCRIPTS_DIRECTORY not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIRECTORY)
