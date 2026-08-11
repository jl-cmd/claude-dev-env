"""Add the hooks directory to sys.path for session entry-point scripts.

Importing this module inserts the hooks directory (this file's parent) at the
front of sys.path so a SessionStart script under session/ can import
hooks_constants with every import kept at module top.
"""

import sys
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)
