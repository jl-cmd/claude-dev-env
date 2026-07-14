"""Put the pr-loop scripts directory on sys.path for the parts test suite.

Importing this conftest inserts the ``_shared/pr-loop/scripts`` directory (this
file's parent's parent's parent) at the front of sys.path so the parts modules
resolve ``pr_loop_shared_constants`` and ``terminology_sweep`` with every import
kept at module top.
"""

import sys
from pathlib import Path

_scripts_directory = str(Path(__file__).resolve().parents[2])
if _scripts_directory not in sys.path:
    sys.path.insert(0, _scripts_directory)
