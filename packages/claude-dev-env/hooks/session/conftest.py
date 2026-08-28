"""Add the session folder to sys.path for the tests.

Then import `_path_setup` so the hooks folder is on `sys.path`.
"""

import sys
from pathlib import Path

SESSION_DIRECTORY = Path(__file__).resolve().parent

if str(SESSION_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SESSION_DIRECTORY))

import _path_setup  # noqa: E402, F401
