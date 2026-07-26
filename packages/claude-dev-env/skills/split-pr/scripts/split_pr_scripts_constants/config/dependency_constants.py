"""Field names and messages for slice dependency verification."""

from __future__ import annotations

PYTHON_FILE_SUFFIX = ".py"

# Mirrors the dead-config-field hook: only dataclasses whose name ends in one of
# these suffixes are judged across modules, and only production modules count as
# readers.
ALL_CONFIG_CLASS_NAME_SUFFIXES = ("Config", "Selectors")
ALL_TEST_PATH_MARKERS = ("tests/", "test_", "_test.py", "conftest.py")
ALL_MIGRATION_PATH_MARKERS = ("migrations/",)

REPORT_KEY_IS_VALID = "is_valid"
REPORT_KEY_FORWARD_REFERENCES = "forward_references"
REPORT_KEY_UNREAD_CONFIG_FIELDS = "unread_config_fields"
REPORT_KEY_COALESCE_SUGGESTION = "coalesce_suggestion"
REPORT_KEY_CONTRADICTIONS = "contradictions"
REPORT_KEY_ERRORS = "errors"

VERIFY_KEY_DEPENDENCIES = "dependencies"
DEPENDENCY_SKIP_KEY = "skipped"
DEPENDENCY_SKIP_REASON = "no --repo-path given, so slice dependencies were not checked"

VIOLATION_KEY_SYMBOL = "symbol"
VIOLATION_KEY_FIELD = "field"
VIOLATION_KEY_FILE = "file"
VIOLATION_KEY_REFERENCING_SLICE = "referencing_slice"
VIOLATION_KEY_DEFINING_SLICE = "defining_slice"
VIOLATION_KEY_SLICE = "slice"
VIOLATION_KEY_EARLIEST_READER_SLICE = "earliest_reader_slice"
VIOLATION_KEY_CURRENT_SLICE = "current_slice"
VIOLATION_KEY_UNCOVERED_FIELDS = "fields_without_an_earlier_reader"

JSON_INDENT_SPACES = 2
LIST_JOIN_SEPARATOR = ", "
STAR_IMPORT_NAME = "*"

SLICE_KEY_INDEX = "index"
SLICE_KEY_SLUG = "slug"
SLICE_KEY_FILES = "files"

ERROR_FORWARD_REFERENCE = (
    "slice %s (%s) reads %r in %s, but only slice %s defines it - "
    "move the defining file to slice %s or earlier"
)
ERROR_UNREAD_CONFIG_FIELD = (
    "slice %s (%s) adds config field %r that no production module in that slice "
    "or earlier reads - the dead-config-field gate rejects this commit"
)
ERROR_COALESCE_HINT = (
    "no ordering satisfies both constraints; ship these files in one slice: %s"
)
ERROR_CONTRADICTION = (
    "%s cannot be ordered: its readers need it by slice %s, but moving it there "
    "leaves config field(s) %s with no earlier production reader, which the "
    "dead-config-field gate rejects"
)

EXIT_CODE_SUCCESS = 0
EXIT_CODE_FAILURE = 1
