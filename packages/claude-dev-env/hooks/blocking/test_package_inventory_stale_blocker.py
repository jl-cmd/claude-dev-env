"""Tests for package_inventory_stale_blocker hook."""

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from package_inventory_stale_blocker import (
    find_stale_inventory,
    inventory_named_basenames,
    is_inventoried_production_file,
)

from hooks_constants.package_inventory_stale_blocker_constants import (
    STALE_INVENTORY_SYSTEM_MESSAGE,
)

HOOK_SCRIPT_PATH = os.path.join(os.path.dirname(__file__), "package_inventory_stale_blocker.py")

README_LISTING_TWO_FILES = (
    "# Pipeline\n\n"
    "| Path | Role |\n"
    "|---|---|\n"
    "| `pipeline/dialer_compose.py` | Composes a dialer strip. |\n"
    "| `compose_dialer_cli.py` | CLI for the dialer strip. |\n"
)

CLAUDE_MD_BULLET_LIST = (
    "# package\n\n"
    "## Key files\n\n"
    "- `compose_dialer_cli.py` — composes one dialer strip.\n"
    "- `compose_aod_cli.py` — composes the AOD image.\n"
)

README_LISTING_ONE_FILE = "# package\n\nSome prose mentioning `single_module.py` once.\n"

README_LISTING_ONLY_GLOB_TOKENS = (
    "# package\n\n"
    "This directory holds files matching `*.py` and `*.mjs`.\n"
)

README_LISTING_ONLY_FENCED_FILENAMES = (
    "# package\n\n"
    "Example inventory table:\n\n"
    "```\n"
    "| Path | Role |\n"
    "|---|---|\n"
    "| `example_alpha.py` | Sample row. |\n"
    "| `example_beta.py` | Sample row. |\n"
    "```\n"
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


def _package_directory_with_readme(tmp_path: Path, readme_content: str) -> Path:
    """Return a fresh package directory holding a README.md with the given content."""
    package_directory = tmp_path / "package_directory"
    package_directory.mkdir()
    (package_directory / "README.md").write_text(readme_content, encoding="utf-8")
    return package_directory


def test_inventory_named_basenames_strips_path_to_basename():
    named_basenames = inventory_named_basenames(README_LISTING_TWO_FILES)
    assert named_basenames == {"dialer_compose.py", "compose_dialer_cli.py"}


def test_inventory_named_basenames_reads_bullet_list():
    named_basenames = inventory_named_basenames(CLAUDE_MD_BULLET_LIST)
    assert named_basenames == {"compose_dialer_cli.py", "compose_aod_cli.py"}


def test_inventory_named_basenames_rejects_glob_tokens():
    named_basenames = inventory_named_basenames(README_LISTING_ONLY_GLOB_TOKENS)
    assert named_basenames == set()


def test_inventory_named_basenames_skips_fenced_code_block():
    named_basenames = inventory_named_basenames(README_LISTING_ONLY_FENCED_FILENAMES)
    assert named_basenames == set()


def test_blocks_new_production_file_absent_from_readme(tmp_path: Path):
    package_directory = _package_directory_with_readme(tmp_path, README_LISTING_TWO_FILES)
    new_file_path = package_directory / "check_dialer_seam_cli.py"
    result = _run_hook(
        "Write",
        {"file_path": str(new_file_path), "content": "x = 1\n"},
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "check_dialer_seam_cli.py" in payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert payload["systemMessage"] == STALE_INVENTORY_SYSTEM_MESSAGE


def test_blocks_new_file_absent_from_claude_md_bullet_list(tmp_path: Path):
    package_directory = tmp_path / "package_directory"
    package_directory.mkdir()
    (package_directory / "CLAUDE.md").write_text(CLAUDE_MD_BULLET_LIST, encoding="utf-8")
    new_file_path = package_directory / "build_dialer_aod_roster_cli.py"
    result = _run_hook(
        "Write",
        {"file_path": str(new_file_path), "content": "x = 1\n"},
    )
    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_allows_new_file_already_named_in_readme(tmp_path: Path):
    package_directory = _package_directory_with_readme(tmp_path, README_LISTING_TWO_FILES)
    new_file_path = package_directory / "compose_dialer_cli.py"
    result = _run_hook(
        "Write",
        {"file_path": str(new_file_path), "content": "x = 1\n"},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_allows_new_file_named_by_path_form_in_readme(tmp_path: Path):
    package_directory = _package_directory_with_readme(tmp_path, README_LISTING_TWO_FILES)
    pipeline_directory = package_directory / "pipeline"
    pipeline_directory.mkdir()
    new_file_path = package_directory / "dialer_compose.py"
    result = _run_hook(
        "Write",
        {"file_path": str(new_file_path), "content": "x = 1\n"},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_allows_directory_with_no_inventory(tmp_path: Path):
    package_directory = tmp_path / "package_directory"
    package_directory.mkdir()
    new_file_path = package_directory / "lonely_module.py"
    result = _run_hook(
        "Write",
        {"file_path": str(new_file_path), "content": "x = 1\n"},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_allows_directory_whose_readme_names_too_few_files(tmp_path: Path):
    package_directory = _package_directory_with_readme(tmp_path, README_LISTING_ONE_FILE)
    new_file_path = package_directory / "another_module.py"
    result = _run_hook(
        "Write",
        {"file_path": str(new_file_path), "content": "x = 1\n"},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_allows_new_file_when_inventory_holds_only_glob_tokens(tmp_path: Path):
    package_directory = _package_directory_with_readme(
        tmp_path, README_LISTING_ONLY_GLOB_TOKENS
    )
    new_file_path = package_directory / "new_sibling_module.py"
    result = _run_hook(
        "Write",
        {"file_path": str(new_file_path), "content": "x = 1\n"},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_allows_new_file_when_inventory_filenames_live_in_code_fence(tmp_path: Path):
    package_directory = _package_directory_with_readme(
        tmp_path, README_LISTING_ONLY_FENCED_FILENAMES
    )
    new_file_path = package_directory / "new_sibling_module.py"
    result = _run_hook(
        "Write",
        {"file_path": str(new_file_path), "content": "x = 1\n"},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_allows_test_file_absent_from_inventory(tmp_path: Path):
    package_directory = _package_directory_with_readme(tmp_path, README_LISTING_TWO_FILES)
    new_file_path = package_directory / "test_check_dialer_seam_cli.py"
    result = _run_hook(
        "Write",
        {"file_path": str(new_file_path), "content": "x = 1\n"},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_allows_init_file_absent_from_inventory(tmp_path: Path):
    package_directory = _package_directory_with_readme(tmp_path, README_LISTING_TWO_FILES)
    new_file_path = package_directory / "__init__.py"
    result = _run_hook(
        "Write",
        {"file_path": str(new_file_path), "content": "x = 1\n"},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_allows_non_code_file_absent_from_inventory(tmp_path: Path):
    package_directory = _package_directory_with_readme(tmp_path, README_LISTING_TWO_FILES)
    new_file_path = package_directory / "notes.txt"
    result = _run_hook(
        "Write",
        {"file_path": str(new_file_path), "content": "x = 1\n"},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_allows_edit_of_existing_file(tmp_path: Path):
    package_directory = _package_directory_with_readme(tmp_path, README_LISTING_TWO_FILES)
    existing_file_path = package_directory / "seam_continuity.py"
    existing_file_path.write_text("x = 1\n", encoding="utf-8")
    result = _run_hook(
        "Write",
        {"file_path": str(existing_file_path), "content": "x = 2\n"},
    )
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_is_inventoried_production_file_rejects_config_directory(tmp_path: Path):
    config_directory = tmp_path / "config"
    config_directory.mkdir()
    config_file_path = config_directory / "constants.py"
    assert is_inventoried_production_file(str(config_file_path)) is False


def test_is_inventoried_production_file_accepts_production_file(tmp_path: Path):
    production_file_path = tmp_path / "dialer_compose.py"
    assert is_inventoried_production_file(str(production_file_path)) is True


def test_find_stale_inventory_returns_survey_for_omission(tmp_path: Path):
    package_directory = _package_directory_with_readme(tmp_path, README_LISTING_TWO_FILES)
    new_file_path = package_directory / "seam_continuity.py"
    survey = find_stale_inventory(str(new_file_path))
    assert survey is not None
    assert survey.present_inventory_names == ["README.md"]
