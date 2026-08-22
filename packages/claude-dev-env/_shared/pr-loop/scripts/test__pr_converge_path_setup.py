"""Importing _pr_converge_path_setup registers the skill and shared directories.

::

    import _pr_converge_path_setup
    ok: str(skill_directory) in sys.path
    ok: str(shared_pr_loop_scripts_directory) in sys.path
"""

from __future__ import annotations

import sys
from pathlib import Path

import _pr_converge_path_setup  # noqa: F401

_SCRIPTS_DIRECTORY = Path(__file__).absolute().parent


def test_path_setup_registers_skill_and_shared_directories() -> None:
    skill_directory = _SCRIPTS_DIRECTORY.parent
    shared_entries = [
        each_path
        for each_path in sys.path
        if each_path.replace("\\", "/").endswith("_shared/pr-loop/scripts")
    ]
    assert str(skill_directory) in sys.path
    assert shared_entries
    assert Path(shared_entries[0]).is_dir()
    assert str(_SCRIPTS_DIRECTORY) in sys.path
