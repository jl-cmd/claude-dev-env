"""Tests for md_to_html_blocker hook."""

import importlib
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
    hook_dir = os.path.dirname(HOOK_SCRIPT_PATH)
    if hook_dir not in sys.path:
        sys.path.insert(0, hook_dir)

    blocker_module = importlib.import_module("md_to_html_blocker")
    importlib.reload(blocker_module)

    assert hasattr(blocker_module, "_exempt_root_filenames")
    assert "readme.md" in blocker_module._exempt_root_filenames
    assert "changelog.md" in blocker_module._exempt_root_filenames


def test_block_messages_mention_claude_dev_env_source_exemptions():
    """The user-facing block context and system message must mention the
    `packages/claude-dev-env/{agents,docs,skills,rules,system-prompts,commands}/`
    exemption so contributors aren't misled when a `.md` write is denied elsewhere."""
    hook_dir = os.path.dirname(HOOK_SCRIPT_PATH)
    if hook_dir not in sys.path:
        sys.path.insert(0, hook_dir)
    blocker_module = importlib.import_module("md_to_html_blocker")
    importlib.reload(blocker_module)

    context_message = blocker_module._block_context()
    system_message = blocker_module._block_system_message()
    combined_messages = context_message + " " + system_message
    assert "claude-dev-env" in combined_messages, (
        "Block messages must mention claude-dev-env source-directory exemption; "
        f"got context={context_message!r} system={system_message!r}"
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


def test_module_imports_path_segments_from_hooks_constants():
    """The blocker pulls the two leading path segments (`packages` and
    `claude-dev-env`) through the centralised hooks_constants module rather
    than inlining them as raw string literals."""
    hook_dir = os.path.dirname(HOOK_SCRIPT_PATH)
    if hook_dir not in sys.path:
        sys.path.insert(0, hook_dir)
    blocker_module = importlib.import_module("md_to_html_blocker")
    importlib.reload(blocker_module)
    assert blocker_module.PACKAGES_TOP_LEVEL_SEGMENT == "packages"
    assert blocker_module.CLAUDE_DEV_ENV_REPO_NAME_SEGMENT == "claude-dev-env"


def test_module_imports_top_directories_from_hooks_constants():
    """The exempt-top-directories set must live in `hooks_constants/` rather
    than as a file-global single-use constant in the blocker module. The
    blocker imports the centralized constant; a regression that reintroduces
    a local module-scope copy would fail this assertion."""
    hook_dir = os.path.dirname(HOOK_SCRIPT_PATH)
    if hook_dir not in sys.path:
        sys.path.insert(0, hook_dir)
    blocker_module = importlib.import_module("md_to_html_blocker")
    importlib.reload(blocker_module)
    assert hasattr(blocker_module, "ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES"), (
        "Blocker module must import ALL_CLAUDE_CODE_SOURCE_TOP_DIRECTORIES from "
        "hooks_constants/ (file-global single-use rule)."
    )
    assert not hasattr(blocker_module, "_claude_code_source_top_directories"), (
        "Local _claude_code_source_top_directories must not be re-introduced; "
        "use the imported constant from hooks_constants/ instead."
    )


def test_blocks_nested_packages_claude_dev_env_path():
    """`packages/claude-dev-env/` exemption is anchored to top-level use only;
    a nested directory like `notes/packages/claude-dev-env/docs/...` is NOT a
    Claude Code source path and must still be blocked. Substring matching let
    this bypass through; segment-anchored matching prevents it."""
    result = _run_hook(
        "Write",
        {"file_path": "notes/packages/claude-dev-env/docs/guide.md", "content": "# Hello"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny", (
        f"Nested fake claude-dev-env path must still be blocked; got {output!r}"
    )


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


def test_passes_claude_code_source_agents_dir():
    """Agent SKILLs live at packages/claude-dev-env/agents/ and must be .md to load."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/claude-dev-env/agents/pr-description-writer.md",
            "content": "---\nname: x\n---\n# Agent",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_code_source_docs_dir():
    """Docs referenced from CLAUDE.md (CODE_RULES.md, guides) live at packages/claude-dev-env/docs/."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/claude-dev-env/docs/PR_DESCRIPTION_GUIDE.md",
            "content": "# Guide",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_code_source_skills_dir():
    """SKILL.md files live at packages/claude-dev-env/skills/."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/claude-dev-env/skills/my-skill/SKILL.md",
            "content": "# SKILL",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_code_source_rules_dir():
    """Rule .md files live at packages/claude-dev-env/rules/."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/claude-dev-env/rules/my-rule.md",
            "content": "# Rule",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_code_source_windows_path():
    """Windows-style backslash paths under packages/claude-dev-env/agents/ must also pass."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages\\claude-dev-env\\agents\\pr-description-writer.md",
            "content": "---\nname: x\n---\n# Agent",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_code_source_absolute_path():
    """Absolute path under packages/claude-dev-env/agents/ must pass on Windows-style drive letter."""
    result = _run_hook(
        "Write",
        {
            "file_path": "Y:\\repo\\packages\\claude-dev-env\\agents\\my-agent.md",
            "content": "# Agent",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_md_under_packages_but_not_in_source_subdir():
    """A .md file under packages/claude-dev-env/hooks/blocking/ is not an exempt source dir."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/claude-dev-env/hooks/blocking/notes.md",
            "content": "# Notes",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
