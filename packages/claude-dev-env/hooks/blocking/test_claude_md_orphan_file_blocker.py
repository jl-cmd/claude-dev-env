"""Tests for claude_md_orphan_file_blocker hook."""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from claude_md_orphan_file_blocker import find_missing_filenames

HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "claude_md_orphan_file_blocker.py")

REPO_ROOT = Path(__file__).resolve().parents[4]

TABLE_WITH_PRESENT_FILE = (
    "# example\n\n| File | What it does |\n|---|---|\n| `present_module.py` | Does a thing |\n"
)

TABLE_WITH_ABSENT_FILE = (
    "# example\n\n| File | What it does |\n|---|---|\n| `reviewer_specs.py` | Does a thing |\n"
)

TABLE_WITH_ABSENT_README = (
    "# example\n\n| Document | Purpose |\n|---|---|\n| `README.md` | Overview |\n"
)

TABLE_WITH_SLASH_COMMAND_AND_SUBDIR = (
    "# example\n\n"
    "| Entry | Description |\n"
    "|---|---|\n"
    "| `/commit` | Slash command |\n"
    "| `scripts/` | A subdirectory |\n"
    "| Plain prose, no backticks | Not a file |\n"
)


class _RunHook:
    """Helper to test the hook via subprocess, mirroring the sibling test style."""

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


def _isolated_claude_md_path(tmp_path: Path) -> Path:
    """Return a CLAUDE.md path nested in a dedicated empty directory.

    Nesting the CLAUDE.md inside a child of tmp_path keeps the hook's scan root
    (the CLAUDE.md directory's parent) controlled, so a sibling test's temp
    content never resolves a filename the case expects to be absent.
    """
    isolated_directory = tmp_path / "package_directory"
    isolated_directory.mkdir()
    return isolated_directory / "CLAUDE.md"


def test_blocks_write_naming_absent_python_file(tmp_path: Path):
    claude_md_path = _isolated_claude_md_path(tmp_path)
    result = _run_hook(
        "Write",
        {
            "file_path": str(claude_md_path),
            "content": TABLE_WITH_ABSENT_FILE,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "reviewer_specs.py" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_blocks_write_naming_absent_markdown_file(tmp_path: Path):
    claude_md_path = _isolated_claude_md_path(tmp_path)
    result = _run_hook(
        "Write",
        {
            "file_path": str(claude_md_path),
            "content": TABLE_WITH_ABSENT_README,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "README.md" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_allows_write_when_referenced_file_present(tmp_path: Path):
    (tmp_path / "present_module.py").write_text("x = 1\n", encoding="utf-8")
    claude_md_path = tmp_path / "CLAUDE.md"
    result = _run_hook(
        "Write",
        {
            "file_path": str(claude_md_path),
            "content": TABLE_WITH_PRESENT_FILE,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_allows_non_claude_md_target(tmp_path: Path):
    other_path = tmp_path / "README.md"
    result = _run_hook(
        "Write",
        {
            "file_path": str(other_path),
            "content": TABLE_WITH_ABSENT_FILE,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_allows_slash_commands_subdirs_and_prose(tmp_path: Path):
    claude_md_path = tmp_path / "CLAUDE.md"
    result = _run_hook(
        "Write",
        {
            "file_path": str(claude_md_path),
            "content": TABLE_WITH_SLASH_COMMAND_AND_SUBDIR,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_blocks_via_edit_new_string(tmp_path: Path):
    claude_md_path = _isolated_claude_md_path(tmp_path)
    result = _run_hook(
        "Edit",
        {
            "file_path": str(claude_md_path),
            "old_string": "| `old.py` | row |",
            "new_string": TABLE_WITH_ABSENT_FILE,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "reviewer_specs.py" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_blocks_via_multiedit_new_string(tmp_path: Path):
    claude_md_path = _isolated_claude_md_path(tmp_path)
    (claude_md_path.parent / "present_module.py").write_text("x = 1\n", encoding="utf-8")
    result = _run_hook(
        "MultiEdit",
        {
            "file_path": str(claude_md_path),
            "edits": [
                {"old_string": "a", "new_string": TABLE_WITH_PRESENT_FILE},
                {"old_string": "b", "new_string": TABLE_WITH_ABSENT_FILE},
            ],
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "reviewer_specs.py" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_block_payload_carries_directory_and_system_message(tmp_path: Path):
    claude_md_path = _isolated_claude_md_path(tmp_path)
    result = _run_hook(
        "Write",
        {
            "file_path": str(claude_md_path),
            "content": TABLE_WITH_ABSENT_FILE,
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["suppressOutput"] is True
    assert isinstance(output["systemMessage"], str)
    assert len(output["systemMessage"]) > 0
    assert str(claude_md_path.parent.resolve()) in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_allows_file_present_in_subdirectory(tmp_path: Path):
    workflows_dir = tmp_path / "workflows"
    workflows_dir.mkdir()
    (workflows_dir / "pr-check.yml").write_text("name: ci\n", encoding="utf-8")
    claude_md_path = tmp_path / "CLAUDE.md"
    content = (
        "# example\n\n"
        "| File | Trigger |\n"
        "|---|---|\n"
        "| `pr-check.yml` | PR opened |\n"
    )
    result = _run_hook(
        "Write",
        {
            "file_path": str(claude_md_path),
            "content": content,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_allows_table_declaring_relative_path_source(tmp_path: Path):
    claude_md_path = tmp_path / "CLAUDE.md"
    content = (
        "# example\n\n"
        "## Shared artifacts (referenced by path, not copied)\n\n"
        "The skill references shared scripts from `../_shared/pr-loop/scripts/`:\n\n"
        "| Script | Role |\n"
        "|---|---|\n"
        "| `preflight.py` | Pre-flight check |\n"
    )
    result = _run_hook(
        "Write",
        {
            "file_path": str(claude_md_path),
            "content": content,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_separator_row_is_skipped(tmp_path: Path):
    claude_md_path = tmp_path / "CLAUDE.md"
    content = "| File | Note |\n|---|---|\n"
    result = _run_hook(
        "Write",
        {
            "file_path": str(claude_md_path),
            "content": content,
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_every_repo_claude_md_is_not_blocked():
    all_claude_md_paths = sorted(REPO_ROOT.rglob("CLAUDE.md"))
    assert all_claude_md_paths, "expected the repo to contain CLAUDE.md files"
    all_offenders: list[str] = []
    for each_path in all_claude_md_paths:
        content = each_path.read_text(encoding="utf-8")
        missing_filenames = find_missing_filenames(content, each_path.parent)
        if missing_filenames:
            all_offenders.append(f"{each_path}: {missing_filenames}")
    assert not all_offenders, "\n".join(all_offenders)
