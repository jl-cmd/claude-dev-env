"""Constants for the non-breaking-finding follow-up ledger."""

from __future__ import annotations

__all__ = [
    "FOLLOWUP_LEDGER_RELATIVE_PATH",
    "LEDGER_ENCODING",
    "LEDGER_APPEND_MODE",
    "RULE_ID_KEY",
    "FILE_PATH_KEY",
    "MESSAGE_KEY",
    "SEVERITY_BREAKING",
    "SEVERITY_SMELL",
    "ALL_SEVERITY_NAMES",
]

FOLLOWUP_LEDGER_RELATIVE_PATH: tuple[str, ...] = (".claude", "followups", "smells.jsonl")
LEDGER_ENCODING: str = "utf-8"
LEDGER_APPEND_MODE: str = "a"

RULE_ID_KEY: str = "rule_id"
FILE_PATH_KEY: str = "file_path"
MESSAGE_KEY: str = "message"

SEVERITY_BREAKING: str = "breaking"
SEVERITY_SMELL: str = "smell"
ALL_SEVERITY_NAMES: frozenset[str] = frozenset({SEVERITY_BREAKING, SEVERITY_SMELL})
