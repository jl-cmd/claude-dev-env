"""Put the session and hooks directories on sys.path for the session tests."""

import sys
from pathlib import Path

SESSION_DIRECTORY = Path(__file__).resolve().parent
HOOKS_DIRECTORY = SESSION_DIRECTORY.parent

if str(SESSION_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SESSION_DIRECTORY))

if str(HOOKS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIRECTORY))
