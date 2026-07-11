"""Ruff integration for fast Python linting."""

import subprocess
from dataclasses import dataclass
from pathlib import Path


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
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def run_ruff_check(files: list[Path]) -> RuffResult:
    """Run ruff check on files."""
    if not files:
        return RuffResult(passed=True, output="No files to check", fixed_count=0)

    if not check_ruff_available():
        return RuffResult(passed=True, output="Ruff not installed - skipping", fixed_count=0)

    py_files = [str(f) for f in files if f.suffix == ".py"]
    if not py_files:
        return RuffResult(passed=True, output="No Python files", fixed_count=0)

    result = subprocess.run(
        ["ruff", "check"] + py_files,
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
