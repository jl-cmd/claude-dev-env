"""Add the hooks and blocking directories to sys.path for sibling imports.

Importing this module inserts the hooks directory (this file's parent's parent)
and the blocking directory (its own parent) at the front of sys.path, so a
module that runs as a standalone script from blocking/ can import both
``hooks_constants`` and its blocking-directory siblings while every import stays
at module top.
"""

import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
for each_directory in (_blocking_directory, _hooks_directory):
    if each_directory not in sys.path:
        sys.path.insert(0, each_directory)
