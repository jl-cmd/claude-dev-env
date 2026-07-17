"""Locate the hooks tree and put it on ``sys.path`` for validator modules.

Importing this module resolves the validators package directory, its parent
hooks directory, and the package name, then inserts the hooks directory on
``sys.path`` so sibling ``blocking`` and ``hooks_constants`` packages import by
their top-level names. Every validator module that needs those packages imports
this module first so the bootstrap runs before their imports resolve.
"""

import sys

from .config import VALIDATORS_DIR

hooks_dir = VALIDATORS_DIR.parent
package_name = VALIDATORS_DIR.name

_hooks_directory_on_path = str(hooks_dir.resolve())
if _hooks_directory_on_path not in sys.path:
    sys.path.insert(0, _hooks_directory_on_path)
