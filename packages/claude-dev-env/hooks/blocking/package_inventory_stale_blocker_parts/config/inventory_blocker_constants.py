"""Constants for the package-inventory blocker parts.

Holds the separator that joins the present inventory document names in the deny
reason, and the retry hint the deny reason closes with once the denied file write
has been recorded as a pending intent.
"""

from __future__ import annotations

INVENTORY_NAME_JOIN_SEPARATOR: str = ", "

FILE_FIRST_RETRY_HINT: str = (
    " This file write has been recorded: add the inventory entry naming this file "
    "now (a README.md/CLAUDE.md/SKILL.md row or bullet), and the file write will "
    "be allowed when you retry it."
)
