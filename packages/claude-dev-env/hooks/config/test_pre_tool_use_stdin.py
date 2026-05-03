"""Tests for PreToolUse stdin JSON parsing helper."""

from __future__ import annotations

import inspect
import io
import json
import sys
from unittest.mock import patch

from config import pre_tool_use_stdin
from config.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin


def test_pre_tool_use_stdin_uses_shared_encoding_and_decode_constants() -> None:
    """Pin: stdin parsing must use shared constants, not duplicate literals."""
    module_source = inspect.getsource(pre_tool_use_stdin)
    assert "UTF8_ENCODING" in module_source
    assert "DECODE_ERRORS_POLICY" in module_source
    assert "UTF8_BYTE_ORDER_MARK" in module_source
    assert '.decode("utf-8"' not in module_source
    assert 'errors="replace"' not in module_source
    assert "stdin_parse_constants" not in module_source


def test_read_returns_none_for_empty_stdin() -> None:
    with patch("sys.stdin", io.StringIO("")):
        assert read_hook_input_dictionary_from_stdin() is None


def test_read_returns_none_for_whitespace_only_stdin() -> None:
    with patch("sys.stdin", io.StringIO("   \n\t  ")):
        assert read_hook_input_dictionary_from_stdin() is None


def test_read_returns_none_for_invalid_json() -> None:
    with patch("sys.stdin", io.StringIO("not json")):
        assert read_hook_input_dictionary_from_stdin() is None


def test_read_returns_none_for_json_array_root() -> None:
    with patch("sys.stdin", io.StringIO("[1, 2]")):
        assert read_hook_input_dictionary_from_stdin() is None


def test_read_strips_bom_and_returns_dict() -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
    with patch("sys.stdin", io.StringIO("\ufeff" + json.dumps(payload))):
        parsed = read_hook_input_dictionary_from_stdin()
    assert parsed == payload


def test_read_returns_dict_for_valid_json_object() -> None:
    payload = {"tool_name": "Read", "tool_input": {"file_path": "/tmp/x"}}
    with patch("sys.stdin", io.StringIO(json.dumps(payload))):
        parsed = read_hook_input_dictionary_from_stdin()
    assert parsed == payload


def test_read_uses_buffer_when_present() -> None:
    payload = {"tool_name": "Bash", "tool_input": {}}
    raw_bytes = json.dumps(payload).encode("utf-8")
    binary_stream = io.BytesIO(raw_bytes)
    text_wrapper = io.TextIOWrapper(binary_stream, encoding="utf-8")
    with patch("sys.stdin", text_wrapper):
        parsed = read_hook_input_dictionary_from_stdin()
    assert parsed == payload


def test_read_returns_none_when_buffer_and_text_read_raise_attribute_error() -> None:
    class BrokenStandardInput:
        @property
        def buffer(self) -> object:
            raise AttributeError("no buffer")

        def read(self, size: int = -1) -> str:
            raise AttributeError("no read")

    with patch("sys.stdin", BrokenStandardInput()):
        assert read_hook_input_dictionary_from_stdin() is None
