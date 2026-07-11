"""Configuration constants for the setup_project_paths bootstrap script.

Shared constants consumed by two or more modules across the hook subsystem.
Single-use values are inlined into their consuming functions per the
file-global-constants use-count rule.
"""

from __future__ import annotations

ES_EXE_FOLDERS_ONLY_QUERY_ARGUMENTS = ("/ad", "folder:.git")

EXCLUDED_PATH_SEGMENTS = frozenset(
    {
        "temp",
        "tmp",
        "worktree",
        "node_modules",
        ".cache",
        "$recycle.bin",
    }
)

JSON_INDENT_SPACES = 2

GIT_DIRECTORY_SEGMENT_NAME = ".git"

ES_EXE_BINARY_NAME = "es.exe"

SUPPORTED_SCHEMA_VERSION = 1

META_KEY = "_meta"

UTF8_ENCODING = "utf-8"

DECODE_ERRORS_POLICY = "replace"

UTF8_BYTE_ORDER_MARK = "\ufeff"

CONFIRMATION_PROMPT_TEXT = "Write this mapping to the config file? (yes/no): "

ABORTED_NOTHING_WRITTEN_MESSAGE = "Aborted. Nothing written."

WROTE_ENTRIES_STATUS_TEMPLATE = "Wrote {entry_count} entries to {save_path}."

STDERR_TRUNCATION_LENGTH = 200
