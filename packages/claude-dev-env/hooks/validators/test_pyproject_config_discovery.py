"""Tests for the shared pyproject config-discovery walk-up primitive.

The primitive walks up from a starting path and returns the first pyproject.toml
whose ``[tool.<name>]`` table exists, so each tool matches only a config that
actually configures it — a mypy-only pyproject is no ruff config.
"""

from pathlib import Path

from hooks_constants.pyproject_config_discovery_constants import (
    MYPY_TOOL_TABLE_NAME,
    RUFF_TOOL_TABLE_NAME,
)

from .pyproject_config_discovery import (
    ancestor_directories,
    find_pyproject_configuring_tool,
)


def test_ancestor_directories_lists_directory_then_parents_nearest_first(
    tmp_path: Path,
) -> None:
    nested_directory = tmp_path / "outer" / "inner"
    nested_directory.mkdir(parents=True)
    nested_file = nested_directory / "module.py"
    nested_file.write_text("sample_number: int = 1\n", encoding="utf-8")

    walked = ancestor_directories(nested_file)

    assert walked[0] == nested_directory.resolve()
    assert walked[1] == (tmp_path / "outer").resolve()


def test_find_pyproject_configuring_tool_returns_table_owning_pyproject(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    nested_directory = project_root / "src" / "deep"
    nested_directory.mkdir(parents=True)
    owning_pyproject = project_root / "pyproject.toml"
    owning_pyproject.write_text("[tool.ruff.lint]\nselect = ['B']\n", encoding="utf-8")
    target_file = nested_directory / "module.py"

    found = find_pyproject_configuring_tool(target_file, RUFF_TOOL_TABLE_NAME)

    assert found == owning_pyproject


def test_find_pyproject_configuring_tool_skips_pyproject_without_the_table(
    tmp_path: Path,
) -> None:
    outer_root = tmp_path / "outer"
    inner_root = outer_root / "inner"
    inner_root.mkdir(parents=True)
    outer_pyproject = outer_root / "pyproject.toml"
    outer_pyproject.write_text("[tool.mypy]\nignore_missing_imports = true\n", encoding="utf-8")
    (inner_root / "pyproject.toml").write_text("[project]\nname = 'inner'\n", encoding="utf-8")
    target_file = inner_root / "module.py"

    found = find_pyproject_configuring_tool(target_file, MYPY_TOOL_TABLE_NAME)

    assert found == outer_pyproject


def test_find_pyproject_configuring_tool_is_table_specific(tmp_path: Path) -> None:
    project_root = tmp_path / "mypy_only"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text(
        "[tool.mypy]\nignore_missing_imports = true\n", encoding="utf-8"
    )
    target_file = project_root / "module.py"

    assert find_pyproject_configuring_tool(target_file, MYPY_TOOL_TABLE_NAME) is not None
    assert find_pyproject_configuring_tool(target_file, RUFF_TOOL_TABLE_NAME) is None


def test_find_pyproject_configuring_tool_returns_none_when_no_match(tmp_path: Path) -> None:
    isolated_directory = tmp_path / "isolated"
    isolated_directory.mkdir()
    target_file = isolated_directory / "module.py"

    assert find_pyproject_configuring_tool(target_file, RUFF_TOOL_TABLE_NAME) is None


def test_find_pyproject_configuring_tool_treats_malformed_toml_as_no_match(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "broken"
    project_root.mkdir()
    (project_root / "pyproject.toml").write_text("[tool.ruff\nbroken = true\n", encoding="utf-8")
    target_file = project_root / "module.py"

    assert find_pyproject_configuring_tool(target_file, RUFF_TOOL_TABLE_NAME) is None
