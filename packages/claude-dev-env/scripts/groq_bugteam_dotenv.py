"""Load ``packages/claude-dev-env/.env`` into ``os.environ`` for local Groq use.

Does not override variables already set in the process environment. Uses a
minimal KEY=value parser (stdlib only) so ``groq_bugteam.py`` stays dependency
free.
"""

from __future__ import annotations

import os
from pathlib import Path


def claude_dev_env_dotenv_path() -> Path:
    """Absolute path to the gitignored ``.env`` beside ``groq_bugteam.py``'s package."""
    return Path(__file__).resolve().parent.parent / ".env"


def load_claude_dev_env_dotenv_file(dotenv_path: Path | None = None) -> None:
    """Apply KEY=value lines from the dotenv file when the file exists."""
    resolved_path = dotenv_path if dotenv_path is not None else claude_dev_env_dotenv_path()
    if not resolved_path.is_file():
        return
    raw_text = resolved_path.read_text(encoding="utf-8")
    for each_line in raw_text.splitlines():
        stripped_line = each_line.strip()
        if not stripped_line or stripped_line.startswith("#"):
            continue
        if stripped_line.startswith("export "):
            stripped_line = stripped_line.removeprefix("export ").strip()
        if "=" not in stripped_line:
            continue
        key_part, _, value_part = stripped_line.partition("=")
        key_name = key_part.strip()
        value_text = value_part.strip()
        if len(value_text) >= 2 and value_text[0] == value_text[-1] and value_text[0] in "\"'":
            value_text = value_text[1:-1]
        if not key_name or key_name in os.environ:
            continue
        os.environ[key_name] = value_text
