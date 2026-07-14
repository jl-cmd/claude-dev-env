"""Tests for the package-inventory detection parts module."""

from pathlib import Path

from package_inventory_stale_blocker_parts.inventory_detection import (
    find_stale_inventory,
    inventory_named_basenames,
    is_inventoried_production_file,
    survey_directory_inventories,
)

README_TWO_FILES = (
    "# Pipeline\n\n"
    "| Path | Role |\n"
    "|---|---|\n"
    "| `dialer_compose.py` | Composes a dialer strip. |\n"
    "| `compose_dialer_cli.py` | CLI for the dialer strip. |\n"
)


def _package_with_readme(tmp_path: Path, readme_content: str) -> Path:
    package_directory = tmp_path / "package_directory"
    package_directory.mkdir()
    (package_directory / "README.md").write_text(readme_content, encoding="utf-8")
    return package_directory


def test_inventory_named_basenames_reads_table_cells() -> None:
    named_basenames = inventory_named_basenames(README_TWO_FILES)
    assert named_basenames == {"dialer_compose.py", "compose_dialer_cli.py"}


def test_survey_directory_inventories_unions_named_files(tmp_path: Path) -> None:
    package_directory = _package_with_readme(tmp_path, README_TWO_FILES)
    survey = survey_directory_inventories(package_directory)
    assert survey.present_inventory_names == ["README.md"]
    assert survey.named_basenames == {"dialer_compose.py", "compose_dialer_cli.py"}


def test_is_inventoried_production_file_accepts_python_module(tmp_path: Path) -> None:
    assert is_inventoried_production_file(str(tmp_path / "dialer_compose.py")) is True


def test_is_inventoried_production_file_rejects_test_file(tmp_path: Path) -> None:
    assert is_inventoried_production_file(str(tmp_path / "test_dialer.py")) is False


def test_find_stale_inventory_reports_omission(tmp_path: Path) -> None:
    package_directory = _package_with_readme(tmp_path, README_TWO_FILES)
    for each_basename in ("dialer_compose.py", "compose_dialer_cli.py"):
        (package_directory / each_basename).write_text("x = 1\n", encoding="utf-8")
    survey = find_stale_inventory(str(package_directory / "seam_continuity.py"))
    assert survey is not None
    assert survey.named_basenames == {"dialer_compose.py", "compose_dialer_cli.py"}


def test_find_stale_inventory_allows_named_file(tmp_path: Path) -> None:
    package_directory = _package_with_readme(tmp_path, README_TWO_FILES)
    for each_basename in ("dialer_compose.py", "compose_dialer_cli.py"):
        (package_directory / each_basename).write_text("x = 1\n", encoding="utf-8")
    assert find_stale_inventory(str(package_directory / "compose_dialer_cli.py")) is None
