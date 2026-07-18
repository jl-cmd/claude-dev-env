"""Ruff integration for fast Python linting."""

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_hooks_directory = str(Path(__file__).resolve().parent.parent)

try:
    from hooks_constants.ruff_integration_constants import (
        FORCE_COLOR_ENVIRONMENT_VARIABLE_NAME,
        NO_COLOR_ENABLED_VALUE,
        NO_COLOR_ENVIRONMENT_VARIABLE_NAME,
    )
except ModuleNotFoundError:
    if _hooks_directory not in sys.path:
        sys.path.insert(0, _hooks_directory)
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
    no_color_environment_variable_name = NO_COLOR_ENVIRONMENT_VARIABLE_NAME
    force_color_environment_variable_name = FORCE_COLOR_ENVIRONMENT_VARIABLE_NAME
    no_color_enabled_value = NO_COLOR_ENABLED_VALUE
    ruff_environment = os.environ.copy()
    ruff_environment[no_color_environment_variable_name] = no_color_enabled_value
    ruff_environment.pop(force_color_environment_variable_name, None)
    return ruff_environment


def run_ruff_check(files: list[Path]) -> RuffResult:
    """Run ruff check on files."""
    if not files:
        return RuffResult(passed=True, output="No files to check", fixed_count=0)

    if not check_ruff_available():
        return RuffResult(passed=True, output="Ruff not installed - skipping", fixed_count=0)

    py_files = [str(f) for f in files if f.suffix == ".py"]
    if not py_files:
        return RuffResult(passed=True, output="No Python files", fixed_count=0)

    concise_output_arguments = ["--output-format", "concise"]
    result = subprocess.run(
        ["ruff", "check", *concise_output_arguments] + py_files,
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
        env=_ruff_subprocess_environment(),
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
