"""Constants for the MSYS path-conversion context advisory.

The advisory is a PostToolUse observer on Bash. It never blocks. When a git
call fails because Git Bash rewrote a ``<rev>:<path>`` argument before git saw
it, the advisory adds one loud note naming the two exports that turn the
rewriting off.
"""

from __future__ import annotations

__all__ = [
    "ALL_MANGLED_ARGUMENT_MARKERS",
    "MANGLED_ARGUMENT_CLOSING_QUOTE",
    "ALL_MSYS_MANGLING_CHARACTERS",
    "MSYS_PATH_CONVERSION_VARIABLE_NAME",
    "MSYS_EXPORT_FIX_LINE",
    "ADVISORY_HEADER",
    "MANGLED_ARGUMENT_LINE_TEMPLATE",
    "MANGLING_EXPLANATION_LINE",
    "FIX_LINE",
    "SAME_COMMAND_LINE",
    "ADVISORY_LINE_SEPARATOR",
]

AMBIGUOUS_ARGUMENT_MARKER: str = "fatal: ambiguous argument '"
INVALID_OBJECT_NAME_MARKER: str = "fatal: invalid object name '"
ALL_MANGLED_ARGUMENT_MARKERS: tuple[str, ...] = (
    AMBIGUOUS_ARGUMENT_MARKER,
    INVALID_OBJECT_NAME_MARKER,
)
MANGLED_ARGUMENT_CLOSING_QUOTE: str = "'"
ALL_MSYS_MANGLING_CHARACTERS: frozenset[str] = frozenset({"\\", ";"})
MSYS_PATH_CONVERSION_VARIABLE_NAME: str = "MSYS_NO_PATHCONV"
MSYS_EXPORT_FIX_LINE: str = "export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'"

ADVISORY_HEADER: str = "=== MSYS PATH CONVERSION (context reminder, never a block) ==="
MANGLED_ARGUMENT_LINE_TEMPLATE: str = "Git saw:     {argument}"
MANGLING_EXPLANATION_LINE: str = (
    "Git Bash rewrote a <rev>:<path> argument before git saw it, turning the "
    "colon into a semicolon and the slashes into backslashes."
)
FIX_LINE: str = "Fix:         " + MSYS_EXPORT_FIX_LINE
SAME_COMMAND_LINE: str = "Put that export and the git command in the same command."
ADVISORY_LINE_SEPARATOR: str = "\n"
