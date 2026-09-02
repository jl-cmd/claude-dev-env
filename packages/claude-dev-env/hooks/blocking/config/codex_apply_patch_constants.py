"""Shared operation-name constants for codex_apply_patch.py.

A Codex apply_patch command names three operations — add, update, and
delete — by a literal marker line. These three constants are the single
source of truth for those spellings, so every caller that branches on one
compares against one value rather than a second local copy that could drift.
"""

from __future__ import annotations

CODEX_ADD_OPERATION = "add"
CODEX_UPDATE_OPERATION = "update"
CODEX_DELETE_OPERATION = "delete"
