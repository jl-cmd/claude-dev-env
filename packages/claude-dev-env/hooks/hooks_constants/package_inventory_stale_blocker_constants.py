"""Constants for the package-inventory stale-entry blocker.

A package directory documents its own files in a sibling inventory document —
a ``README.md`` Layout table, a ``CLAUDE.md`` "Key files" list, or a skill
``SKILL.md`` Layout table that maps the ``scripts/`` subdirectory — whose entries
name each file in backticks. When a new production code file lands in that
directory and the inventory carries no entry naming it, the inventory disagrees
with the directory on the package's file set, and a reader trusting the
inventory to map the directory misses the new file. This module holds the
inventory document names, the production code extensions that earn an inventory
entry, the backtick pattern that finds an inventory's named files, the code-fence
pattern that marks lines to skip, the glob-metacharacter pattern that rejects
pattern tokens, the non-filename pattern that rejects command-example and
path-bearing prose spans, the minimum inventory size that marks a document as a
maintained inventory, the filenames exempt from an entry, the scan budget, and
the block-message text the hook emits.
"""

import re

__all__ = [
    "ALL_INVENTORY_DOCUMENT_NAMES",
    "SKILL_INVENTORY_DOCUMENT_NAME",
    "SCRIPTS_SUBDIRECTORY_NAME",
    "ALL_PRODUCTION_CODE_EXTENSIONS",
    "PYTHON_FILE_EXTENSION",
    "ALL_TEST_FILE_MARKERS",
    "BACKTICK_TOKEN_PATTERN",
    "CODE_FENCE_PATTERN",
    "GLOB_METACHARACTER_PATTERN",
    "NON_FILENAME_TOKEN_PATTERN",
    "MINIMUM_INVENTORY_ENTRY_COUNT",
    "ALL_EXEMPT_BASENAMES",
    "ALL_EXEMPT_DIRECTORY_NAMES",
    "MAX_INVENTORY_FILE_BYTES",
    "STALE_INVENTORY_MESSAGE_TEMPLATE",
    "STALE_INVENTORY_SYSTEM_MESSAGE",
    "STALE_INVENTORY_ADDITIONAL_CONTEXT",
]

SKILL_INVENTORY_DOCUMENT_NAME: str = "SKILL.md"

SCRIPTS_SUBDIRECTORY_NAME: str = "scripts"

ALL_INVENTORY_DOCUMENT_NAMES: frozenset[str] = frozenset(
    {"README.md", "CLAUDE.md", SKILL_INVENTORY_DOCUMENT_NAME}
)

PYTHON_FILE_EXTENSION: str = ".py"

ALL_TEST_FILE_MARKERS: tuple[str, ...] = (".spec.", ".test.")

ALL_PRODUCTION_CODE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".py",
        ".mjs",
        ".js",
        ".ts",
        ".ps1",
        ".sh",
    }
)

BACKTICK_TOKEN_PATTERN: re.Pattern[str] = re.compile(r"`([^`]+)`")

CODE_FENCE_PATTERN: re.Pattern[str] = re.compile(r"^\s*(?:```|~~~)")

GLOB_METACHARACTER_PATTERN: re.Pattern[str] = re.compile(r"[*?{}\[\]]")

NON_FILENAME_TOKEN_PATTERN: re.Pattern[str] = re.compile(r"[\s:$<>]")

MINIMUM_INVENTORY_ENTRY_COUNT: int = 2

ALL_EXEMPT_BASENAMES: frozenset[str] = frozenset(
    {
        "__init__.py",
        "conftest.py",
        "setup.py",
        "_path_setup.py",
    }
)

ALL_EXEMPT_DIRECTORY_NAMES: frozenset[str] = frozenset(
    {
        "config",
        "tests",
        "__pycache__",
        ".git",
        "node_modules",
        ".pytest_cache",
        ".ruff_cache",
    }
)

MAX_INVENTORY_FILE_BYTES: int = 200_000

STALE_INVENTORY_MESSAGE_TEMPLATE: str = (
    "New production file `{filename}` lands in {directory}, whose inventory "
    "document(s) ({inventories}) name {entry_count} sibling files but no entry "
    "for `{filename}`. A package inventory names every production file in its "
    "directory; a new file the inventory omits leaves the inventory and the "
    "directory disagreeing on the package's file set. Add an entry naming "
    "`{filename}` to the inventory in this same change."
)

STALE_INVENTORY_SYSTEM_MESSAGE: str = (
    "New production file is absent from its package inventory (README.md / "
    "CLAUDE.md / SKILL.md) - add the inventory entry in this same change"
)

STALE_INVENTORY_ADDITIONAL_CONTEXT: str = (
    "A package directory whose README.md, CLAUDE.md, or SKILL.md lists its files "
    "in backticks is a maintained inventory of the package's file set. A skill "
    "SKILL.md Layout table that maps the scripts/ subdirectory counts as the "
    "inventory for files in that subdirectory. A new production code file (.py, "
    ".mjs, .js, .ts, .ps1, .sh) in an inventoried directory carries one entry "
    "naming it. Add a row to the README.md or SKILL.md table or a bullet to the "
    "CLAUDE.md list naming this file, describing what it does, in the same change "
    "that creates the file. Exempt files (no entry needed): "
    "__init__.py, conftest.py, setup.py, _path_setup.py, files under config/ or "
    "tests/, and test files (test_*.py, *_test.py, *.spec.*, *.test.*)."
)
