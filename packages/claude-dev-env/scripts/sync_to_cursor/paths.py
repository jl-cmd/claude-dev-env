"""Resolve Claude / Cursor layout paths (LLM_SETTINGS_ROOT or home)."""

import os
from pathlib import Path


def llm_layout_paths() -> tuple[Path, Path, Path, Path]:
    """Return (claude_dir, cursor_dir, rules_out_dir, manifest_path)."""
    raw = os.environ.get("LLM_SETTINGS_ROOT", "").strip()
    if raw:
        base = Path(raw).expanduser().resolve()
        claude = base / ".claude"
        cursor = base / ".cursor"
    else:
        home = Path.home()
        claude = home / ".claude"
        cursor = home / ".cursor"
    return claude, cursor, cursor / "rules", cursor / ".sync-manifest.json"
