"""Named constants for the Codex findings parser."""

from __future__ import annotations

FINDING_KEY_TITLE = "title"
FINDING_KEY_PRIORITY = "priority"
FINDING_KEY_FILE = "file"
FINDING_KEY_LINE_RANGE = "line_range"
FINDING_KEY_BODY = "body"
FENCED_JSON_BLOCK_PATTERN = r"```(?:json)?\s*\n(.*?)\n```"
FREEFORM_FINDING_LINE_PATTERN = (
    r"^-\s*\[(?P<priority>P\d+)\]\s+"
    r"(?P<title>.+?)\s+[—–-]\s+"
    r"(?P<file_path>.+?):(?P<line_range>\d+-\d+)\s*$"
)
FREEFORM_BULLET_PREFIX = "- ["
EMPTY_STRING = ""
NEWLINE = "\n"
