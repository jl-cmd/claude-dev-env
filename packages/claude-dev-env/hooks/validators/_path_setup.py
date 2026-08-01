"""Add the hooks directory to sys.path for cross-package validator imports.

Importing this module inserts the hooks directory (this file's parent's parent)
at the front of sys.path, so a validator module can import the ``blocking`` and
``hooks_constants`` packages while every import stays at module top.
"""

import sys
from pathlib import Path

hooks_directory_on_path = str(Path(__file__).resolve().parent.parent)
"""The hooks directory this module places on ``sys.path``.

An importer binds this name so the bootstrap import reads as used rather than as
a stray side-effect import.
"""

if hooks_directory_on_path not in sys.path:
    sys.path.insert(0, hooks_directory_on_path)
