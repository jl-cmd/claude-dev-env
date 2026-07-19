"""Put the scripts directory on ``sys.path`` for every test in this folder.

The code-review invoker and its constants package live beside these tests
rather than on the default pytest path, so each test module can import them
by bare name once this directory is registered.

::

    import invoke_code_review as invoker   # resolves here
    from dev_env_scripts_constants...      # resolves here

pytest loads this file before collecting sibling test modules, so the path
is in place by the time any test module runs its top-level imports.
"""

from __future__ import annotations

import sys
from pathlib import Path

_scripts_directory = str(Path(__file__).resolve().parent)
if _scripts_directory not in sys.path:
    sys.path.insert(0, _scripts_directory)
