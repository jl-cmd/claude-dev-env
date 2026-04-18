#!/usr/bin/env python3
"""Generate Cursor rules from ~/.claude/rules and docs.

Writes to <profile or repo>/.cursor/rules/*.mdc, .cursor/docs/*.md (byte copies of
CODE_RULES.md and TEST_QUALITY.md when present), and .cursor/.sync-manifest.json.
If LLM_SETTINGS_ROOT is set to the llm-settings repo root, uses <root>/.claude and
<root>/.cursor. Otherwise uses ~/.claude and ~/.cursor (after junction install).
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from sync_to_cursor.engine import main

if __name__ == "__main__":
    sys.exit(main())
