"""Mypy integration for static type checking."""

import subprocess
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


def run_mypy_check(files: list[Path]) -> MypyResult:
    """Run mypy on files."""
    if not files:
        return MypyResult(passed=True, output="No files to check", error_count=0)

    if not check_mypy_available():
        return MypyResult(passed=True, output="Mypy not installed - skipping", error_count=0)

    py_files = [str(f) for f in files if f.suffix == ".py"]
    if not py_files:
        return MypyResult(passed=True, output="No Python files", error_count=0)

    result = subprocess.run(
        ["mypy", "--ignore-missing-imports", "--no-error-summary"] + py_files,
        capture_output=True,
        text=True,
    )

    error_count = result.stdout.count(": error:")

    return MypyResult(
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "No type errors",
        error_count=error_count,
    )
