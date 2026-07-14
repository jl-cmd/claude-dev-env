"""Constants for the shared inventory/orphan pending-intent records.

Holds the per-session records-file name shape, the freshness window a pending
note lives inside, the two list keys the file stores under, and the field names
of one stored note.
"""

from __future__ import annotations

INTENT_FILE_PREFIX: str = "claude-inventory-intent-"
INTENT_FILE_SUFFIX: str = ".json"

INTENT_FRESHNESS_WINDOW_SECONDS: float = 900.0

ALL_FILE_INTENTS_KEY: str = "pending_file_intents"
ALL_ROW_INTENTS_KEY: str = "pending_row_intents"

INTENT_DIRECTORY_FIELD: str = "directory"
INTENT_FILENAME_FIELD: str = "filename"
INTENT_RECORDED_AT_FIELD: str = "recorded_at"
