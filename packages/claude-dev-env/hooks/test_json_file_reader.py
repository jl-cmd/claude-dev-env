"""Behavior tests for safe JSON-object reads."""

import sys
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from json_file_reader import read_json_object


def test_read_json_object_returns_decoded_mapping(tmp_path: Path) -> None:
    file_path = tmp_path / "state.json"
    file_path.write_text('{"status": "ready"}', encoding="utf-8")

    assert read_json_object(file_path, "utf-8") == {"status": "ready"}


def test_read_json_object_returns_none_for_invalid_bytes(tmp_path: Path) -> None:
    file_path = tmp_path / "state.json"
    file_path.write_bytes(b"\xff")

    assert read_json_object(file_path, "utf-8") is None
