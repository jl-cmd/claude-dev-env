"""Constants for the CLAUDE.md orphan-file blocker parts.

Holds the newline that joins a region's lines before scanning it for a
relative-path source, the separator that joins the missing filenames in the deny
reason, and the retry hint the deny reason closes with once the denied inventory
row has been recorded as a pending intent.
"""

from __future__ import annotations

NEWLINE_JOIN_SEPARATOR: str = "\n"

MISSING_NAME_JOIN_SEPARATOR: str = ", "

ROW_FIRST_RETRY_HINT: str = (
    " This inventory row has been recorded: create the file it names now, and the "
    "row will be allowed when you retry it."
)
