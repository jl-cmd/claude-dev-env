"""Table names used when a validator resolves its config from a pyproject.toml.

A ``pyproject.toml`` nests each tool's settings under ``[tool.<name>]``, so the
top-level table key is ``tool`` and each tool matches its own name below it.
These names live here so the discovery module carries no inline table literals.
"""

__all__ = [
    "TOOL_TABLE_KEY",
    "MYPY_TOOL_TABLE_NAME",
    "RUFF_TOOL_TABLE_NAME",
]

TOOL_TABLE_KEY: str = "tool"
MYPY_TOOL_TABLE_NAME: str = "mypy"
RUFF_TOOL_TABLE_NAME: str = "ruff"
