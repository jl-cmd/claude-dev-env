"""Path markers and detached-file mypy CLI flags.

The integration walks ancestors for a ``.git`` entry or a ``pyproject.toml``,
and filters the check list to ``.py`` files. A file with no project root is a
detached gate staging copy: mypy then skips followed imports and must finish
inside a short subprocess timeout so the 30-second PreToolUse hook can return.
"""

__all__ = [
    "GIT_DIRECTORY_NAME",
    "PYTHON_SOURCE_SUFFIX",
    "PYPROJECT_FILENAME",
    "FOLLOW_IMPORTS_FLAG",
    "FOLLOW_IMPORTS_SKIP_VALUE",
    "MYPY_DETACHED_SUBPROCESS_TIMEOUT_SECONDS",
    "MYPY_DETACHED_TIMEOUT_SKIP_MESSAGE",
]

GIT_DIRECTORY_NAME: str = ".git"
PYTHON_SOURCE_SUFFIX: str = ".py"
PYPROJECT_FILENAME: str = "pyproject.toml"
FOLLOW_IMPORTS_FLAG: str = "--follow-imports"
FOLLOW_IMPORTS_SKIP_VALUE: str = "skip"
MYPY_DETACHED_SUBPROCESS_TIMEOUT_SECONDS: int = 8
MYPY_DETACHED_TIMEOUT_SKIP_MESSAGE: str = (
    "mypy timed out on a detached file; skipping"
)
