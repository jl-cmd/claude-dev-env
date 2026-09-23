"""Constants for the non-breaking-finding follow-up ledger."""

from __future__ import annotations

__all__ = [
    "ALL_FOLLOWUP_LEDGER_PATH_SEGMENTS",
    "LEDGER_ENCODING",
    "LEDGER_APPEND_MODE",
    "LEDGER_IGNORE_FILE_NAME",
    "LEDGER_IGNORE_TEXT",
    "RULE_ID_KEY",
    "FILE_PATH_KEY",
    "MESSAGE_KEY",
    "CHECK_ID_KEY",
    "SEVERITY_KEY",
    "ORIGIN_COMMIT_KEY",
    "ABSENT_ORIGIN_COMMIT",
    "ALL_GIT_HEAD_PATH_SEGMENTS",
    "GIT_DIRECTORY_NAME",
    "GIT_REFERENCE_PREFIX",
    "SEVERITY_BREAKING",
    "SEVERITY_SMELL",
    "ALL_SEVERITY_NAMES",
]

ALL_FOLLOWUP_LEDGER_PATH_SEGMENTS: tuple[str, ...] = (".claude", "followups", "smells.jsonl")
LEDGER_ENCODING: str = "utf-8"
LEDGER_APPEND_MODE: str = "a"
LEDGER_IGNORE_FILE_NAME: str = ".gitignore"
LEDGER_IGNORE_TEXT: str = "*\n"

RULE_ID_KEY: str = "rule_id"
FILE_PATH_KEY: str = "file_path"
MESSAGE_KEY: str = "message"
CHECK_ID_KEY: str = "check_id"
SEVERITY_KEY: str = "severity"
ORIGIN_COMMIT_KEY: str = "origin_commit"

ABSENT_ORIGIN_COMMIT: str = ""
GIT_DIRECTORY_NAME: str = ".git"
ALL_GIT_HEAD_PATH_SEGMENTS: tuple[str, ...] = (GIT_DIRECTORY_NAME, "HEAD")
GIT_REFERENCE_PREFIX: str = "ref: "

SEVERITY_BREAKING: str = "breaking"
SEVERITY_SMELL: str = "smell"
ALL_SEVERITY_NAMES: frozenset[str] = frozenset({SEVERITY_BREAKING, SEVERITY_SMELL})
