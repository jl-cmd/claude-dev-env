"""Run all pre-push validators and report results.

This script orchestrates all automated validators and produces a unified report.
Exit code 0 = all checks pass, 1 = violations found.
"""

import argparse
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from health_check import get_validator_version
from mypy_integration import check_mypy_available, run_mypy_check
from output_formatter import OutputFormatter, OutputMode, ValidatorResultDict
from ruff_integration import check_ruff_available, run_ruff_check


VALIDATORS_DIR = Path(__file__).parent


@dataclass(frozen=True)
class TimingMetrics:
    """Timing information for validator runs (immutable)."""

    total_seconds: float
    validator_times: Dict[str, float]


def create_timing_metrics(validator_times: Dict[str, float]) -> TimingMetrics:
    """Create a TimingMetrics instance from validator times.

    Args:
        validator_times: Dict mapping validator names to elapsed seconds

    Returns:
        TimingMetrics with calculated total
    """
    total = sum(validator_times.values())
    return TimingMetrics(
        total_seconds=total,
        validator_times=dict(validator_times),
    )


def add_timing(metrics: TimingMetrics, name: str, seconds: float) -> TimingMetrics:
    """Add a timing entry, returning a new TimingMetrics instance.

    Args:
        metrics: Existing TimingMetrics
        name: Validator name
        seconds: Elapsed time in seconds

    Returns:
        New TimingMetrics with added entry
    """
    new_times = dict(metrics.validator_times)
    new_times[name] = seconds
    return create_timing_metrics(new_times)


def format_timing_report(metrics: TimingMetrics) -> str:
    """Format timing metrics as a report string.

    Args:
        metrics: TimingMetrics to format

    Returns:
        Formatted report string
    """
    lines = ["", "Timing:"]
    for name, seconds in sorted(metrics.validator_times.items(), key=lambda x: -x[1]):
        lines.append(f"  {name}: {seconds:.3f}s")
    lines.append(f"  Total: {metrics.total_seconds:.3f}s")
    return "\n".join(lines)


def print_header() -> None:
    """Print the header with version information."""
    version = get_validator_version()
    print("=" * 60)
    print(f"PRE-PUSH VALIDATOR RESULTS (v{version})")
    print("=" * 60)


def build_json_output(
    results: List[Any],
    metrics: TimingMetrics,
    include_timing: bool,
) -> Dict[str, Any]:
    """Build JSON output dictionary.

    Args:
        results: List of validator results
        metrics: TimingMetrics instance
        include_timing: Whether to include timing data

    Returns:
        Dict suitable for JSON serialization
    """
    return {
        "version": get_validator_version(),
        "timestamp": datetime.now().isoformat(),
        "results": [
            {"name": r.name, "checks": r.checks, "passed": r.passed, "output": r.output}
            for r in results
        ],
        "timing": metrics.validator_times if include_timing else None,
    }


@dataclass(frozen=True)
class ValidatorResult:
    """Result from running a validator."""

    name: str
    checks: str
    passed: bool
    output: str
    skipped: bool = False


def run_with_fallback(
    validator_func: Callable[[], ValidatorResult],
    fallback_name: str,
    fallback_checks: str,
) -> ValidatorResult:
    """Run a validator with graceful error handling.

    Args:
        validator_func: Validator function to run
        fallback_name: Name to use in error result
        fallback_checks: Check numbers for error result

    Returns:
        ValidatorResult, either from validator or skipped fallback
    """
    try:
        return validator_func()
    except FileNotFoundError as error:
        return ValidatorResult(
            name=fallback_name,
            checks=fallback_checks,
            passed=False,
            output=f"Validator not found: {error} (skipped)",
            skipped=True,
        )
    except Exception as error:
        return ValidatorResult(
            name=fallback_name,
            checks=fallback_checks,
            passed=False,
            output=f"Validator error: {error} (skipped)",
            skipped=True,
        )


def run_python_style_checks(files: List[Path]) -> ValidatorResult:
    """Run Python style checks on files."""
    py_files = [f for f in files if f.suffix == ".py"]
    if not py_files:
        return ValidatorResult(
            name="Python Style",
            checks="1,2,3,4",
            passed=True,
            output="No Python files to check",
        )

    result = subprocess.run(
        [sys.executable, str(VALIDATORS_DIR / "python_style_checks.py")]
        + [str(f) for f in py_files],
        capture_output=True,
        text=True,
    )

    return ValidatorResult(
        name="Python Style",
        checks="1,2,3,4",
        passed=result.returncode == 0,
        output=result.stdout or "All checks passed",
    )


def run_test_safety_checks(files: List[Path]) -> ValidatorResult:
    """Run test safety checks on test files."""
    test_files = [f for f in files if "test" in f.name.lower() and f.suffix == ".py"]
    if not test_files:
        return ValidatorResult(
            name="Test Safety",
            checks="11,21",
            passed=True,
            output="No test files to check",
        )

    result = subprocess.run(
        [sys.executable, str(VALIDATORS_DIR / "test_safety_checks.py")]
        + [str(f) for f in test_files],
        capture_output=True,
        text=True,
    )

    return ValidatorResult(
        name="Test Safety",
        checks="11,21",
        passed=result.returncode == 0,
        output=result.stdout or "All checks passed",
    )


def get_project_root() -> Optional[Path]:
    """Get project root by finding git root."""
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return Path(result.stdout.strip())
    return None


def run_file_structure_checks(project_root: Optional[Path] = None) -> ValidatorResult:
    """Run file structure checks on project."""
    if project_root is None:
        project_root = get_project_root()

    if project_root is None:
        return ValidatorResult(
            name="File Structure",
            checks="14,15",
            passed=True,
            output="Not in a git repository - skipping",
        )

    result = subprocess.run(
        [sys.executable, str(VALIDATORS_DIR / "file_structure_checks.py"), str(project_root)],
        capture_output=True,
        text=True,
    )

    return ValidatorResult(
        name="File Structure",
        checks="14,15",
        passed=result.returncode == 0,
        output=result.stdout or "All checks passed",
    )


def run_react_checks(files: List[Path]) -> ValidatorResult:
    """Run React checks on TSX/JSX files."""
    react_files = [f for f in files if f.suffix in (".tsx", ".jsx")]
    if not react_files:
        return ValidatorResult(
            name="React",
            checks="17",
            passed=True,
            output="No React files to check",
        )

    result = subprocess.run(
        [sys.executable, str(VALIDATORS_DIR / "react_checks.py")]
        + [str(f) for f in react_files],
        capture_output=True,
        text=True,
    )

    return ValidatorResult(
        name="React",
        checks="17",
        passed=result.returncode == 0,
        output=result.stdout or "All checks passed",
    )


def run_git_checks() -> ValidatorResult:
    """Run git/GitHub checks."""
    result = subprocess.run(
        [sys.executable, str(VALIDATORS_DIR / "git_checks.py")],
        capture_output=True,
        text=True,
    )

    return ValidatorResult(
        name="Git/PR Workflow",
        checks="23,24",
        passed=result.returncode == 0,
        output=result.stdout or "All checks passed",
    )


def run_comment_checks(files: List[Path]) -> ValidatorResult:
    """Comment preservation is enforced by code_rules_enforcer hook.

    The hook compares old vs new content to block NEW comments and
    block DELETION of existing comments. This standalone validator
    is disabled because it flags ALL comments in existing files,
    which forces agents to remove them to pass validation.
    """
    return ValidatorResult(
        name="No Comments",
        checks="26",
        passed=True,
        output="Handled by code_rules_enforcer hook (old vs new comparison)",
    )


def run_ruff_checks(files: List[Path]) -> ValidatorResult:
    """Run ruff for fast Python linting."""
    if not check_ruff_available():
        return ValidatorResult(
            name="Ruff",
            checks="37",
            passed=True,
            output="Ruff not installed - skipping",
        )

    result = run_ruff_check(files)

    return ValidatorResult(
        name="Ruff",
        checks="37",
        passed=result.passed,
        output=result.output,
    )


def run_mypy_checks(files: List[Path]) -> ValidatorResult:
    """Run mypy for static type checking."""
    if not check_mypy_available():
        return ValidatorResult(
            name="Mypy",
            checks="39,40",
            passed=True,
            output="Mypy not installed - skipping",
        )

    result = run_mypy_check(files)

    return ValidatorResult(
        name="Mypy",
        checks="39,40",
        passed=result.passed,
        output=result.output[:500] if len(result.output) > 500 else result.output,
    )


def run_abbreviation_checks(files: List[Path]) -> ValidatorResult:
    """Run abbreviation checks on Python files."""
    py_files = [f for f in files if f.suffix == ".py"]
    if not py_files:
        return ValidatorResult(
            name="Abbreviations",
            checks="5",
            passed=True,
            output="No Python files to check",
        )

    result = subprocess.run(
        [sys.executable, str(VALIDATORS_DIR / "abbreviation_checks.py")]
        + [str(f) for f in py_files],
        capture_output=True,
        text=True,
    )

    return ValidatorResult(
        name="Abbreviations",
        checks="5",
        passed=result.returncode == 0,
        output=result.stdout or "All checks passed",
    )


def run_pr_reference_checks(files: List[Path]) -> ValidatorResult:
    """Run PR reference checks on code files."""
    code_files = [f for f in files if f.suffix in (".py", ".ts", ".tsx", ".js", ".jsx")]
    if not code_files:
        return ValidatorResult(
            name="PR References",
            checks="6",
            passed=True,
            output="No code files to check",
        )

    result = subprocess.run(
        [sys.executable, str(VALIDATORS_DIR / "pr_reference_checks.py")]
        + [str(f) for f in code_files],
        capture_output=True,
        text=True,
    )

    return ValidatorResult(
        name="PR References",
        checks="6",
        passed=result.returncode == 0,
        output=result.stdout or "All checks passed",
    )


def run_magic_value_checks(files: List[Path]) -> ValidatorResult:
    """Run magic value checks on Python files."""
    py_files = [f for f in files if f.suffix == ".py"]
    if not py_files:
        return ValidatorResult(
            name="Magic Values",
            checks="7",
            passed=True,
            output="No Python files to check",
        )

    result = subprocess.run(
        [sys.executable, str(VALIDATORS_DIR / "magic_value_checks.py")]
        + [str(f) for f in py_files],
        capture_output=True,
        text=True,
    )

    return ValidatorResult(
        name="Magic Values",
        checks="7",
        passed=result.returncode == 0,
        output=result.stdout or "All checks passed",
    )


def run_useless_test_checks(files: List[Path]) -> ValidatorResult:
    """Run useless test checks on test files."""
    test_files = [f for f in files if "test" in f.name.lower() and f.suffix == ".py"]
    if not test_files:
        return ValidatorResult(
            name="Useless Tests",
            checks="12",
            passed=True,
            output="No test files to check",
        )

    result = subprocess.run(
        [sys.executable, str(VALIDATORS_DIR / "useless_test_checks.py")]
        + [str(f) for f in test_files],
        capture_output=True,
        text=True,
    )

    return ValidatorResult(
        name="Useless Tests",
        checks="12",
        passed=result.returncode == 0,
        output=result.stdout or "All checks passed",
    )


def run_security_checks(files: List[Path]) -> ValidatorResult:
    """Run security checks on Python files."""
    py_files = [f for f in files if f.suffix == ".py"]
    if not py_files:
        return ValidatorResult(
            name="Security",
            checks="27,28,29",
            passed=True,
            output="No Python files to check",
        )

    result = subprocess.run(
        [sys.executable, str(VALIDATORS_DIR / "security_checks.py")]
        + [str(f) for f in py_files],
        capture_output=True,
        text=True,
    )

    return ValidatorResult(
        name="Security",
        checks="27,28,29",
        passed=result.returncode == 0,
        output=result.stdout or "All checks passed",
    )


def run_code_quality_checks(files: List[Path]) -> ValidatorResult:
    """Run code quality checks on Python files."""
    py_files = [f for f in files if f.suffix == ".py"]
    if not py_files:
        return ValidatorResult(
            name="Code Quality",
            checks="30,31,32",
            passed=True,
            output="No Python files to check",
        )

    result = subprocess.run(
        [sys.executable, str(VALIDATORS_DIR / "code_quality_checks.py")]
        + [str(f) for f in py_files],
        capture_output=True,
        text=True,
    )

    return ValidatorResult(
        name="Code Quality",
        checks="30,31,32",
        passed=result.returncode == 0,
        output=result.stdout or "All checks passed",
    )


def run_python_antipattern_checks(files: List[Path]) -> ValidatorResult:
    """Run Python anti-pattern checks on Python files."""
    py_files = [f for f in files if f.suffix == ".py"]
    if not py_files:
        return ValidatorResult(
            name="Python Anti-patterns",
            checks="33,34,35",
            passed=True,
            output="No Python files to check",
        )

    result = subprocess.run(
        [sys.executable, str(VALIDATORS_DIR / "python_antipattern_checks.py")]
        + [str(f) for f in py_files],
        capture_output=True,
        text=True,
    )

    return ValidatorResult(
        name="Python Anti-patterns",
        checks="33,34,35",
        passed=result.returncode == 0,
        output=result.stdout or "All checks passed",
    )


def run_todo_checks(files: List[Path]) -> ValidatorResult:
    """Run TODO/FIXME checks on Python files."""
    py_files = [f for f in files if f.suffix == ".py"]
    if not py_files:
        return ValidatorResult(
            name="TODO Tracking",
            checks="36",
            passed=True,
            output="No Python files to check",
        )

    result = subprocess.run(
        [sys.executable, str(VALIDATORS_DIR / "todo_checks.py")]
        + [str(f) for f in py_files],
        capture_output=True,
        text=True,
    )

    return ValidatorResult(
        name="TODO Tracking",
        checks="36",
        passed=result.returncode == 0,
        output=result.stdout or "All checks passed",
    )


def run_type_safety_checks(files: List[Path]) -> ValidatorResult:
    """Run type safety checks on Python files."""
    py_files = [f for f in files if f.suffix == ".py"]
    if not py_files:
        return ValidatorResult(
            name="Type Safety",
            checks="39,40",
            passed=True,
            output="No Python files to check",
        )

    result = subprocess.run(
        [sys.executable, str(VALIDATORS_DIR / "type_safety_checks.py")]
        + [str(f) for f in py_files],
        capture_output=True,
        text=True,
    )

    return ValidatorResult(
        name="Type Safety",
        checks="39,40",
        passed=result.returncode == 0,
        output=result.stdout or "All checks passed",
    )


def fix_python_style(files: List[Path]) -> List[str]:
    """Apply Python style fixes to files.

    Args:
        files: List of files to fix

    Returns:
        List of files that were fixed
    """
    from python_style_checks import fix_file

    fixed_files: List[str] = []
    py_files = [f for f in files if f.suffix == ".py"]

    for file_path in py_files:
        if fix_file(file_path):
            fixed_files.append(str(file_path))

    return fixed_files


def get_changed_files() -> List[Path]:
    """Get list of files changed in current commit/staging."""
    # Try staged files first
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )

    files = result.stdout.strip().split("\n") if result.stdout.strip() else []

    # If no staged files, try last commit
    if not files:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1"],
            capture_output=True,
            text=True,
        )
        files = result.stdout.strip().split("\n") if result.stdout.strip() else []

    return [Path(f) for f in files if f]


def main() -> int:
    """Run all validators and report results."""
    parser = argparse.ArgumentParser(description="Run pre-push validators")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Auto-fix violations where possible",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Run health check only",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output",
    )
    parser.add_argument(
        "--context",
        type=int,
        default=2,
        help="Lines of context around violations",
    )
    args = parser.parse_args()

    if args.health:
        from health_check import get_system_health, print_health_report
        health = get_system_health()
        print_health_report(health)
        return 0 if health.all_healthy else 1

    mode = OutputMode.JSON if args.json else OutputMode.TEXT
    formatter = OutputFormatter(
        mode=mode,
        use_colors=not args.no_color,
        context_lines=args.context,
    )

    start_time = time.time()

    if not args.json:
        print(formatter.format_header("PRE-PUSH VALIDATOR RESULTS"))

    files = get_changed_files()
    if not files:
        if not args.json:
            print("No changed files detected. Skipping file-based checks.\n")
    else:
        if not args.json:
            print(f"Checking {len(files)} changed file(s):")
            for file_path in files[:10]:
                print(f"  - {file_path}")
            if len(files) > 10:
                print(f"  ... and {len(files) - 10} more")
            print()

    if args.fix and files and not args.json:
        print("Applying auto-fixes...")
        fixed_files = fix_python_style(files)
        if fixed_files:
            print(f"Fixed {len(fixed_files)} file(s):")
            for fixed_file in fixed_files:
                print(f"  - {fixed_file}")
            print()
        else:
            print("No auto-fixes needed.")
            print()

    results: List[ValidatorResult] = []
    validators: List[Tuple[str, Callable[[], ValidatorResult]]] = []

    if files:
        validators = [
            ("Python Style", lambda: run_python_style_checks(files)),
            ("Test Safety", lambda: run_test_safety_checks(files)),
            ("React", lambda: run_react_checks(files)),
            ("Comments", lambda: run_comment_checks(files)),
            ("Ruff", lambda: run_ruff_checks(files)),
            ("Mypy", lambda: run_mypy_checks(files)),
            ("Abbreviations", lambda: run_abbreviation_checks(files)),
            ("PR References", lambda: run_pr_reference_checks(files)),
            ("Magic Values", lambda: run_magic_value_checks(files)),
            ("Useless Tests", lambda: run_useless_test_checks(files)),
            ("Security", lambda: run_security_checks(files)),
            ("Code Quality", lambda: run_code_quality_checks(files)),
            ("Python Anti-patterns", lambda: run_python_antipattern_checks(files)),
            ("TODO Tracking", lambda: run_todo_checks(files)),
            ("Type Safety", lambda: run_type_safety_checks(files)),
        ]

    validators.extend([
        ("File Structure", run_file_structure_checks),
        ("Git/PR", run_git_checks),
    ])

    for i, (name, validator_func) in enumerate(validators, 1):
        if not args.json:
            progress = formatter.format_progress(i, len(validators), name)
            print(f"\r{progress}", end="", flush=True)

        result = validator_func()
        results.append(result)

    if not args.json:
        print("\r" + " " * 60 + "\r", end="")

    all_passed = all(r.passed for r in results)
    passed_count = sum(1 for r in results if r.passed)
    failed_count = len(results) - passed_count

    if args.json:
        json_results: List[ValidatorResultDict] = [
            {"name": r.name, "checks": r.checks, "passed": r.passed, "output": r.output}
            for r in results
        ]
        print(formatter.format_results(json_results))
    else:
        for result in results:
            print(formatter.format_result(result.name, result.checks, result.passed, result.output))
            print()

        elapsed = time.time() - start_time
        print(formatter.format_stats(len(files), failed_count, elapsed))
        print(formatter.format_summary(passed_count, failed_count))

        print()
        print("MANUAL CHECKS REQUIRED:")
        print("  [ ] Constants near usage")
        print("  [ ] Consistent terminology")
        print("  [ ] Required vs optional params")
        print("  [ ] Single responsibility")
        print("  [ ] No over-engineering")
        print()

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
