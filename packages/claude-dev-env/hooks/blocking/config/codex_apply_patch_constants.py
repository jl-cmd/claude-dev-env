"""Shared operation-name constants for codex_apply_patch.py.

A Codex apply_patch command names three operations — add, update, and
delete — by a literal marker line. ``CODEX_ADD_OPERATION`` is the single
source of truth for the "add" spelling, so every caller that branches on it
compares against one value rather than a second local copy that could drift.
"""

from __future__ import annotations

CODEX_ADD_OPERATION = "add"
