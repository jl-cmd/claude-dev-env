"""Tests for md_to_html_blocker hook.

Subprocess CWD is rooted in a per-session sandbox created lazily by a
session-scoped fixture so that relative-path test cases canonicalize outside
any `.claude-plugin/` ancestor, outside the OS temp directory, and outside the
exempt home-relative subdirectories. The sandbox is a real repo root (it
carries a `.git` marker) so relative `README.md` / `CHANGELOG.md` writes
exercise the repo-root exemption path. This keeps tests independent of where
pytest itself is run.
"""

import functools
import importlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "md_to_html_blocker.py")


def _strip_read_only_and_retry(removal_function, target_path, *_exc_info):
    try:
        os.chmod(target_path, stat.S_IWRITE)
        removal_function(target_path)
    except OSError:
        pass


def _force_rmtree(target_path: str) -> None:
    handler_kw = (
        {"onexc": _strip_read_only_and_retry}
        if sys.version_info >= (3, 12)
        else {"onerror": _strip_read_only_and_retry}
    )
    try:
        shutil.rmtree(target_path, **handler_kw)
    except OSError:
        pass


@functools.lru_cache(maxsize=1)
def _get_sandbox_parent_directory() -> str:
    sandbox_parent = tempfile.mkdtemp(prefix="pytest_md_blocker_", dir=str(Path.home()))
    git_marker_path = os.path.join(sandbox_parent, ".git")
    Path(git_marker_path).touch()
    return sandbox_parent


@pytest.fixture(scope="session", autouse=True)
def _cleanup_sandbox_parent_directory():
    yield
    if _get_sandbox_parent_directory.cache_info().currsize:
        _force_rmtree(_get_sandbox_parent_directory())
        _get_sandbox_parent_directory.cache_clear()


class _RunHook:
    def __call__(self, tool_name: str, tool_input: dict) -> subprocess.CompletedProcess:
        payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        return subprocess.run(
            [sys.executable, HOOK_SCRIPT_PATH],
            input=payload,
            capture_output=True,
            text=True,
            check=False,
            cwd=_get_sandbox_parent_directory(),
        )


_run_hook = _RunHook()


def test_block_messages_mention_claude_dev_env_source_exemptions():
    """Block messages must surface the `packages/claude-dev-env/<dir>/` anchored
    exemption so contributors aren't misled when a `.md` write is denied
    elsewhere. Ensures docs/, rules/, and system-prompts/ source files
    render as writable in the user-facing message."""
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


def test_blocks_relative_readme_when_cwd_is_not_repo_root():
    sandbox_parent = _get_sandbox_parent_directory()
    non_repo_cwd = os.path.join(sandbox_parent, "not-a-repo")
    os.makedirs(non_repo_cwd, exist_ok=True)
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "README.md", "content": "# README"},
        }
    )
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        cwd=non_repo_cwd,
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


def test_passes_home_session_log_directory():
    home_directory = os.path.expanduser("~")
    session_log_path = os.path.join(home_directory, "SessionLog", "decisions", "note.md")
    result = _run_hook(
        "Write",
        {"file_path": session_log_path, "content": "# Note"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_home_claude_plans_directory():
    home_directory = os.path.expanduser("~")
    plans_path = os.path.join(home_directory, ".claude", "plans", "plan.md")
    result = _run_hook(
        "Write",
        {"file_path": plans_path, "content": "# Plan"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_home_directory_other_md_file():
    home_directory = os.path.expanduser("~")
    other_path = os.path.join(home_directory, "docs", "guide.md")
    result = _run_hook(
        "Write",
        {"file_path": other_path, "content": "# Guide"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_tilde_session_log_path():
    result = _run_hook(
        "Write",
        {"file_path": "~/SessionLog/decisions/note.md", "content": "# Note"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_tilde_claude_plans_path():
    result = _run_hook(
        "Write",
        {"file_path": "~/.claude/plans/plan.md", "content": "# Plan"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_tilde_other_home_md_file():
    result = _run_hook(
        "Write",
        {"file_path": "~/docs/guide.md", "content": "# Guide"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_system_temp_directory():
    temp_md_path = os.path.join(tempfile.gettempdir(), "bugteam-scratch", "pr-body.md")
    result = _run_hook(
        "Write",
        {"file_path": temp_md_path, "content": "# Scratch"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_dot_claude_plugin_directory():
    result = _run_hook(
        "Write",
        {"file_path": ".claude-plugin/manifest.md", "content": "# Manifest"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_nested_dot_claude_plugin_directory():
    result = _run_hook(
        "Write",
        {
            "file_path": "Y:/repo/.claude-plugin/skills/foo/SKILL.md",
            "content": "# Skill",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_skill_md_at_any_depth():
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/dev-env/skills/pr-converge/SKILL.md",
            "content": "# Skill",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_skill_md_uppercase():
    result = _run_hook(
        "Write",
        {"file_path": "any/path/SKILL.MD", "content": "# Skill"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_agents_directory_anywhere():
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/dev-env/agents/pr-description-writer.md",
            "content": "# Agent",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_skills_reference_directory():
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/dev-env/skills/pr-converge/reference/per-tick.md",
            "content": "# Reference",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_commands_directory_anywhere():
    result = _run_hook(
        "Write",
        {"file_path": "commands/pyguide-health.md", "content": "# Command"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_dev_env_docs_dir():
    """A .md file under ``packages/claude-dev-env/docs/`` is exempt. The
    segment-anywhere rule does not list ``docs``; this exemption fires only
    via the anchored helper."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/claude-dev-env/docs/PR_DESCRIPTION_GUIDE.md",
            "content": "# Guide",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_dev_env_rules_dir():
    """A .md file under ``packages/claude-dev-env/rules/`` is exempt. The
    segment-anywhere rule does not list ``rules``; the anchored helper is
    the only path to this exemption."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/claude-dev-env/rules/my-rule.md",
            "content": "# Rule",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_dev_env_system_prompts_dir():
    """A .md file under ``packages/claude-dev-env/system-prompts/`` is
    exempt via the anchored helper."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages/claude-dev-env/system-prompts/new-prompt.md",
            "content": "# Prompt",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_dev_env_windows_backslash_path():
    """A Windows-style backslash relative path under
    ``packages\\claude-dev-env\\<dir>\\`` is exempt."""
    result = _run_hook(
        "Write",
        {
            "file_path": "packages\\claude-dev-env\\docs\\windows-style.md",
            "content": "# Guide",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_claude_dev_env_absolute_drive_letter_path():
    """A Windows absolute drive-letter path containing the anchored
    ``packages\\claude-dev-env\\<dir>\\`` indicator at any depth is exempt."""
    result = _run_hook(
        "Write",
        {
            "file_path": "Y:\\repo\\packages\\claude-dev-env\\docs\\drive-letter.md",
            "content": "# Guide",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_md_under_packages_but_not_in_anchored_source_subdir():
    """A .md file inside the package but under a non-source subtree (e.g.
    ``packages/claude-dev-env/hooks/blocking/``) is blocked. The anchored
    helper accepts only the named source subdirectories (agents, docs,
    skills, rules, system-prompts, commands)."""
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


def test_blocks_nested_claude_dev_env_substring_does_not_bypass():
    """A path that contains the anchored prefix as a non-leading substring
    (e.g. ``notes/packages/claude-dev-env/docs/foo.md``) is blocked. The
    anchored helper matches only at the start of the path (relative) or at
    the root of an absolute path."""
    result = _run_hook(
        "Write",
        {
            "file_path": "notes/packages/claude-dev-env/docs/foo.md",
            "content": "# Notes",
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_blocks_ordinary_docs_md_file():
    result = _run_hook(
        "Write",
        {"file_path": "docs/intro.md", "content": "# Intro"},
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_passes_relative_path_from_home_cwd():
    home_directory = os.path.expanduser("~")
    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "SessionLog/decisions/note.md",
                "content": "# Note",
            },
        }
    )
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        cwd=home_directory,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_canonicalized_home_path():
    canonical_home = os.path.realpath(os.path.expanduser("~"))
    canonical_path = os.path.join(canonical_home, "SessionLog", "canonical-note.md")
    result = _run_hook(
        "Write",
        {"file_path": canonical_path, "content": "# Canonical"},
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_passes_relative_path_under_cwd_plugin_root_marker(tmp_path):
    plugin_root = tmp_path / "plugin-cwd-repo"
    (plugin_root / ".claude-plugin").mkdir(parents=True)
    (plugin_root / "subdir").mkdir(parents=True)

    payload = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "subdir/design.md",
                "content": "# Design",
            },
        }
    )
    result = subprocess.run(
        [sys.executable, HOOK_SCRIPT_PATH],
        input=payload,
        capture_output=True,
        text=True,
        check=False,
        cwd=str(plugin_root),
    )
    assert result.returncode == 0
    assert result.stdout == ""
