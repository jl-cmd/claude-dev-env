"""Mypy integration for static type checking."""

import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MypyResult:
    passed: bool
    output: str
    error_count: int


def check_mypy_available() -> bool:
    """Check if mypy is installed."""
    try:
        result = subprocess.run(
            ["mypy", "--version"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def _pyproject_contains_tool_mypy(pyproject_path: Path) -> bool:
    try:
        with pyproject_path.open("rb") as readable_handle:
            parsed_toml = tomllib.load(readable_handle)
    except (OSError, tomllib.TOMLDecodeError):
        return False
    tool_table = parsed_toml.get("tool", {})
    return isinstance(tool_table, dict) and "mypy" in tool_table


def find_pyproject_with_mypy_config(starting_file: Path) -> Path | None:
    """Walk up from a starting file to locate a pyproject.toml that configures mypy.

    The walk skips pyproject.toml files that do not declare a [tool.mypy]
    table so that an unrelated package config (for example, a project root
    pyproject.toml) does not shadow a hook-tree pyproject.toml that
    actually configures the type checker.

    Args:
        starting_file: The file (or directory) the walk begins from. The walk
            climbs through every parent directory in order.

    Returns:
        The first ``pyproject.toml`` Path that declares a ``[tool.mypy]``
        table, or ``None`` when no such file exists between ``starting_file``
        and the filesystem root.
    """
    pyproject_filename_for_lookup = "pyproject.toml"
    resolved_starting_file = starting_file.resolve()
    current_directory = resolved_starting_file.parent if resolved_starting_file.is_file() else resolved_starting_file
    for each_candidate_directory in [current_directory, *current_directory.parents]:
        candidate_pyproject = each_candidate_directory / pyproject_filename_for_lookup
        if candidate_pyproject.is_file() and _pyproject_contains_tool_mypy(candidate_pyproject):
            return candidate_pyproject
    return None


def run_mypy_check(files: list[Path]) -> MypyResult:
    """Run mypy on files."""
    if not files:
        return MypyResult(passed=True, output="No files to check", error_count=0)

    if not check_mypy_available():
        return MypyResult(passed=True, output="Mypy not installed - skipping", error_count=0)

    py_files = [str(f) for f in files if f.suffix == ".py"]
    if not py_files:
        return MypyResult(passed=True, output="No Python files", error_count=0)

    config_argument: list[str] = []
    for each_py_file in py_files:
        discovered_pyproject = find_pyproject_with_mypy_config(Path(each_py_file))
        if discovered_pyproject is not None:
            config_argument = ["--config-file", str(discovered_pyproject)]
            break

    result = subprocess.run(
        ["mypy", *config_argument, "--ignore-missing-imports", "--no-error-summary"]
        + py_files,
        capture_output=True,
        text=True,
    )

    error_count = result.stdout.count(": error:")

    return MypyResult(
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "No type errors",
        error_count=error_count,
    )
