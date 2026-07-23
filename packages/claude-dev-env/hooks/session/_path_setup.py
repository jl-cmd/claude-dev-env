"""Add the hooks directory to sys.path for sibling session entry-point hooks.

Importing this module inserts the hooks directory (this file's parent's parent)
at the front of sys.path so a SessionStart hook that runs as a standalone script
from session/ can import hooks_constants with every import kept at module top.
"""

import sys
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)
