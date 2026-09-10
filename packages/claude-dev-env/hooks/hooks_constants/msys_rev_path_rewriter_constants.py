"""Constants for the MSYS ``<rev>:<path>`` argument-exclusion rewriter.

Git Bash converts a git argument such as ``origin/main:.claude/settings.json``
before git sees it. ``MSYS2_ARG_CONV_EXCL`` takes a semicolon-separated list of
argument prefixes to leave alone, so naming one ``<rev>:`` prefix per detected
token keeps every other argument in the command converting as before.
"""

from __future__ import annotations

from hooks_constants.msys_path_conversion_advisor_constants import (
    MSYS_ARGUMENT_CONVERSION_EXCLUSION_VARIABLE_NAME,
)

__all__ = [
    "GIT_PROGRAM_NAME",
    "REVISION_PATH_SEPARATOR",
    "REVISION_PATH_SPLIT_COUNT",
    "REVISION_SLASH_CHARACTER",
    "ALL_CONVERTED_PATH_START_CHARACTERS",
    "ALL_UNCONVERTED_PATH_START_PREFIXES",
    "EXCLUSION_PREFIX_JOIN_SEPARATOR",
    "EXCLUSION_EXPORT_TEMPLATE",
]

GIT_PROGRAM_NAME: str = "git"
REVISION_PATH_SEPARATOR: str = ":"
REVISION_PATH_SPLIT_COUNT: int = 1
REVISION_SLASH_CHARACTER: str = "/"
ALL_CONVERTED_PATH_START_CHARACTERS: tuple[str, ...] = ("/", ".")
ALL_UNCONVERTED_PATH_START_PREFIXES: tuple[str, ...] = ("./", "../")
EXCLUSION_PREFIX_JOIN_SEPARATOR: str = ";"
EXCLUSION_EXPORT_TEMPLATE: str = (
    "export " + MSYS_ARGUMENT_CONVERSION_EXCLUSION_VARIABLE_NAME + "='{all_prefixes}'; "
)
