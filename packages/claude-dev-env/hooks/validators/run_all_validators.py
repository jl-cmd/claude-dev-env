"""Run all pre-push validators and report results.

This script orchestrates all automated validators and produces a unified report.
Exit code 0 = all checks pass, 1 = violations found.
"""

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Tuple

from .baseline_diff import _scope_new_and_preexisting
from .branch_scoped_runners import (
    get_project_root,
    run_comment_checks,
    run_file_structure_checks,
    run_git_checks,
)
from .config import (
    DEFAULT_CONTEXT_LINES,
    FILE_DISPLAY_CAP,
    LINE_SEPARATOR,
    SEPARATOR_WIDTH,
)
from .file_content_io import fix_python_style, get_changed_files
from .file_scoped_runners import (
    invoke_validator_module,
    run_abbreviation_checks,
    run_code_quality_checks,
    run_file_scoped_validators,
    run_magic_value_checks,
    run_mypy_checks,
    run_pr_reference_checks,
    run_python_antipattern_checks,
    run_python_style_checks,
    run_react_checks,
    run_ruff_checks,
    run_security_checks,
    run_test_safety_checks,
    run_todo_checks,
    run_type_safety_checks,
    run_useless_test_checks,
    validate_proposed_file,
)
from .health_check import get_system_health, get_validator_version, print_health_report
from .output_formatter import OutputFormatter, OutputMode, ValidatorResultDict
from .pre_tool_use_gate import reconstruct_proposed_content, run_pre_tool_use_gate
from .validator_env import hooks_dir
from .validator_result import ValidatorResult, run_with_fallback
from .validator_subprocess import (
    _hooks_subprocess_working_directory_and_environment,
    run_validators_entrypoint_subprocess,
)
from .violation_parsing import _violation_line_number

__all__ = [
    "ValidatorResult",
    "_hooks_subprocess_working_directory_and_environment",
    "_scope_new_and_preexisting",
    "_violation_line_number",
    "add_timing",
    "build_json_output",
    "create_timing_metrics",
    "fix_python_style",
    "format_timing_report",
    "get_changed_files",
    "get_project_root",
    "hooks_dir",
    "invoke_validator_module",
    "main",
    "print_header",
    "reconstruct_proposed_content",
    "run_abbreviation_checks",
    "run_code_quality_checks",
    "run_comment_checks",
    "run_file_scoped_validators",
    "run_file_structure_checks",
    "run_git_checks",
    "run_magic_value_checks",
    "run_mypy_checks",
    "run_pr_reference_checks",
    "run_pre_tool_use_gate",
    "run_python_antipattern_checks",
    "run_python_style_checks",
    "run_react_checks",
    "run_ruff_checks",
    "run_security_checks",
    "run_test_safety_checks",
    "run_todo_checks",
    "run_type_safety_checks",
    "run_useless_test_checks",
    "run_validators_entrypoint_subprocess",
    "run_with_fallback",
    "validate_proposed_file",
]


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
    for each_name, each_seconds in sorted(
        metrics.validator_times.items(), key=lambda each_item: -each_item[1]
    ):
        lines.append(f"  {each_name}: {each_seconds:.3f}s")
    lines.append(f"  Total: {metrics.total_seconds:.3f}s")
    return LINE_SEPARATOR.join(lines)


def print_header() -> None:
    """Print the header with version information."""
    version = get_validator_version()
    print("=" * SEPARATOR_WIDTH)
    print(f"PRE-PUSH VALIDATOR RESULTS (v{version})")
    print("=" * SEPARATOR_WIDTH)


def build_json_output(
    results: List["ValidatorResult"],
    metrics: TimingMetrics,
    include_timing: bool,
) -> Dict[str, object]:
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


def _build_argument_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for the validator entry point."""
    parser = argparse.ArgumentParser(description="Run pre-push validators")
    parser.add_argument(
        "--fix", action="store_true", help="Auto-fix violations where possible"
    )
    parser.add_argument("--health", action="store_true", help="Run health check only")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    parser.add_argument(
        "--context",
        type=int,
        default=DEFAULT_CONTEXT_LINES,
        help="Lines of context around violations",
    )
    parser.add_argument(
        "--pre-tool-use",
        action="store_true",
        help="Run as a PreToolUse gate on the single proposed file write from stdin",
    )
    return parser


def _print_changed_files(files: List[Path], as_json: bool) -> None:
    """Print the changed-file summary unless JSON output is requested."""
    if as_json:
        return
    if not files:
        print("No changed files detected. Skipping file-based checks.\n")
        return
    print(f"Checking {len(files)} changed file(s):")
    for each_file in files[:FILE_DISPLAY_CAP]:
        print(f"  - {each_file}")
    if len(files) > FILE_DISPLAY_CAP:
        print(f"  ... and {len(files) - FILE_DISPLAY_CAP} more")
    print()


def _apply_auto_fixes(files: List[Path]) -> None:
    """Apply Python style auto-fixes and report the files changed."""
    print("Applying auto-fixes...")
    all_fixed_files = fix_python_style(files)
    if not all_fixed_files:
        print("No auto-fixes needed.")
        print()
        return
    print(f"Fixed {len(all_fixed_files)} file(s):")
    for each_fixed_file in all_fixed_files:
        print(f"  - {each_fixed_file}")
    print()


def _build_validators(
    files: List[Path],
) -> List[Tuple[str, Callable[[], ValidatorResult]]]:
    """Return the ordered (name, call) pairs for every validator to run."""
    all_file_scoped: List[Tuple[str, Callable[[], ValidatorResult]]] = []
    if files:
        all_file_scoped = [
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
    return all_file_scoped + [
        ("File Structure", run_file_structure_checks),
        ("Git/PR", run_git_checks),
    ]


def _run_validators(
    all_validators: List[Tuple[str, Callable[[], ValidatorResult]]],
    formatter: OutputFormatter,
    as_json: bool,
) -> List[ValidatorResult]:
    """Run each validator in order, showing progress unless JSON is requested."""
    all_results: List[ValidatorResult] = []
    for each_index, (each_name, each_call) in enumerate(all_validators, 1):
        if not as_json:
            progress = formatter.format_progress(each_index, len(all_validators), each_name)
            print(f"\r{progress}", end="", flush=True)
        all_results.append(each_call())
    if not as_json:
        print("\r" + " " * SEPARATOR_WIDTH + "\r", end="")
    return all_results


def _print_manual_checklist() -> None:
    """Print the manual-review checklist footer."""
    print("MANUAL CHECKS REQUIRED:")
    print("  [ ] Constants near usage")
    print("  [ ] Consistent terminology")
    print("  [ ] Required vs optional params")
    print("  [ ] Single responsibility")
    print("  [ ] No over-engineering")
    print()


def _report_text_results(
    all_results: List[ValidatorResult],
    files: List[Path],
    formatter: OutputFormatter,
    start_time: float,
) -> None:
    """Print the per-validator text results, stats, summary, and checklist."""
    for each_result in all_results:
        print(
            formatter.format_result(
                each_result.name,
                each_result.checks,
                each_result.passed,
                each_result.output,
            )
        )
        print()
    passed_count = sum(1 for each_result in all_results if each_result.passed)
    failed_count = len(all_results) - passed_count
    elapsed = time.time() - start_time
    print(formatter.format_stats(len(files), failed_count, elapsed))
    print(formatter.format_summary(passed_count, failed_count))
    print()
    _print_manual_checklist()


def _report_json_results(
    all_results: List[ValidatorResult], formatter: OutputFormatter
) -> None:
    """Print the validator results as JSON."""
    all_json_results: List[ValidatorResultDict] = [
        {
            "name": each_result.name,
            "checks": each_result.checks,
            "passed": each_result.passed,
            "output": each_result.output,
        }
        for each_result in all_results
    ]
    print(formatter.format_results(all_json_results))


def _run_cli_report(args: argparse.Namespace) -> int:
    """Run every validator and print the report, returning the exit code."""
    formatter = OutputFormatter(
        mode=OutputMode.JSON if args.json else OutputMode.TEXT,
        use_colors=not args.no_color,
        context_lines=args.context,
    )
    start_time = time.time()
    if not args.json:
        print(formatter.format_header("PRE-PUSH VALIDATOR RESULTS"))
    files = get_changed_files()
    _print_changed_files(files, args.json)
    if args.fix and files and not args.json:
        _apply_auto_fixes(files)
    all_results = _run_validators(_build_validators(files), formatter, args.json)
    if args.json:
        _report_json_results(all_results, formatter)
    else:
        _report_text_results(all_results, files, formatter, start_time)
    return 0 if all(each_result.passed for each_result in all_results) else 1


def main() -> int:
    """Run all validators and report results."""
    args = _build_argument_parser().parse_args()
    if args.pre_tool_use:
        return run_pre_tool_use_gate()
    if args.health:
        health = get_system_health()
        print_health_report(health)
        return 0 if health.all_healthy else 1
    return _run_cli_report(args)


if __name__ == "__main__":
    sys.exit(main())
