"""Tests for md_to_html_blocker extension matching and malformed-input handling.

Covers the core decision: which file extensions and tool names trigger a deny,
which pass through, and how the hook degrades on malformed or non-dict stdin.
"""

import json
import os
import subprocess
import sys

_BLOCKING_DIRECTORY = os.path.dirname(__file__)

if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)

from _md_to_html_blocker_test_support import (  # noqa: E402
    HOOK_SCRIPT_PATH,
    _run_hook,
)


def test_blocks_write_md_file():
    result = _run_hook(
        "Write",
        {"file_path": "docs/guide.md", "content": "# Hello"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_edit_md_file():
    result = _run_hook(
        "Edit",
        {"file_path": "docs/guide.md", "old_string": "a", "new_string": "b"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_uppercase_md_extension():
    result = _run_hook(
        "Write",
        {"file_path": "DOCS/GUIDE.MD", "content": "# Hello"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_html_file():
    result = _run_hook(
        "Write",
        {"file_path": "docs/guide.html", "content": "<h1>Hello</h1>"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_non_markdown_extension():
    result = _run_hook(
        "Write",
        {"file_path": "src/main.py", "content": "x = 1"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_unknown_tool_passes():
    result = _run_hook(
        "Grep",
        {"pattern": "foo", "path": "."},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_empty_file_path_passes():
    result = _run_hook(
        "Write",
        {"file_path": "", "content": "# Hello"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_non_dict_stdin_passes():
    payload = json.dumps(["not", "a", "dict"])
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_non_string_tool_name_passes():
    payload = json.dumps({"tool_name": 123, "tool_input": {"file_path": "docs/guide.md"}})
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_non_dict_tool_input_passes():
    payload = json.dumps({"tool_name": "Write", "tool_input": "not_a_dict"})
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_json_decode_error_passes():
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input="not json",
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_md_with_curly_braces_in_path():
    result = _run_hook(
        "Write",
        {"file_path": "docs/{template}.md", "content": "# Template"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_windows_path_with_backslash():
    result = _run_hook(
        "Write",
        {"file_path": "docs\\guide.md", "content": "# Hello"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
