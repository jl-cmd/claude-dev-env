"""Constants for the tr-sess session transfer script.

Groups: profile layout, transcript record keys, project-entry defaults, CLI
flags, JSON payload keys, and exit codes.
"""

from __future__ import annotations

PROFILES_ROOT_DIRECTORY_NAME = ".claude-profiles"
PROJECTS_DIRECTORY_NAME = "projects"
CONFIG_FILE_NAME = ".claude.json"
CONFIG_BACKUP_SUFFIX = ".bak-tr-sess"
TRANSCRIPT_SUFFIX = ".jsonl"
ALL_SIDECAR_DIRECTORY_NAMES: tuple[str, ...] = ("tasks", "session-env")

CONFIG_PROJECTS_KEY = "projects"
RECORD_CWD_KEY = "cwd"
RECORD_SESSION_ID_KEY = "sessionId"
RECORD_TYPE_KEY = "type"
RECORD_CUSTOM_TITLE_KEY = "customTitle"
RECORD_AI_TITLE_KEY = "title"
CUSTOM_TITLE_RECORD_TYPE = "custom-title"
AI_TITLE_RECORD_TYPE = "ai-title"

NEWLINE_BYTE = 10
HASH_ALGORITHM_NAME = "sha256"
FILE_READ_CHUNK_SIZE = 1024 * 1024
JSON_INDENT_WIDTH = 2

ALL_PROJECT_ENTRY_DEFAULTS: dict[str, object] = {
    "allowedTools": [],
    "mcpContextUris": [],
    "enabledMcpjsonServers": [],
    "disabledMcpjsonServers": [],
    "hasTrustDialogAccepted": True,
    "projectOnboardingSeenCount": 0,
    "hasClaudeMdExternalIncludesApproved": False,
    "hasClaudeMdExternalIncludesWarningShown": False,
}

PAYLOAD_SOURCE_PROFILE_KEY = "sourceProfile"
PAYLOAD_DESTINATION_PROFILE_KEY = "destinationProfile"
PAYLOAD_SESSION_ID_KEY = "sessionId"
PAYLOAD_PROJECT_KEY = "projectKey"
PAYLOAD_WORKING_DIRECTORY_KEY = "workingDirectory"
PAYLOAD_SOURCE_BYTES_KEY = "sourceBytesAtCopy"
PAYLOAD_COPIED_BYTES_KEY = "copiedBytes"
PAYLOAD_COPIED_LINES_KEY = "copiedLines"
PAYLOAD_HASH_MATCH_KEY = "hashMatch"
PAYLOAD_SIDECARS_KEY = "sidecarsCopied"
PAYLOAD_CONFIG_ACTION_KEY = "configAction"
PAYLOAD_SESSIONS_KEY = "sessions"
PAYLOAD_TITLE_KEY = "title"
PAYLOAD_MODIFIED_KEY = "modifiedEpochSeconds"
PAYLOAD_BYTES_KEY = "bytes"

CONFIG_ACTION_ADDED = "added project entry"
CONFIG_ACTION_PRESENT = "project entry already present"
CONFIG_ACTION_SKIPPED_NO_CWD = "skipped: transcript carries no cwd"
CONFIG_ACTION_SKIPPED_NO_CONFIG = "skipped: destination has no .claude.json"

EXIT_CODE_SUCCESS = 0
EXIT_CODE_USAGE_ERROR = 2
EXIT_CODE_DESTINATION_DIVERGED = 3

DIVERGED_MESSAGE_TEMPLATE = (
    "destination transcript has {destination_bytes} bytes against the source's "
    "{source_bytes}, so the destination carries work the source does not. "
    "Copying would discard it. Re-run with --force to overwrite anyway."
)
