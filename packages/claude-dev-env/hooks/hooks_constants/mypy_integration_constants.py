"""Path markers used when mypy resolves a target file's project root.

The integration walks ancestors for a ``.git`` entry or a ``pyproject.toml``,
and filters the check list to ``.py`` files. These names live here so the
integration module carries no inline path or extension literals.
"""

__all__ = [
    "GIT_DIRECTORY_NAME",
    "PYTHON_SOURCE_SUFFIX",
    "PYPROJECT_FILENAME",
]

GIT_DIRECTORY_NAME: str = ".git"
PYTHON_SOURCE_SUFFIX: str = ".py"
PYPROJECT_FILENAME: str = "pyproject.toml"
