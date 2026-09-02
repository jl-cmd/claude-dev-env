"""Resolve the project root that contains a path, if any.

A project root is the nearest ancestor holding a ``.git`` entry or a
``pyproject.toml``. Callers need that anchor for unrelated reasons: binding a
first-party import, deciding which directory segments a project owns. One
module answers it rather than each re-coding the walk.

::

    target_repo/.git + target_repo/tools/x.py  -> target_repo
    /tmp/detached/x.py (home .git above temp)  -> None
"""

from __future__ import annotations

import sys
from pathlib import Path

_validators_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
for each_directory in (_validators_directory, _hooks_directory):
    if each_directory not in sys.path:
        sys.path.insert(0, each_directory)

from pyproject_config_discovery import ancestor_directories  # noqa: E402
from system_temporary_roots import (  # noqa: E402
    enclosing_system_temporary_root,
)

from hooks_constants.mypy_integration_constants import (  # noqa: E402
    GIT_DIRECTORY_NAME,
    PYPROJECT_FILENAME,
)


def enclosing_project_root(starting_file: Path) -> Path | None:
    """Return the nearest ancestor directory that roots a project, else None.

    The walk stops at the system temp root. A staging copy lives under a temp
    directory, and a ``.git`` in the user home above that root roots no
    project of the staged file's.

    Args:
        starting_file: The file (or directory) the walk begins from.

    Returns:
        The nearest ancestor holding ``.git`` or ``pyproject.toml``, or None
        when the walk reaches the temp root or runs out of ancestors.
    """
    enclosing_temporary_root = enclosing_system_temporary_root(starting_file)
    for each_candidate_directory in ancestor_directories(starting_file):
        has_git_entry = (each_candidate_directory / GIT_DIRECTORY_NAME).exists()
        has_pyproject = (each_candidate_directory / PYPROJECT_FILENAME).is_file()
        if has_git_entry or has_pyproject:
            return each_candidate_directory
        if each_candidate_directory == enclosing_temporary_root:
            return None
    return None
