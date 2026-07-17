"""Resolve a validator's config file by walking up from an original path.

A staged temp copy has no config in its own ancestors, so ruff and mypy would
discover nothing there. This walk starts from the ORIGINAL target path and
returns the first pyproject.toml whose ``[tool.<name>]`` table exists.

::

    tool_table_name="ruff", start .../hooks/validators/module.py
    -> climbs to .../hooks/pyproject.toml, which declares [tool.ruff] -> that path
    tool_table_name="ruff", start .../advisor/scripts/module.py
    -> that pyproject declares [tool.mypy] only, no [tool.ruff] -> None
"""

import sys
import tomllib
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent.parent)

try:
    from hooks_constants.mypy_integration_constants import PYPROJECT_FILENAME
    from hooks_constants.pyproject_config_discovery_constants import TOOL_TABLE_KEY
except ModuleNotFoundError:
    if _hooks_directory not in sys.path:
        sys.path.insert(0, _hooks_directory)
    from hooks_constants.mypy_integration_constants import PYPROJECT_FILENAME
    from hooks_constants.pyproject_config_discovery_constants import TOOL_TABLE_KEY


def ancestor_directories(starting_file: Path) -> list[Path]:
    """Return *starting_file*'s directory and every parent, nearest first.

    ::

        repo/pkg/mod.py -> [repo/pkg, repo, ... , filesystem root]
        repo/pkg/       -> [repo/pkg, repo, ... , filesystem root]

    A file resolves to its containing directory; a directory resolves to itself,
    so both callers start the walk from the same first candidate.

    Args:
        starting_file: The file (or directory) the walk begins from.

    Returns:
        The resolved starting directory followed by each of its parents.
    """
    resolved_starting_file = starting_file.resolve()
    walk_origin = (
        resolved_starting_file.parent
        if resolved_starting_file.is_file()
        else resolved_starting_file
    )
    return [walk_origin, *walk_origin.parents]


def _pyproject_configures_tool(pyproject_path: Path, tool_table_name: str) -> bool:
    """Return whether *pyproject_path* declares a ``[tool.<tool_table_name>]`` table.

    A malformed or unreadable file counts as no match, so a broken pyproject
    never shadows a valid config further up the tree.

    Args:
        pyproject_path: The candidate pyproject.toml to parse.
        tool_table_name: The tool's table name below ``[tool]`` (for example ``ruff``).

    Returns:
        True when the parsed file holds ``[tool.<tool_table_name>]``, else False.
    """
    try:
        with pyproject_path.open("rb") as readable_handle:
            parsed_toml = tomllib.load(readable_handle)
    except (OSError, tomllib.TOMLDecodeError):
        return False
    tool_table = parsed_toml.get(TOOL_TABLE_KEY, {})
    return isinstance(tool_table, dict) and tool_table_name in tool_table


def find_pyproject_configuring_tool(starting_file: Path, tool_table_name: str) -> Path | None:
    """Walk up from *starting_file* to the first pyproject.toml configuring a tool.

    The walk skips a pyproject.toml that does not declare the tool's table, so an
    unrelated package config does not shadow a config that actually configures
    the tool further up the tree.

    Args:
        starting_file: The file (or directory) the walk begins from — the
            original target path, not the staged temp copy.
        tool_table_name: The tool's table name below ``[tool]`` (for example ``ruff``).

    Returns:
        The first ``pyproject.toml`` Path that declares ``[tool.<tool_table_name>]``,
        or ``None`` when no such file exists up to the filesystem root.
    """
    for each_candidate_directory in ancestor_directories(starting_file):
        candidate_pyproject = each_candidate_directory / PYPROJECT_FILENAME
        if candidate_pyproject.is_file() and _pyproject_configures_tool(
            candidate_pyproject, tool_table_name
        ):
            return candidate_pyproject
    return None
