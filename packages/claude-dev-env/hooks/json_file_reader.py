"""Safe JSON-object reads for hook-state files."""

import json
from pathlib import Path


def read_json_object(file_path: Path, encoding: str) -> dict[str, object] | None:
    """Return one decoded JSON object.

    Args:
        file_path: The JSON file path.
        encoding: The text encoding.

    Returns:
        The decoded object, or ``None`` for missing, unreadable, or malformed data.
    """
    try:
        raw_text = file_path.read_text(encoding=encoding)
        parsed_payload = json.loads(raw_text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return parsed_payload if isinstance(parsed_payload, dict) else None
