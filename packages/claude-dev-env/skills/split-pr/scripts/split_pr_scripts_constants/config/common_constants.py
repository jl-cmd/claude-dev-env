"""CLI exit codes, JSON shaping, and gh invocation names shared package-wide.

Every other module in this package imports these names instead of restating
them. One definition per value keeps the sibling modules from disagreeing when
one of them is edited alone.
"""

from __future__ import annotations

EXIT_CODE_SUCCESS = 0
EXIT_CODE_FAILURE = 1

PAYLOAD_KEY_ERROR = "error"
JSON_INDENT_SPACES = 2

ALL_EMPTY_ERROR_CONTEXT: tuple[object, ...] = ()

PATH_SEPARATOR = "/"
FIELD_LIST_SEPARATOR = ","
BLANK_LINE = ""

GH_COMMAND = "gh"
GH_PR = "pr"
GH_VIEW = "view"
GH_JSON_FLAG = "--json"
GH_REPO_FLAG = "--repo"
