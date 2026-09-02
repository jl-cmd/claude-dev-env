"""Constants for the shared source reader and parser in validator_base."""

from __future__ import annotations

# One save validates one file, so a handful of entries covers a run and keeps
# a long-lived CLI pass from holding every file it ever read.
SOURCE_CACHE_ENTRIES: int = 8

SOURCE_ENCODING: str = "utf-8"
