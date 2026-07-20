"""Put the session and hooks directories on sys.path for the session tests."""

import json
import sys
from collections.abc import Callable
from io import StringIO
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest

_SESSION_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
for each_bootstrap_directory in (_SESSION_DIRECTORY, _HOOKS_DIRECTORY):
    if each_bootstrap_directory not in sys.path:
        sys.path.insert(0, each_bootstrap_directory)


@pytest.fixture
def run_hook_main_with_payload() -> Callable[[ModuleType, dict[str, object]], str]:
    """Return a helper that runs a SessionStart hook's main() with payload on stdin.

    ``run_hook_main_with_payload(starter, {"source": "startup"})`` feeds the
    payload to ``starter.main()`` on stdin and returns whatever it wrote to
    stdout.
    """

    def _run(hook_module: ModuleType, payload: dict[str, object]) -> str:
        captured_stdout = StringIO()
        with (
            patch("sys.stdin", StringIO(json.dumps(payload))),
            patch("sys.stdout", captured_stdout),
            pytest.raises(SystemExit),
        ):
            hook_module.main()
        return captured_stdout.getvalue()

    return _run
