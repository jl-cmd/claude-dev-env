"""Put this worktree's prototype scripts directory on the import path.

The scripts import their ``prototype_scripts_constants`` package by name.
Inserting this directory lets the tests resolve that package and the
script modules from the local worktree rather than an installed copy.
"""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))
