"""Tests for md_to_html_blocker hook."""

import json
import os
import subprocess
import sys


HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "md_to_html_blocker.py")


class _RunHook:
    def __call__(self, tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        return subprocess.run(
            [sys.executable, HOOK_SCRIPT_PATH],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
        )


_run_hook = _RunHook()


def test_exempt_root_filenames_are_module_constant():
    """Exempt root filenames should be a module-level constant, not inline in the function body."""
    import importlib
    import sys
    hook_dir = os.path.dirname(HOOK_SCRIPT_PATH)
    if hook_dir not in sys.path:
        sys.path.insert(0, hook_dir)

    import md_to_html_blocker as blocker_module
    importlib.reload(blocker_module)

    assert hasattr(blocker_module, "_exempt_root_filenames")
    assert "readme.md" in blocker_module._exempt_root_filenames
    assert "changelog.md" in blocker_module._exempt_root_filenames


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


def test_passes_claude_dir():
    result = _run_hook(
        "Write",
        {"file_path": ".claude/rules/foo.md", "content": "# Rule"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_nested_claude_dir():
    result = _run_hook(
        "Write",
        {"file_path": "notes/.claude/plans/plan.md", "content": "# Plan"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_readme_at_root():
    result = _run_hook(
        "Write",
        {"file_path": "README.md", "content": "# README"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_changelog_at_root():
    result = _run_hook(
        "Write",
        {"file_path": "CHANGELOG.md", "content": "# Changelog"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_readme_not_at_root():
    result = _run_hook(
        "Write",
        {"file_path": "docs/README.md", "content": "# README"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_changelog_not_at_root():
    result = _run_hook(
        "Write",
        {"file_path": "sub/CHANGELOG.md", "content": "# Log"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


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
    payload = json.dumps(
        {"tool_name": 123, "tool_input": {"file_path": "docs/guide.md"}}
    )
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


def test_denial_has_system_message():
    result = _run_hook(
        "Write",
        {"file_path": "docs/guide.md", "content": "# Hello"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["suppressOutput"] is True
    assert isinstance(output["systemMessage"], str)
    assert len(output["systemMessage"]) > 0


def test_denial_has_additional_context():
    result = _run_hook(
        "Write",
        {"file_path": "docs/guide.md", "content": "# Hello"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    ctx = output["hookSpecificOutput"].get("additionalContext", "")
    assert "HTML" in ctx
    assert (
        "thariqs.github.io" in output["hookSpecificOutput"]["permissionDecisionReason"]
    )


def test_denial_reason_mentions_html_redirect():
    result = _run_hook(
        "Write",
        {"file_path": "docs/guide.md", "content": "# Hello"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    reason = output["hookSpecificOutput"]["permissionDecisionReason"]
    assert ".html" in reason.lower()


def test_passes_claude_md_file():
    result = _run_hook(
        "Write",
        {"file_path": ".claude/CLAUDE.md", "content": "# CLAUDE.md"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_windows_path_with_backslash():
    result = _run_hook(
        "Write",
        {"file_path": "docs\\guide.md", "content": "# Hello"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_windows_path_claude_exempt():
    result = _run_hook(
        "Write",
        {"file_path": "project\\.claude\\rules\\foo.md", "content": "# Rule"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_dir_case_insensitive():
    result = _run_hook(
        "Write",
        {"file_path": ".Claude/rules/foo.md", "content": "# Rule"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_readme_lowercase_at_root():
    result = _run_hook(
        "Write",
        {"file_path": "readme.md", "content": "# readme"},
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


def test_blocks_claude_path_traversal_bypass():
    result = _run_hook(
        "Write",
        {"file_path": ".claude/../docs/guide.md", "content": "# Bypass"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_md_with_curly_braces_in_path():
    result = _run_hook(
        "Write",
        {"file_path": "docs/{template}.md", "content": "# Template"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
