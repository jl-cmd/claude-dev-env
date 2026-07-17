"""Ruff integration for fast Python linting."""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .pyproject_config_discovery import find_pyproject_configuring_tool

_hooks_directory = str(Path(__file__).resolve().parent.parent)

try:
    from hooks_constants.mypy_integration_constants import PYTHON_SOURCE_SUFFIX
    from hooks_constants.pyproject_config_discovery_constants import RUFF_TOOL_TABLE_NAME
except ModuleNotFoundError:
    if _hooks_directory not in sys.path:
        sys.path.insert(0, _hooks_directory)
    from hooks_constants.mypy_integration_constants import PYTHON_SOURCE_SUFFIX
    from hooks_constants.pyproject_config_discovery_constants import RUFF_TOOL_TABLE_NAME


@dataclass
class RuffResult:
    passed: bool
    output: str
    fixed_count: int


def check_ruff_available() -> bool:
    """Check if ruff is installed."""
    try:
        result = subprocess.run(
            ["ruff", "--version"],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def find_pyproject_with_ruff_config(starting_file: Path) -> Path | None:
    """Walk up from a starting file to a pyproject.toml that configures ruff.

    The walk skips a pyproject.toml with no [tool.ruff] table, so a mypy-only
    config is not handed to ``ruff --config``, which errors on the missing table.

    Args:
        starting_file: The file (or directory) the walk begins from.

    Returns:
        The first ``pyproject.toml`` Path declaring a ``[tool.ruff]`` table, or
        ``None`` when none exists up to the filesystem root.
    """
    return find_pyproject_configuring_tool(starting_file, RUFF_TOOL_TABLE_NAME)


def _ruff_config_argument(config_source_path: Path | None) -> list[str]:
    """Return the ``--config`` argument resolved from the original path, or empty.

    ::

        config_source_path resolves .../hooks/pyproject.toml
            -> ["--config", ".../hooks/pyproject.toml"]
        config_source_path given, no [tool.ruff] up-tree -> [] (native discovery)
        config_source_path None -> [] (native discovery)

    Args:
        config_source_path: The original target path the staged copy stands in
            for, or ``None`` for a native run.

    Returns:
        The ``--config`` argument vector, empty when no ruff config resolves.
    """
    if config_source_path is None:
        return []
    resolved_pyproject = find_pyproject_with_ruff_config(config_source_path)
    if resolved_pyproject is None:
        return []
    return ["--config", str(resolved_pyproject)]


def run_ruff_check(
    all_files: list[Path], config_source_path: Path | None = None
) -> RuffResult:
    """Run ruff check on *all_files*, resolving config from *config_source_path*.

    A given ``config_source_path`` adds ``--config`` from the original target."""
    if not all_files:
        return RuffResult(passed=True, output="No files to check", fixed_count=0)

    if not check_ruff_available():
        return RuffResult(passed=True, output="Ruff not installed - skipping", fixed_count=0)

    py_files = [
        str(each_file) for each_file in all_files if each_file.suffix == PYTHON_SOURCE_SUFFIX
    ]
    if not py_files:
        return RuffResult(passed=True, output="No Python files", fixed_count=0)
    config_argument = _ruff_config_argument(config_source_path)
    concise_output_arguments = ["--output-format", "concise"]
    result = subprocess.run(
        ["ruff", "check", *config_argument, *concise_output_arguments] + py_files,
        check=False,
        capture_output=True,
        text=True,
    )
    return RuffResult(
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "No issues found",
        fixed_count=0,
    )


def run_ruff_fix(files: list[Path]) -> RuffResult:
    """Run ruff with --fix to auto-fix violations."""
    if not check_ruff_available():
        return RuffResult(passed=True, output="Ruff not installed", fixed_count=0)

    py_files = [str(f) for f in files if f.suffix == ".py"]
    if not py_files:
        return RuffResult(passed=True, output="No Python files", fixed_count=0)

    result = subprocess.run(
        ["ruff", "check", "--fix"] + py_files,
        check=False,
        capture_output=True,
        text=True,
    )

    fixed_count = 0
    for line in result.stdout.split("\n"):
        if "Fixed" in line:
            try:
                fixed_count = int(line.split()[1])
            except (IndexError, ValueError):
                pass

    return RuffResult(
        passed=result.returncode == 0,
        output=result.stdout or "No fixes applied",
        fixed_count=fixed_count,
    )
