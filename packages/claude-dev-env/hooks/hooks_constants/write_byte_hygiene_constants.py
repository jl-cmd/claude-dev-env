"""Constants for the write-byte hygiene PostToolUse hook."""

from __future__ import annotations

from typing import Literal

__all__ = [
    "HygieneStatus",
    "CRLF_ERROR_MESSAGE",
    "NUL_ERROR_MESSAGE",
    "ALLOWED_TOOL_NAMES",
    "CARRIAGE_RETURN_BYTE",
    "NUL_BYTE",
    "HYGIENE_EXIT_CODE",
]

HygieneStatus = Literal["ok", "crlf", "nul"]

CRLF_ERROR_MESSAGE: str = "ERROR: CRLF detected"
NUL_ERROR_MESSAGE: str = "ERROR: NUL byte detected"
ALLOWED_TOOL_NAMES: frozenset[str] = frozenset({"Write", "Edit"})
CARRIAGE_RETURN_BYTE: bytes = b"\r"
NUL_BYTE: bytes = b"\x00"
HYGIENE_EXIT_CODE: int = 2
