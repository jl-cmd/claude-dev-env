"""Tests for claude_md_orphan_file_blocker hook."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import claude_md_orphan_file_blocker as blocker_module
from claude_md_orphan_file_blocker import (
    find_missing_filenames,
    find_referenced_filenames,
)
from code_rules_annotations_length import check_unused_known_pytest_fixture_parameters
from code_rules_naming_collection import check_collection_prefix

from hooks_constants.claude_md_orphan_file_blocker_constants import (
    ORPHAN_FILE_ADDITIONAL_CONTEXT,
    ORPHAN_FILE_MESSAGE_TEMPLATE,
)

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


def test_relative_path_table_does_not_exempt_sibling_local_table(tmp_path: Path):
    claude_md_path = _isolated_claude_md_path(tmp_path)
    content = (
        "# example\n\n"
        "## Local files\n\n"
        "| File | Note |\n"
        "|---|---|\n"
        "| `reviewer_specs.py` | Does a thing |\n\n"
        "## Shared artifacts\n\n"
        "Referenced from `../_shared/scripts/`:\n\n"
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
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "reviewer_specs.py" in output["hookSpecificOutput"]["permissionDecisionReason"]
    assert "preflight.py" not in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_relative_path_prose_above_its_own_table_exempts_that_table(tmp_path: Path):
    claude_md_path = _isolated_claude_md_path(tmp_path)
    content = (
        "# example\n\n"
        "## Shared artifacts\n\n"
        "Referenced from `../_shared/scripts/`:\n\n"
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


def test_edit_to_relative_path_sourced_table_is_allowed(tmp_path: Path):
    claude_md_path = _isolated_claude_md_path(tmp_path)
    claude_md_path.write_text(
        "# example\n\n"
        "## Shared artifacts\n\n"
        "Referenced from `../_shared/scripts/`:\n\n"
        "| Script | Role |\n"
        "|---|---|\n"
        "| `code_rules_gate.py` | Gate |\n",
        encoding="utf-8",
    )
    result = _run_hook(
        "Edit",
        {
            "file_path": str(claude_md_path),
            "old_string": "| `code_rules_gate.py` | Gate |",
            "new_string": (
                "| `code_rules_gate.py` | Gate |\n"
                "| `preflight.py` | Pre-flight gate that runs before the audit |"
            ),
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_edit_adding_orphan_to_non_exempt_file_is_denied(tmp_path: Path):
    claude_md_path = _isolated_claude_md_path(tmp_path)
    claude_md_path.write_text(
        "# example\n\n"
        "## Local files\n\n"
        "| File | Note |\n"
        "|---|---|\n"
        "| `kept.py` | row |\n",
        encoding="utf-8",
    )
    (claude_md_path.parent / "kept.py").write_text("x = 1\n", encoding="utf-8")
    result = _run_hook(
        "Edit",
        {
            "file_path": str(claude_md_path),
            "old_string": "| `kept.py` | row |",
            "new_string": (
                "| `kept.py` | row |\n| `reviewer_specs.py` | Does a thing |"
            ),
        },
    )
    assert result.returncode == 0
    output = json.loads(result.stdout)
    assert output["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "reviewer_specs.py" in output["hookSpecificOutput"]["permissionDecisionReason"]


def test_block_lines_yield_their_filenames_when_region_is_not_exempt():
    content = (
        "# example\n\n"
        "## Local files\n\n"
        "| File | Note |\n"
        "|---|---|\n"
        "| `alpha.py` | row |\n"
        "| `beta.py` | row |\n"
    )
    assert find_referenced_filenames(content) == ["alpha.py", "beta.py"]


def test_block_lines_yield_nothing_when_region_declares_relative_source():
    content = (
        "# example\n\n"
        "Referenced from `../_shared/scripts/`:\n\n"
        "| Script | Role |\n"
        "|---|---|\n"
        "| `preflight.py` | Pre-flight check |\n"
    )
    assert find_referenced_filenames(content) == []


def test_corrective_message_names_siblings_under_parent():
    assert "sibling" in ORPHAN_FILE_MESSAGE_TEMPLATE
    assert "sibling" in ORPHAN_FILE_ADDITIONAL_CONTEXT


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


def test_unrelated_edit_over_preexisting_orphan_row_is_allowed(tmp_path: Path):
    claude_md_path = _isolated_claude_md_path(tmp_path)
    (claude_md_path.parent / "kept.py").write_text("x = 1\n", encoding="utf-8")
    claude_md_path.write_text(
        "# example\n\n"
        "A prose paragraph with a typoo to fix.\n\n"
        "## Local files\n\n"
        "| File | Note |\n"
        "|---|---|\n"
        "| `kept.py` | row |\n"
        "| `already_orphan.py` | pre-existing orphan |\n",
        encoding="utf-8",
    )
    result = _run_hook(
        "Edit",
        {
            "file_path": str(claude_md_path),
            "old_string": "A prose paragraph with a typoo to fix.",
            "new_string": "A prose paragraph with a typo fixed.",
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_multiedit_unrelated_change_over_preexisting_orphan_is_allowed(tmp_path: Path):
    claude_md_path = _isolated_claude_md_path(tmp_path)
    (claude_md_path.parent / "kept.py").write_text("x = 1\n", encoding="utf-8")
    claude_md_path.write_text(
        "# example\n\n"
        "First prose paragraph.\n\n"
        "## Local files\n\n"
        "| File | Note |\n"
        "|---|---|\n"
        "| `kept.py` | row |\n"
        "| `already_orphan.py` | pre-existing orphan |\n",
        encoding="utf-8",
    )
    result = _run_hook(
        "MultiEdit",
        {
            "file_path": str(claude_md_path),
            "edits": [
                {"old_string": "First prose paragraph.", "new_string": "Revised prose paragraph."},
            ],
        },
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_fenced_example_table_row_is_skipped(tmp_path: Path):
    claude_md_path = _isolated_claude_md_path(tmp_path)
    content = (
        "# example\n\n"
        "An example table you might write:\n\n"
        "```\n"
        "| File | Note |\n"
        "|---|---|\n"
        "| `ghostfile.py` | example row |\n"
        "```\n"
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


def test_fenced_table_row_does_not_exempt_a_later_real_row():
    content = (
        "# example\n\n"
        "```\n"
        "| File | Note |\n"
        "|---|---|\n"
        "| `ghostfile.py` | fenced example |\n"
        "```\n\n"
        "## Local files\n\n"
        "| File | Note |\n"
        "|---|---|\n"
        "| `reviewer_specs.py` | real row |\n"
    )
    assert find_referenced_filenames(content) == ["reviewer_specs.py"]


def test_tilde_fenced_example_table_row_is_skipped():
    content = (
        "# example\n\n"
        "~~~\n"
        "| File | Note |\n"
        "|---|---|\n"
        "| `ghostfile.py` | example row |\n"
        "~~~\n"
    )
    assert find_referenced_filenames(content) == []


def test_file_present_only_past_the_scan_cap_is_not_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(blocker_module, "MAX_SUBTREE_FILES_SCANNED", 5)
    package_directory = tmp_path / "package_directory"
    package_directory.mkdir()
    filler_directory = tmp_path / "filler"
    filler_directory.mkdir()
    for each_index in range(50):
        (filler_directory / f"filler_{each_index}.py").write_text("x = 1\n", encoding="utf-8")
    (package_directory / "real_target.py").write_text("x = 1\n", encoding="utf-8")
    claude_md_path = package_directory / "CLAUDE.md"
    content = (
        "# example\n\n"
        "| File | Note |\n"
        "|---|---|\n"
        "| `real_target.py` | a file that genuinely exists |\n"
    )
    first_missing = find_missing_filenames(content, claude_md_path.parent)
    second_missing = find_missing_filenames(content, claude_md_path.parent)
    assert first_missing == []
    assert second_missing == []


def test_oserror_during_subtree_walk_fails_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    def _raise_oserror(self, pattern):
        raise OSError("simulated unreadable directory")

    monkeypatch.setattr(Path, "rglob", _raise_oserror)
    claude_md_path = tmp_path / "CLAUDE.md"
    content = (
        "# example\n\n"
        "| File | Note |\n"
        "|---|---|\n"
        "| `reviewer_specs.py` | absent |\n"
    )
    missing_filenames = find_missing_filenames(content, claude_md_path.parent)
    assert missing_filenames == []


def test_blocker_module_has_no_collection_parameter_naming_violations():
    blocker_source = Path(HOOK_SCRIPT_PATH).read_text(encoding="utf-8")
    assert check_collection_prefix(blocker_source, HOOK_SCRIPT_PATH) == []


def test_test_module_has_no_unused_pytest_fixture_parameters():
    test_file_path = str(Path(__file__).resolve())
    test_source = Path(test_file_path).read_text(encoding="utf-8")
    assert check_unused_known_pytest_fixture_parameters(test_source, test_file_path) == []
