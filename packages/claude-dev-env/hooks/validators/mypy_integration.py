"""Mypy integration for static type checking."""

import contextlib
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

_validators_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)

try:
    from pyproject_config_discovery import (
        ancestor_directories,
        find_pyproject_configuring_tool,
    )
except ModuleNotFoundError:
    if _validators_directory not in sys.path:
        sys.path.insert(0, _validators_directory)
    from pyproject_config_discovery import (
        ancestor_directories,
        find_pyproject_configuring_tool,
    )

try:
    from hooks_constants.mypy_integration_constants import (
        GIT_DIRECTORY_NAME,
        PYPROJECT_FILENAME,
        PYTHON_SOURCE_SUFFIX,
    )
    from hooks_constants.pyproject_config_discovery_constants import MYPY_TOOL_TABLE_NAME
except ModuleNotFoundError:
    if _hooks_directory not in sys.path:
        sys.path.insert(0, _hooks_directory)
    from hooks_constants.mypy_integration_constants import (
        GIT_DIRECTORY_NAME,
        PYPROJECT_FILENAME,
        PYTHON_SOURCE_SUFFIX,
    )
    from hooks_constants.pyproject_config_discovery_constants import MYPY_TOOL_TABLE_NAME


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
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


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
    return find_pyproject_configuring_tool(starting_file, MYPY_TOOL_TABLE_NAME)


def find_module_resolution_root(starting_file: Path) -> Path | None:
    """Return the nearest ancestor directory that roots a project, else None.

    A project root is the first ancestor holding a ``.git`` entry or a
    ``pyproject.toml``. Mypy resolves a first-party import against its working
    directory, so anchoring there binds ``config.*`` to the target file's own
    project and keeps a foreign ``config`` in the caller's directory out of scope.

    ::

        target_repo/.git + target_repo/tools/x.py -> target_repo
        /tmp/detached/x.py (no marker up-tree)      -> None

    Args:
        starting_file: The file (or directory) the walk begins from.

    Returns:
        The nearest ancestor Path that holds ``.git`` or ``pyproject.toml``,
        or ``None`` when no such ancestor exists.
    """
    git_entry_name = GIT_DIRECTORY_NAME
    pyproject_filename = PYPROJECT_FILENAME
    for each_candidate_directory in ancestor_directories(starting_file):
        has_git_entry = (each_candidate_directory / git_entry_name).exists()
        has_pyproject = (each_candidate_directory / pyproject_filename).is_file()
        if has_git_entry or has_pyproject:
            return each_candidate_directory
    return None


def _first_module_resolution_root(all_py_files: list[str]) -> Path | None:
    """Return the project root of the first rooted target file, or None."""
    for each_py_file in all_py_files:
        resolution_root = find_module_resolution_root(Path(each_py_file))
        if resolution_root is not None:
            return resolution_root
    return None


@contextlib.contextmanager
def mypy_working_directory(all_py_files: list[str]) -> Iterator[str]:
    """Yield the working directory mypy resolves first-party imports from.

    ::

        target_repo/tools/serialize_tool.py -> yields target_repo
        /tmp/detached/serialize_tool.py       -> yields a fresh empty temp dir

    A rooted file yields its project root so ``config.constants`` binds to the
    target repo's own package; a detached file yields an isolated directory so
    no foreign top-level package leaks in.

    Args:
        all_py_files: Absolute or relative paths of the Python files under check.

    Yields:
        A directory path string mypy should use as its working directory.
    """
    resolution_root = _first_module_resolution_root(all_py_files)
    if resolution_root is not None:
        yield str(resolution_root)
        return
    with tempfile.TemporaryDirectory() as isolated_directory:
        yield isolated_directory


def _native_mypy_config_argument(all_py_files: list[str]) -> list[str]:
    """Return the ``--config-file`` argument for the first file with a mypy config."""
    for each_py_file in all_py_files:
        discovered_pyproject = find_pyproject_with_mypy_config(Path(each_py_file))
        if discovered_pyproject is not None:
            return ["--config-file", str(discovered_pyproject)]
    return []


def _mypy_config_argument(
    all_py_files: list[str], config_source_path: Path | None
) -> list[str]:
    """Return the ``--config-file`` argument, resolved from the original path when given.

    ::

        config_source_path resolves .../hooks/pyproject.toml
            -> ["--config-file", ".../hooks/pyproject.toml"]
        config_source_path given, no [tool.mypy] up-tree -> [] (native discovery)
        config_source_path None -> native per-file discovery over all_py_files

    Args:
        all_py_files: The resolved paths mypy will check.
        config_source_path: The original target path the staged copy stands in
            for, or ``None`` for a native multi-file run.

    Returns:
        The ``--config-file`` argument vector, empty when no config resolves.
    """
    if config_source_path is None:
        return _native_mypy_config_argument(all_py_files)
    resolved_pyproject = find_pyproject_with_mypy_config(config_source_path)
    if resolved_pyproject is not None:
        return ["--config-file", str(resolved_pyproject)]
    return _native_mypy_config_argument(all_py_files)


def _run_mypy_subprocess(
    all_py_files: list[str], config_source_path: Path | None
) -> subprocess.CompletedProcess[str]:
    """Run mypy over *all_py_files* from each file's own project root."""
    config_argument = _mypy_config_argument(all_py_files, config_source_path)
    with mypy_working_directory(all_py_files) as working_directory:
        return subprocess.run(
            ["mypy", *config_argument, "--ignore-missing-imports", "--no-error-summary"]
            + all_py_files,
            check=False,
            capture_output=True,
            text=True,
            cwd=working_directory,
        )


def run_mypy_check(
    all_files: list[Path], config_source_path: Path | None = None
) -> MypyResult:
    """Run mypy on files, resolving config from *config_source_path* when given.

    A given ``config_source_path`` walks ``--config-file`` up from the original
    target rather than the staged copy's own ancestors.
    """
    if not all_files:
        return MypyResult(passed=True, output="No files to check", error_count=0)

    if not check_mypy_available():
        return MypyResult(passed=True, output="Mypy not installed - skipping", error_count=0)

    all_py_files = [
        str(each_file.resolve())
        for each_file in all_files
        if each_file.suffix == PYTHON_SOURCE_SUFFIX
    ]
    if not all_py_files:
        return MypyResult(passed=True, output="No Python files", error_count=0)

    completed_process = _run_mypy_subprocess(all_py_files, config_source_path)
    error_count = completed_process.stdout.count(": error:")

    return MypyResult(
        passed=completed_process.returncode == 0,
        output=completed_process.stdout or completed_process.stderr or "No type errors",
        error_count=error_count,
    )
