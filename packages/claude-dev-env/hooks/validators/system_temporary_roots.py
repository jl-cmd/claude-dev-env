"""Resolve the system temp root that contains a path, if any.

Staging copies and pytest basetemp live under ``tempfile.gettempdir()`` or
under ``TEMP`` / ``TMP`` / ``TMPDIR`` / ``RUNNER_TEMP``. A walk that needs to
stop at that boundary asks here instead of re-coding membership in each caller.

::

    %TEMP%/pytest-123/x.py              -> %TEMP%
    RUNNER_TEMP/detached/x.py (GHA)     -> RUNNER_TEMP
    C:/repo/pkg/x.py                    -> None
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from validators.config.system_temporary_roots_constants import (  # noqa: E402
    ALL_SYSTEM_TEMPORARY_ROOT_ENVIRONMENT_VARIABLE_NAMES,
)


def all_system_temporary_roots() -> tuple[Path, ...]:
    """Return resolved roots that count as system temporary directories.

    ::

        gettempdir() plus TEMP / TMP / TMPDIR / RUNNER_TEMP when set.

    GitHub Actions puts pytest basetemp under ``RUNNER_TEMP``
    (``/home/runner/work/_temp``) while ``tempfile.gettempdir()`` is ``/tmp``.
    Both count so a staging walk and a path-exemption check agree.

    Returns:
        Unique resolved directory Paths. Unresolvable candidates are dropped.
    """
    all_candidate_roots: list[str] = [tempfile.gettempdir()]
    for each_environment_name in ALL_SYSTEM_TEMPORARY_ROOT_ENVIRONMENT_VARIABLE_NAMES:
        environment_value = os.environ.get(each_environment_name)
        if environment_value:
            all_candidate_roots.append(environment_value)
    all_resolved_roots: list[Path] = []
    all_seen_roots: set[Path] = set()
    for each_candidate in all_candidate_roots:
        try:
            resolved_root = Path(each_candidate).resolve()
        except OSError:
            continue
        if resolved_root in all_seen_roots:
            continue
        all_seen_roots.add(resolved_root)
        all_resolved_roots.append(resolved_root)
    return tuple(all_resolved_roots)


def enclosing_system_temporary_root(starting_file: Path) -> Path | None:
    """Return the innermost system temp root that contains *starting_file*.

    ::

        %TEMP%/pytest-123/x.py -> %TEMP%
        C:/repo/pkg/x.py       -> None

    When more than one listed root contains the file, the first ancestor that
    is already in the root set wins, so a nested ``RUNNER_TEMP`` stops the walk
    before a broader ``gettempdir()`` ancestor.

    Args:
        starting_file: The file or directory whose ancestors are bounded.

    Returns:
        The innermost matching root Path, or ``None`` when no listed root
        contains *starting_file*.
    """
    try:
        resolved_start = starting_file.resolve()
    except OSError:
        return None
    all_root_set = set(all_system_temporary_roots())
    for each_candidate_directory in (resolved_start, *resolved_start.parents):
        if each_candidate_directory in all_root_set:
            return each_candidate_directory
    return None
