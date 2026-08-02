"""Behavior test for the sibling-import path bootstrap.

Importing _path_setup must place the hooks directory (its own parent) on
sys.path so an entry-point dispatcher in blocking/ can then import hooks_constants
with all imports kept at module top. The check runs in a subprocess with only
blocking/ on PYTHONPATH, proving the bootstrap adds the hooks directory itself.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_BLOCKING_DIR = Path(__file__).resolve().parent
_HOOKS_DIR = _BLOCKING_DIR.parent


def test_importing_path_setup_puts_the_hooks_directory_on_sys_path() -> None:
    """A subprocess that imports _path_setup finds the hooks directory on sys.path."""
    driver = (
        "import _path_setup\n"
        "import sys\n"
        "from pathlib import Path\n"
        "hooks_dir = str(Path(_path_setup.__file__).resolve().parent.parent)\n"
        "assert hooks_dir in sys.path, hooks_dir\n"
        "print('ok')\n"
    )
    subprocess_environment = {**os.environ, "PYTHONPATH": str(_BLOCKING_DIR)}
    completed = subprocess.run(
        [sys.executable, "-c", driver],
        check=False,
        capture_output=True,
        text=True,
        env=subprocess_environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"


def test_importing_path_setup_puts_the_blocking_directory_on_sys_path() -> None:
    """A module reached through the package finds its own directory on sys.path.

    ``code_rules_shared`` imports both ``hooks_constants`` (a hooks-directory
    package) and its blocking-directory siblings, so the bootstrap must place
    both roots. Only the hooks directory is on PYTHONPATH here, so the blocking
    entry can only come from the bootstrap itself.
    """
    driver = (
        "import sys\n"
        "from blocking import _path_setup\n"
        "from pathlib import Path\n"
        "blocking_dir = str(Path(_path_setup.__file__).resolve().parent)\n"
        "assert blocking_dir in sys.path, blocking_dir\n"
        "print('ok')\n"
    )
    subprocess_environment = {**os.environ, "PYTHONPATH": str(_HOOKS_DIR)}
    completed = subprocess.run(
        [sys.executable, "-c", driver],
        check=False,
        capture_output=True,
        text=True,
        env=subprocess_environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"
