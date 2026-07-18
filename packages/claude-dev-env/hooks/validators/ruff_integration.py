"""Ruff integration for fast Python linting."""

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_validators_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)

try:
    from pyproject_config_discovery import find_pyproject_configuring_tool
except ModuleNotFoundError:
    if _validators_directory not in sys.path:
        sys.path.insert(0, _validators_directory)
    from pyproject_config_discovery import find_pyproject_configuring_tool

try:
    from hooks_constants.mypy_integration_constants import PYTHON_SOURCE_SUFFIX
    from hooks_constants.pyproject_config_discovery_constants import RUFF_TOOL_TABLE_NAME
    from hooks_constants.ruff_integration_constants import (
        FORCE_COLOR_ENVIRONMENT_VARIABLE_NAME,
        NO_COLOR_ENABLED_VALUE,
        NO_COLOR_ENVIRONMENT_VARIABLE_NAME,
    )
except ModuleNotFoundError:
    if _hooks_directory not in sys.path:
        sys.path.insert(0, _hooks_directory)
    from hooks_constants.mypy_integration_constants import PYTHON_SOURCE_SUFFIX
    from hooks_constants.pyproject_config_discovery_constants import RUFF_TOOL_TABLE_NAME
    from hooks_constants.ruff_integration_constants import (
        FORCE_COLOR_ENVIRONMENT_VARIABLE_NAME,
        NO_COLOR_ENABLED_VALUE,
        NO_COLOR_ENVIRONMENT_VARIABLE_NAME,
    )


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


def _ruff_subprocess_environment() -> dict[str, str]:
    """Return an environment that forces plain, non-ANSI ruff diagnostics.

    The PreToolUse gate parses ``path:line:col:`` prefixes. ANSI color codes
    wrap those fields when FORCE_COLOR is set, so line numbers no longer parse
    and baseline scoping fail-closes every ruff finding as new.
    """
    ruff_environment = os.environ.copy()
    ruff_environment[NO_COLOR_ENVIRONMENT_VARIABLE_NAME] = NO_COLOR_ENABLED_VALUE
    ruff_environment.pop(FORCE_COLOR_ENVIRONMENT_VARIABLE_NAME, None)
    return ruff_environment


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


def _config_relative_stdin_filename(target_path: Path, config_directory: Path) -> str:
    """Return *target_path* expressed relative to the ruff config directory.

    ::

        target .../hooks/validators/run_all_validators.py, config dir .../hooks
            -> "validators/run_all_validators.py"  (path-scoped ignore matches)
        target off-tree from the config dir -> the bare basename

    Ruff matches ``[tool.ruff.lint.per-file-ignores]`` keys against the path a
    file presents relative to ruff's working directory, so a path-scoped key
    matches only when the staged copy is graded under that same relative name.

    Args:
        target_path: The real target path the staged copy stands in for.
        config_directory: The directory holding the resolved ruff pyproject.

    Returns:
        The config-relative POSIX path when the target sits under the config
        directory, else the target's basename.
    """
    try:
        return target_path.relative_to(config_directory).as_posix()
    except ValueError:
        pass
    resolved_target = target_path.resolve()
    resolved_config_directory = config_directory.resolve()
    try:
        return resolved_target.relative_to(resolved_config_directory).as_posix()
    except ValueError:
        return resolved_target.name


def _read_staged_content(staged_file: Path) -> str | None:
    """Return the staged copy's text content, or None when it cannot be read."""
    try:
        return staged_file.read_text(encoding="utf-8")
    except OSError:
        return None


def _single_staged_python_file(all_files: list[Path]) -> Path | None:
    """Return the sole staged Python file, or None unless there is exactly one."""
    all_python_files = [
        each_file for each_file in all_files if each_file.suffix == PYTHON_SOURCE_SUFFIX
    ]
    if len(all_python_files) != 1:
        return None
    return all_python_files[0]


def _staged_ruff_command(resolved_pyproject: Path, stdin_filename: str) -> list[str]:
    """Return the ruff argv that grades stdin under a config-relative name."""
    concise_output_arguments = ["--output-format", "concise"]
    return [
        "ruff",
        "check",
        "--config",
        str(resolved_pyproject),
        *concise_output_arguments,
        "--stdin-filename",
        stdin_filename,
        "-",
    ]


def _staged_ruff_result(
    resolved_pyproject: Path, stdin_filename: str, staged_content: str
) -> RuffResult:
    """Pipe *staged_content* to ruff from the config directory and wrap the result."""
    result = subprocess.run(
        _staged_ruff_command(resolved_pyproject, stdin_filename),
        check=False,
        capture_output=True,
        text=True,
        input=staged_content,
        cwd=str(resolved_pyproject.parent),
        env=_ruff_subprocess_environment(),
    )
    return RuffResult(
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "No issues found",
        fixed_count=0,
    )


def _run_staged_ruff_check(
    all_files: list[Path], config_source_path: Path
) -> RuffResult | None:
    """Grade one staged file under the config resolved from its original path.

    The staged content is piped to ruff under ``--stdin-filename`` set to the
    original target's config-relative name, so ruff applies path-scoped
    per-file-ignores that never match the temporary copy's own location.
    Returns None when the staged shape does not apply: no resolvable ruff
    config, not exactly one Python file, or an unreadable staged copy.
    """
    resolved_pyproject = find_pyproject_with_ruff_config(config_source_path)
    if resolved_pyproject is None:
        return None
    staged_file = _single_staged_python_file(all_files)
    if staged_file is None:
        return None
    staged_content = _read_staged_content(staged_file)
    if staged_content is None:
        return None
    stdin_filename = _config_relative_stdin_filename(
        config_source_path, resolved_pyproject.parent
    )
    return _staged_ruff_result(resolved_pyproject, stdin_filename, staged_content)


def _run_native_ruff_check(
    all_python_files: list[str], config_source_path: Path | None
) -> RuffResult:
    """Run ruff over *all_python_files* directly, resolving ``--config`` from the path."""
    config_argument = _ruff_config_argument(config_source_path)
    concise_output_arguments = ["--output-format", "concise"]
    result = subprocess.run(
        ["ruff", "check", *config_argument, *concise_output_arguments] + all_python_files,
        check=False,
        capture_output=True,
        text=True,
        env=_ruff_subprocess_environment(),
    )
    return RuffResult(
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "No issues found",
        fixed_count=0,
    )


def run_ruff_check(
    all_files: list[Path], config_source_path: Path | None = None
) -> RuffResult:
    """Run ruff check on *all_files*, resolving config from *config_source_path*.

    A given ``config_source_path`` grades the single staged copy under the project
    config resolved from the original target, applying its path-scoped
    per-file-ignores. Without it, the files are checked natively."""
    if not all_files:
        return RuffResult(passed=True, output="No files to check", fixed_count=0)

    if not check_ruff_available():
        return RuffResult(passed=True, output="Ruff not installed - skipping", fixed_count=0)

    all_python_files = [
        str(each_file) for each_file in all_files if each_file.suffix == PYTHON_SOURCE_SUFFIX
    ]
    if not all_python_files:
        return RuffResult(passed=True, output="No Python files", fixed_count=0)
    if config_source_path is not None:
        staged_result = _run_staged_ruff_check(all_files, config_source_path)
        if staged_result is not None:
            return staged_result
    return _run_native_ruff_check(all_python_files, config_source_path)


def _parse_fixed_count(fix_output: str) -> int:
    """Return the count ruff reports on its ``Fixed N`` line, or 0 when absent."""
    for each_line in fix_output.split("\n"):
        if "Fixed" not in each_line:
            continue
        try:
            return int(each_line.split()[1])
        except (IndexError, ValueError):
            return 0
    return 0


def run_ruff_fix(all_files: list[Path]) -> RuffResult:
    """Run ruff with --fix to auto-fix violations."""
    if not check_ruff_available():
        return RuffResult(passed=True, output="Ruff not installed", fixed_count=0)
    py_files = [
        str(each_file) for each_file in all_files if each_file.suffix == PYTHON_SOURCE_SUFFIX
    ]
    if not py_files:
        return RuffResult(passed=True, output="No Python files", fixed_count=0)
    result = subprocess.run(
        ["ruff", "check", "--fix"] + py_files,
        check=False,
        capture_output=True,
        text=True,
        env=_ruff_subprocess_environment(),
    )
    return RuffResult(
        passed=result.returncode == 0,
        output=result.stdout or "No fixes applied",
        fixed_count=_parse_fixed_count(result.stdout),
    )
