"""Run all pre-push validators and report results.

This script orchestrates all automated validators and produces a unified report.
Exit code 0 = all checks pass, 1 = violations found.
"""
# pragma: no-tdd-gate

import argparse
import ast
import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .config.directory_exemption_constants import (
    ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES,
)
from .health_check import get_system_health, get_validator_version, print_health_report
from .mypy_integration import check_mypy_available, run_mypy_check
from .output_formatter import OutputFormatter, OutputMode, ValidatorResultDict
from .python_style_checks import fix_file
from .ruff_integration import check_ruff_available, run_ruff_check


VALIDATORS_DIR = Path(__file__).parent
hooks_dir = VALIDATORS_DIR.parent
package_name = VALIDATORS_DIR.name

_hooks_directory_on_path = str(hooks_dir.resolve())
if _hooks_directory_on_path not in sys.path:
    sys.path.insert(0, _hooks_directory_on_path)
_blocking_directory_on_path = str((hooks_dir / "blocking").resolve())
if _blocking_directory_on_path not in sys.path:
    sys.path.insert(0, _blocking_directory_on_path)

from blocking.code_rules_shared import is_ephemeral_path  # noqa: E402
from gate_skip_token.records import (  # noqa: E402
    consume_skip_token,
    content_sha256,
    has_valid_skip_token,
    should_downgrade_to_ask,
)
from hooks_constants.hook_block_logger import log_hook_block  # noqa: E402
from hooks_constants.multi_edit_reconstruction import (  # noqa: E402
    apply_edits,
    edits_for_tool,
)


def _windows_non_unc_working_directory_string(
    candidate_directory_strings: list[str | None],
) -> str:
    """Return the first candidate cwd that is not a UNC path (Windows only)."""
    for each_candidate in candidate_directory_strings:
        if each_candidate is None:
            continue
        expanded_candidate = str(Path(each_candidate).expanduser())
        if expanded_candidate.startswith("\\\\"):
            continue
        return expanded_candidate
    current_working_directory = os.getcwd()
    expanded_current_working_directory = str(Path(current_working_directory).expanduser())
    if not expanded_current_working_directory.startswith("\\\\"):
        return expanded_current_working_directory
    raise RuntimeError(
        "Cannot find a non-UNC working directory for hook validator subprocesses."
    )


def _hooks_subprocess_working_directory_and_environment() -> tuple[str, dict[str, str]]:
    """Return cwd and env for validator subprocesses.

    On Windows, ``CreateProcess`` rejects some UNC working directories (invalid
    directory name). When the hooks tree resolves to UNC, use a local temp cwd
    and put the hooks directory on ``PYTHONPATH`` so ``python -m validators.*``
    still resolves.
    """
    hooks_directory_string = str(hooks_dir.resolve())
    environment = os.environ.copy()
    previous_pythonpath = environment.get("PYTHONPATH", "")
    environment["PYTHONPATH"] = (
        hooks_directory_string
        + (os.pathsep + previous_pythonpath if previous_pythonpath else "")
    )
    working_directory_string = hooks_directory_string
    if sys.platform == "win32" and working_directory_string.startswith("\\\\"):
        windows_temp_fallback_directory = str(Path(r"C:\Windows\Temp"))
        working_directory_string = _windows_non_unc_working_directory_string(
            [
                os.environ.get("TEMP"),
                os.environ.get("TMP"),
                tempfile.gettempdir(),
                windows_temp_fallback_directory,
            ]
        )
    return working_directory_string, environment


def invoke_validator_module(module_stem: str, forwarded_file_paths: List[str]) -> subprocess.CompletedProcess[str]:  # pragma: no-tdd-gate
    """Run a sibling validator as ``python -m validators.<module_stem>``.

    The subprocess uses the hooks tree on ``PYTHONPATH`` (and normally ``cwd``
    there). On Windows, if that path is UNC, ``cwd`` falls back to a local temp
    directory so ``CreateProcess`` succeeds.
    """
    qualified_module = ".".join([package_name, module_stem])
    working_directory_string, environment = (
        _hooks_subprocess_working_directory_and_environment()
    )
    return subprocess.run(
        [sys.executable, "-m", qualified_module, *forwarded_file_paths],
        capture_output=True,
        text=True,
        cwd=working_directory_string,
        env=environment,
    )


def run_validators_entrypoint_subprocess(
    extra_arguments: List[str],
    stdin_text: Optional[str] = None,
) -> subprocess.CompletedProcess[str]:
    """Run ``python -m validators.run_all_validators`` with a Windows-safe cwd.

    Args:
        extra_arguments: Argument vector appended after the module name.
        stdin_text: Text replayed as the subprocess stdin, or None to leave
            stdin empty. The PreToolUse gate mode reads its payload from stdin,
            so a caller exercising ``--pre-tool-use`` passes the payload here.

    Returns:
        The completed subprocess carrying its captured stdout and stderr.
    """
    working_directory_string, environment = (
        _hooks_subprocess_working_directory_and_environment()
    )
    entry_module = f"{package_name}.run_all_validators"
    return subprocess.run(
        [sys.executable, "-m", entry_module, *extra_arguments],
        capture_output=True,
        text=True,
        cwd=working_directory_string,
        env=environment,
        input=stdin_text,
    )


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

    result = invoke_validator_module("python_style_checks", [str(f) for f in py_files])

    return ValidatorResult(
        name="Python Style",
        checks="1,2,3,4",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
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

    result = invoke_validator_module("test_safety_checks", [str(f) for f in test_files])

    return ValidatorResult(
        name="Test Safety",
        checks="11,21",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def get_project_root() -> Optional[Path]:
    """Get project root by finding git root.

    Uses ``git -C <hooks_dir>`` to pin git's working tree to the hooks
    directory without setting the subprocess cwd. On Windows, ``CreateProcess``
    rejects some UNC working directories, so setting ``cwd=hooks_dir`` would
    fail when ``hooks_dir`` resolves to a UNC path. The ``-C`` flag tells git
    to operate as if started in that directory while the subprocess itself
    inherits a normal cwd from the caller. Anchoring git to ``hooks_dir`` is
    required so the lookup resolves to this repo even when the caller's cwd
    points at an unrelated git checkout (e.g., the user's home), avoiding
    validators that ``rglob`` over tens of thousands of unrelated files.
    """
    completed_git_lookup = subprocess.run(
        ["git", "-C", str(hooks_dir), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if completed_git_lookup.returncode == 0:
        return Path(completed_git_lookup.stdout.strip())
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

    result = invoke_validator_module("file_structure_checks", [str(project_root)])

    return ValidatorResult(
        name="File Structure",
        checks="14,15",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
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

    result = invoke_validator_module("react_checks", [str(f) for f in react_files])

    return ValidatorResult(
        name="React",
        checks="17",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_git_checks() -> ValidatorResult:
    """Run git/GitHub checks."""
    result = invoke_validator_module("git_checks", [])

    return ValidatorResult(
        name="Git/PR Workflow",
        checks="23,24",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_comment_checks(files: List[Path]) -> ValidatorResult:
    """Comment preservation is enforced by code_rules_enforcer hook.

    The hook compares old vs new content to block NEW comments and
    print a stderr advisory when an existing comment is removed. This
    standalone validator is disabled because it flags ALL comments in
    existing files, which forces agents to remove them to pass validation.
    """
    return ValidatorResult(
        name="No Comments",
        checks="26",
        passed=True,
        output="Handled by code_rules_enforcer hook (old vs new comparison)",
    )


def run_ruff_checks(
    files: List[Path], config_source_path: Optional[Path] = None
) -> ValidatorResult:
    """Run ruff for fast Python linting."""
    if not check_ruff_available():
        return ValidatorResult(
            name="Ruff",
            checks="37",
            passed=True,
            output="Ruff not installed - skipping",
        )

    result = run_ruff_check(files, config_source_path)

    return ValidatorResult(
        name="Ruff",
        checks="37",
        passed=result.passed,
        output=result.output,
    )


def run_mypy_checks(
    files: List[Path], config_source_path: Optional[Path] = None
) -> ValidatorResult:
    """Run mypy for static type checking."""
    if not check_mypy_available():
        return ValidatorResult(
            name="Mypy",
            checks="39,40",
            passed=True,
            output="Mypy not installed - skipping",
        )

    result = run_mypy_check(files, config_source_path)

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

    result = invoke_validator_module("abbreviation_checks", [str(f) for f in py_files])

    return ValidatorResult(
        name="Abbreviations",
        checks="5",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
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

    result = invoke_validator_module("pr_reference_checks", [str(f) for f in code_files])

    return ValidatorResult(
        name="PR References",
        checks="6",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
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

    result = invoke_validator_module("magic_value_checks", [str(f) for f in py_files])

    return ValidatorResult(
        name="Magic Values",
        checks="7",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
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

    result = invoke_validator_module("useless_test_checks", [str(f) for f in test_files])

    return ValidatorResult(
        name="Useless Tests",
        checks="12",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
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

    result = invoke_validator_module("security_checks", [str(f) for f in py_files])

    return ValidatorResult(
        name="Security",
        checks="27,28,29",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
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

    result = invoke_validator_module("code_quality_checks", [str(f) for f in py_files])

    return ValidatorResult(
        name="Code Quality",
        checks="30,31,32",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
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

    result = invoke_validator_module("python_antipattern_checks", [str(f) for f in py_files])

    return ValidatorResult(
        name="Python Anti-patterns",
        checks="33,34,35",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
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

    result = invoke_validator_module("todo_checks", [str(f) for f in py_files])

    return ValidatorResult(
        name="TODO Tracking",
        checks="36",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
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

    result = invoke_validator_module("type_safety_checks", [str(f) for f in py_files])

    return ValidatorResult(
        name="Type Safety",
        checks="39,40",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def fix_python_style(files: List[Path]) -> List[str]:
    """Apply Python style fixes to files.

    Args:
        files: List of files to fix

    Returns:
        List of files that were fixed
    """
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


def _read_target_file_content(file_path: str) -> Optional[str]:
    """Return the on-disk content of *file_path*, or None when it cannot be read."""
    try:
        with open(file_path, "r", encoding="utf-8") as readable_file:
            return readable_file.read()
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None


def reconstruct_proposed_content(
    tool_name: str, tool_input: Dict[str, object]
) -> Optional[str]:
    """Return the post-edit content one Write, Edit, or MultiEdit payload leaves on disk.

    ::

        Write     -> tool_input["content"] verbatim
        Edit      -> existing file, each old_string rewritten to new_string
        MultiEdit -> existing file, each edit applied in order

    The Edit and MultiEdit reconstruction reuses the shared applier so this gate
    judges the same post-edit content the standalone blockers judge.

    Args:
        tool_name: The intercepted tool — Write, Edit, or MultiEdit.
        tool_input: The tool's input payload.

    Returns:
        The proposed post-edit content, or None when the payload carries no
        readable target for an edit or no string content for a write.
    """
    if tool_name == "Write":
        written_content = tool_input.get("content", "")
        return written_content if isinstance(written_content, str) else None
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        return None
    existing_content = _read_target_file_content(file_path)
    if existing_content is None:
        return None
    return apply_edits(existing_content, edits_for_tool(tool_name, dict(tool_input)))


def run_file_scoped_validators(
    all_files: List[Path], config_source_path: Optional[Path] = None
) -> List[ValidatorResult]:
    """Run every file-scoped validator against *all_files*.

    Excludes the branch-scoped File Structure and Git validators.

    Args:
        all_files: The files under validation — one reconstructed file in gate mode.
        config_source_path: Original path ruff and mypy resolve their config from.

    Returns:
        One ValidatorResult per file-scoped validator, in run order.
    """
    return [
        run_python_style_checks(all_files),
        run_test_safety_checks(all_files),
        run_react_checks(all_files),
        run_ruff_checks(all_files, config_source_path),
        run_mypy_checks(all_files, config_source_path),
        run_abbreviation_checks(all_files),
        run_pr_reference_checks(all_files),
        run_magic_value_checks(all_files),
        run_useless_test_checks(all_files),
        run_security_checks(all_files),
        run_code_quality_checks(all_files),
        run_python_antipattern_checks(all_files),
        run_todo_checks(all_files),
        run_type_safety_checks(all_files),
    ]


def _escapes_temporary_root(path_part: str) -> bool:
    """Return True when a path part would climb out of or re-anchor the temp root.

    ::

        ok:   "scripts"  -> False (stays inside)
        flag: ".."       -> True  (climbs a level)
        flag: "/etc"     -> True  (absolute, re-anchors the join)

    A ``..`` component escapes upward and an absolute or anchored component
    re-roots the join away from the temporary directory. Both are dropped so a
    staged file cannot land outside the ephemeral root.

    Args:
        path_part: A single path component drawn from the destination path.

    Returns:
        True when the component must be dropped to keep staging contained.
    """
    if path_part == os.pardir:
        return True
    part_as_path = Path(path_part)
    return part_as_path.is_absolute() or bool(part_as_path.anchor)


def _temporary_path_preserving_directory_signal(
    temporary_directory: Path, file_path: str
) -> Path:
    """Build a temp path that keeps exemption directory tails and the basename.

    Directory-based exemptions (for example ``/scripts/`` CLI markers and
    ``/tests/`` test-path patterns) match substrings of the file path. Staging
    under a flat temp basename drops those segments. Mirroring only the
    exemption-relevant directory tail (plus basename) restores that signal
    without copying absolute system prefixes such as pytest ``tmp_path`` parents
    that contain ``test_`` and would falsely trip test-file exemptions.

    Args:
        temporary_directory: Root of the ephemeral staging tree.
        file_path: Real destination path the write or edit targets.

    Returns:
        Path under *temporary_directory* ending in the exemption directory tail
        (when present) and the real basename.
    """
    destination_path = Path(file_path)
    path_parts = destination_path.parts
    if destination_path.anchor:
        path_parts = path_parts[1:]
    if not path_parts:
        path_parts = (destination_path.name,)

    all_directory_exemption_segment_names = ALL_DIRECTORY_EXEMPTION_SEGMENT_NAMES
    start_index = len(path_parts) - 1
    for each_index, each_part in enumerate(path_parts[:-1]):
        if each_part.lower() not in all_directory_exemption_segment_names:
            continue
        start_index = each_index
        break

    selected_parts = path_parts[start_index:]
    contained_parts = tuple(
        each_part for each_part in selected_parts if not _escapes_temporary_root(each_part)
    )
    if not contained_parts:
        contained_parts = (destination_path.name,)
    temporary_file = temporary_directory.joinpath(*contained_parts)
    if not temporary_file.resolve().is_relative_to(temporary_directory.resolve()):
        temporary_file = temporary_directory / destination_path.name
    temporary_file.parent.mkdir(parents=True, exist_ok=True)
    return temporary_file


def validate_proposed_file(
    file_path: str,
    proposed_content: str,
    config_source_path: Optional[Path] = None,
) -> List[ValidatorResult]:
    """Validate *proposed_content* as if written to *file_path*.

    Writes the content to a temporary file that preserves the exemption-relevant
    directory tail and basename so directory-based exemptions, suffix-based
    filtering, and test-name-based filtering match the real path, then runs the
    file-scoped validators against it. Ruff and mypy resolve their config by
    walking up from the config source path, so the staged copy is graded under
    the project config the real path sits in rather than the temp directory's.

    Args:
        file_path: The destination path the write or edit targets.
        proposed_content: The reconstructed post-edit content of that file.
        config_source_path: Path ruff and mypy resolve their config from;
            defaults to *file_path* when the caller passes nothing.

    Returns:
        One ValidatorResult per file-scoped validator.
    """
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_file = _temporary_path_preserving_directory_signal(
            Path(temporary_directory), file_path
        )
        temporary_file.write_text(proposed_content, encoding="utf-8")
        resolved_config_source_path = (
            config_source_path
            if config_source_path is not None
            else Path(file_path)
        )
        return run_file_scoped_validators(
            [temporary_file], config_source_path=resolved_config_source_path
        )


def _validator_summaries(results: List[ValidatorResult]) -> str:
    """Join one ``name (checks): output`` summary per result with a separator.

    Args:
        results: The validator results to summarize.

    Returns:
        The joined summary text shared by the deny reason and the warning.
    """
    validator_summary_separator = " | "
    return validator_summary_separator.join(
        f"{each_result.name} (checks {each_result.checks}): {each_result.output.strip()}"
        for each_result in results
    )


def _proposed_content_deny_reason(failed_results: List[ValidatorResult]) -> str:
    """Compose the deny reason naming each failing validator and its output.

    Args:
        failed_results: The validator results that did not pass.

    Returns:
        The composed ``permissionDecisionReason`` text.
    """
    return (
        f"BLOCKED: [validators] {len(failed_results)} "
        f"validator(s) failed: {_validator_summaries(failed_results)}"
    )


def _emit_pre_tool_use_deny(deny_reason: str) -> None:
    """Write one PreToolUse deny JSON payload carrying *deny_reason* to stdout."""
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": deny_reason,
        }
    }
    log_hook_block(
        calling_hook_name="run_all_validators.py",
        hook_event="PreToolUse",
        block_reason=deny_reason,
    )
    sys.stdout.write(json.dumps(deny_payload) + "\n")
    sys.stdout.flush()


def _emit_pre_tool_use_ask(ask_reason: str) -> None:
    """Write one PreToolUse ask JSON payload escalating the block to a human prompt.

    ::

        deny  -> a new violation, or no valid token: the block stands
        ask   -> only pre-existing findings under a valid token: a human grants

    Args:
        ask_reason: The ``permissionDecisionReason`` naming the pre-existing
            findings a human must approve.
    """
    ask_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": ask_reason,
        }
    }
    log_hook_block(
        calling_hook_name="run_all_validators.py",
        hook_event="PreToolUse",
        block_reason=ask_reason,
    )
    sys.stdout.write(json.dumps(ask_payload) + "\n")
    sys.stdout.flush()


def _record_function_spans(
    parent_node: ast.AST, name_prefix: str, name_by_line: dict[int, str]
) -> None:
    """Assign each line inside a function to that function's qualified name.

    Inner functions overwrite the enclosing name, so a line resolves to its
    innermost function; a method resolves to ``Class.method``.

    Args:
        parent_node: The AST node whose children are walked.
        name_prefix: The dotted qualifier accumulated from enclosing scopes.
        name_by_line: The line-to-name map filled in place.
    """
    for each_child in ast.iter_child_nodes(parent_node):
        if isinstance(each_child, ast.ClassDef):
            _record_function_spans(each_child, f"{name_prefix}{each_child.name}.", name_by_line)
        elif isinstance(each_child, ast.FunctionDef | ast.AsyncFunctionDef):
            qualified_name = f"{name_prefix}{each_child.name}"
            last_line = each_child.end_lineno or each_child.lineno
            for each_line in range(each_child.lineno, last_line + 1):
                name_by_line[each_line] = qualified_name
            _record_function_spans(each_child, f"{qualified_name}.", name_by_line)
        else:
            _record_function_spans(each_child, name_prefix, name_by_line)


def _enclosing_function_name_by_line(content: str) -> dict[int, str]:
    """Map each source line to its innermost enclosing function's qualified name.

    ::

        def outer():             # lines 1-4 -> "outer"
            def inner():         # lines 2-3 -> "outer.inner"
                return None
            return inner
        log_start()              # line 5 -> "" (module scope)

    Args:
        content: The full source text to parse.

    Returns:
        A line-to-name map; a line outside every function has no entry, so a
        lookup yields the empty string for module scope. An unparseable source
        yields an empty map.
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return {}
    name_by_line: dict[int, str] = {}
    _record_function_spans(tree, "", name_by_line)
    return name_by_line


def _violation_line_number(output_line: str) -> int:
    """Return the source line a validator's location prefix names.

    ::

        /pkg/legacy_module.py:37: magic number    -> line number 37
        /pkg/legacy_module.py:37:5: F401 unused   -> line number 37
        a summary line with no file location      -> line number 0
        1 | import os  (ruff code frame)          -> line number 0

    The line is the first colon-delimited field that is all digits, with every
    later prefix field also all digits (the column) and every earlier field
    reading like a path — no pipes or quotes, though spaces are allowed so a
    spaced directory or file name still parses. A ruff code-frame line quoting
    source text carries a pipe or quote before any digits, so frame and
    summary noise resolves to 0.

    Args:
        output_line: One printed ``Violation`` line from a validator.

    Returns:
        The parsed line number, or 0 for a line with no ``file:line`` prefix.
    """
    prefix_fields = output_line.partition(": ")[0].split(":")
    for each_field_index, each_field in enumerate(prefix_fields):
        if not each_field.isdigit():
            continue
        return _line_number_when_prefix_is_a_location(prefix_fields, each_field_index)
    return 0


def _line_number_when_prefix_is_a_location(
    prefix_fields: List[str], digit_field_index: int
) -> int:
    """Return the digit field as a line number when its prefix reads ``path:line``.

    Args:
        prefix_fields: The colon-split fields of the text before the message.
        digit_field_index: The index of the first all-digit field.

    Returns:
        The line number, or 0 when the surrounding fields do not form a
        ``path:line[:col]`` location.
    """
    non_path_characters = ("|", '"')
    if digit_field_index == 0:
        return 0
    path_fields = prefix_fields[:digit_field_index]
    looks_like_a_path = not any(
        each_character in each_path_field
        for each_path_field in path_fields
        for each_character in non_path_characters
    )
    trailing_fields = prefix_fields[digit_field_index + 1 :]
    if looks_like_a_path and all(each_field.isdigit() for each_field in trailing_fields):
        return int(prefix_fields[digit_field_index])
    return 0


def _identity_scope(output_line: str, name_by_line: dict[int, str]) -> str:
    """Return the enclosing-function name a single violation line belongs to.

    Args:
        output_line: One printed ``Violation`` line from a validator.
        name_by_line: The line-to-name map for the content that produced it.

    Returns:
        The enclosing function's qualified name, or the empty string for a
        module-scope or unlocatable violation.
    """
    return name_by_line.get(_violation_line_number(output_line), "")


def _failed_results(all_results: List[ValidatorResult]) -> List[ValidatorResult]:
    """Return the results that fired — not passed and not skipped."""
    return [
        each_result
        for each_result in all_results
        if not each_result.passed and not each_result.skipped
    ]


ViolationIdentity = tuple[str, str, str]


def _violation_message(output_line: str) -> str:
    """Return the message text after the ``path:line[:col]: `` location prefix.

    Args:
        output_line: One located violation line from a validator.

    Returns:
        The text after the first colon-space separator.
    """
    return output_line.partition(": ")[2]


def _located_violation_lines(each_result: ValidatorResult) -> List[str]:
    """Return the result's output lines that carry a real ``file:line`` location.

    Ruff code frames, help hints, and ``Found N errors`` summaries carry no
    location, so they are dropped rather than classified.

    Args:
        each_result: The failing validator result to filter.

    Returns:
        The located violation lines in output order.
    """
    return [
        each_output_line
        for each_output_line in each_result.output.splitlines()
        if _violation_line_number(each_output_line) > 0
    ]


def _line_identity(
    validator_name: str, output_line: str, name_by_line: dict[int, str]
) -> ViolationIdentity:
    """Return one line's ``(validator, enclosing function, message)`` identity key.

    Args:
        validator_name: The name of the validator that printed the line.
        output_line: One located violation line.
        name_by_line: The line-to-name map for the content that produced it.

    Returns:
        The identity key for baseline comparison.
    """
    return (
        validator_name,
        _identity_scope(output_line, name_by_line),
        _violation_message(output_line),
    )


def _violation_identities(
    failed_results: List[ValidatorResult], content: str
) -> Counter[ViolationIdentity]:
    """Count each located violation line by its identity key.

    Keying on the enclosing function rather than the raw line number keeps a
    key stable when an edit shifts that function, and counting rather than set
    membership keeps a second violation of the same validator in the same
    function visible as new.

    Args:
        failed_results: The validator results that fired.
        content: The source text those results were produced against.

    Returns:
        The multiset of violation identity keys.
    """
    name_by_line = _enclosing_function_name_by_line(content)
    return Counter(
        _line_identity(each_result.name, each_output_line, name_by_line)
        for each_result in failed_results
        for each_output_line in _located_violation_lines(each_result)
    )


def _baseline_violation_identities(file_path: str) -> Counter[ViolationIdentity]:
    """Return the violation identity counts the on-disk file already carries.

    Args:
        file_path: The write's target path, read as the pre-edit baseline.

    Returns:
        The baseline identity multiset, empty when the file is absent or empty.
    """
    baseline_content = _read_target_file_content(file_path)
    if not baseline_content:
        return Counter()
    baseline_failed = _failed_results(validate_proposed_file(file_path, baseline_content))
    return _violation_identities(baseline_failed, baseline_content)


def _identity_key_counts(
    baseline_identities: Counter[ViolationIdentity],
) -> Counter[tuple[str, str]]:
    """Sum baseline counts down to ``(validator, enclosing function)`` keys.

    Args:
        baseline_identities: The baseline identity multiset.

    Returns:
        The per-key line counts with messages ignored, so a violation whose
        message drifted with the edit still finds its baseline budget.
    """
    key_counts: Counter[tuple[str, str]] = Counter()
    for each_identity, each_count in baseline_identities.items():
        key_counts[each_identity[:2]] += each_count
    return key_counts


def _result_with_output(
    source_result: ValidatorResult, all_output_lines: List[str]
) -> ValidatorResult:
    """Return a copy of *source_result* carrying only *all_output_lines*."""
    output_line_separator = "\n"
    return ValidatorResult(
        name=source_result.name,
        checks=source_result.checks,
        passed=False,
        output=output_line_separator.join(all_output_lines),
    )


def _consume_exact_matches(
    all_line_identities: List[ViolationIdentity],
    remaining_exact: Counter[ViolationIdentity],
    remaining_by_key: Counter[tuple[str, str]],
) -> set[int]:
    """Mark the lines whose full identity matches an unconsumed baseline entry.

    Args:
        all_line_identities: One identity per located line, in output order.
        remaining_exact: The unconsumed baseline identity budget, decremented
            in place per match.
        remaining_by_key: The unconsumed per-key budget, decremented in step.

    Returns:
        The indexes of the exactly-matched lines.
    """
    all_matched_line_indexes: set[int] = set()
    for each_line_index, each_identity in enumerate(all_line_identities):
        if remaining_exact[each_identity] <= 0:
            continue
        remaining_exact[each_identity] -= 1
        remaining_by_key[each_identity[:2]] -= 1
        all_matched_line_indexes.add(each_line_index)
    return all_matched_line_indexes


def _line_is_preexisting(
    line_index: int,
    all_line_identities: List[ViolationIdentity],
    all_matched_line_indexes: set[int],
    remaining_by_key: Counter[tuple[str, str]],
) -> bool:
    """Return whether one located line matches the baseline budget.

    An exact identity match is pre-existing. A leftover line whose
    ``(validator, enclosing function)`` key still has baseline budget is
    pre-existing with a drifted message. A line beyond its key's budget is new.

    Args:
        line_index: The line's position in the located-line order.
        all_line_identities: One identity per located line.
        all_matched_line_indexes: The exactly-matched line indexes.
        remaining_by_key: The unconsumed per-key budget, decremented in place.

    Returns:
        True when the line is pre-existing, False when it is new.
    """
    if line_index in all_matched_line_indexes:
        return True
    each_key = all_line_identities[line_index][:2]
    if remaining_by_key[each_key] > 0:
        remaining_by_key[each_key] -= 1
        return True
    return False


def _partition_output_lines(
    each_result: ValidatorResult,
    name_by_line: dict[int, str],
    remaining_exact: Counter[ViolationIdentity],
    remaining_by_key: Counter[tuple[str, str]],
) -> tuple[List[str], List[str]]:
    """Split one result's located lines into a (new, pre-existing) line pair.

    The exact and per-key baseline budgets are consumed in place, exact
    matches first, so a later result never double-spends an earlier match.
    """
    located_lines = _located_violation_lines(each_result)
    all_line_identities = [
        _line_identity(each_result.name, each_line, name_by_line)
        for each_line in located_lines
    ]
    all_matched_line_indexes = _consume_exact_matches(
        all_line_identities, remaining_exact, remaining_by_key
    )
    all_new_lines: List[str] = []
    all_preexisting_lines: List[str] = []
    for each_line_index, each_line in enumerate(located_lines):
        is_preexisting = _line_is_preexisting(
            each_line_index, all_line_identities, all_matched_line_indexes, remaining_by_key
        )
        (all_preexisting_lines if is_preexisting else all_new_lines).append(each_line)
    return all_new_lines, all_preexisting_lines


def _grouped_result_lines(
    each_result: ValidatorResult, all_partitioned_lines: tuple[List[str], List[str]]
) -> tuple[List[ValidatorResult], List[ValidatorResult]]:
    """Return one result's (new, pre-existing) groups from its partitioned lines.

    A failed result with no located line at all cannot be baseline-matched, so
    it stays new in full — the gate fails closed rather than letting an
    unlocatable failure through.
    """
    all_new_lines, all_preexisting_lines = all_partitioned_lines
    if not all_new_lines and not all_preexisting_lines:
        return [each_result], []
    new_results = [_result_with_output(each_result, all_new_lines)] if all_new_lines else []
    preexisting_results = (
        [_result_with_output(each_result, all_preexisting_lines)]
        if all_preexisting_lines
        else []
    )
    return new_results, preexisting_results


def _scope_new_and_preexisting(
    all_proposed_failed_results: List[ValidatorResult],
    proposed_content: str,
    baseline_identities: Counter[ViolationIdentity],
) -> tuple[List[ValidatorResult], List[ValidatorResult]]:
    """Group proposed violations into newly-introduced and pre-existing results.

    Args:
        all_proposed_failed_results: The validators that fired on the proposed file.
        proposed_content: The reconstructed post-edit source text.
        baseline_identities: The identity counts the on-disk baseline carries.

    Returns:
        A ``(new_results, preexisting_results)`` pair.
    """
    name_by_line = _enclosing_function_name_by_line(proposed_content)
    remaining_exact = Counter(baseline_identities)
    remaining_by_key = _identity_key_counts(baseline_identities)
    all_new_results: List[ValidatorResult] = []
    all_preexisting_results: List[ValidatorResult] = []
    for each_result in all_proposed_failed_results:
        new_results, preexisting_results = _grouped_result_lines(
            each_result,
            _partition_output_lines(each_result, name_by_line, remaining_exact, remaining_by_key),
        )
        all_new_results.extend(new_results)
        all_preexisting_results.extend(preexisting_results)
    return all_new_results, all_preexisting_results


def _emit_pre_existing_warning(all_preexisting_results: List[ValidatorResult]) -> None:
    """Write a stderr advisory naming each pre-existing violation left in place."""
    advisory_summaries = _validator_summaries(all_preexisting_results)
    sys.stderr.write(
        "[run_all_validators] allowed with warning: "
        f"pre-existing violation(s) unchanged: {advisory_summaries}\n"
    )
    sys.stderr.flush()


def _decide_pre_tool_use(
    file_path: str, proposed_content: str, permission_mode: str, session_id: str
) -> None:
    """Deny only violations absent from the baseline; warn on the ones that persist.

    A new violation never downgrades: the escalation guard treats "proposed
    findings are a subset of the on-disk findings" as "there are no new
    results", which is false whenever a new result exists. So a valid token
    escalates to a human ``ask`` only when every proposed failure is
    pre-existing, and a new violation always denies.

    Args:
        file_path: The write's target path.
        proposed_content: The reconstructed post-edit content of that file.
        permission_mode: The PreToolUse permission mode of the write.
        session_id: The session a skip token belongs to.
    """
    all_proposed_failed = _failed_results(
        validate_proposed_file(file_path, proposed_content)
    )
    if not all_proposed_failed:
        return
    baseline_identities = _baseline_violation_identities(file_path)
    all_new_results, all_preexisting_results = _scope_new_and_preexisting(
        all_proposed_failed, proposed_content, baseline_identities
    )
    if all_preexisting_results:
        _emit_pre_existing_warning(all_preexisting_results)
    if not all_new_results:
        return
    proposed_content_hash = content_sha256(proposed_content)
    has_token = has_valid_skip_token(session_id, file_path, proposed_content_hash)
    deny_reason = _proposed_content_deny_reason(all_new_results)
    if should_downgrade_to_ask(permission_mode, not all_new_results, has_token):
        consume_skip_token(session_id, file_path, proposed_content_hash)
        _emit_pre_tool_use_ask(deny_reason)
        return
    _emit_pre_tool_use_deny(deny_reason)


def _evaluate_pre_tool_use_payload() -> None:
    """Read the PreToolUse payload from stdin and deny only newly-introduced violations.

    The path-based exemption decision runs against the real target path from the
    payload, so an ephemeral scratch or session scratchpad target passes without
    validation before any baseline-scoped decision runs. For a non-exempt target,
    each located violation is keyed by validator name, enclosing function, and
    message, then counted against the on-disk baseline. A violation beyond the
    baseline's budget for its key denies the write; one the baseline already
    carries passes with a stderr advisory. Writes nothing for a clean file, an
    exempt target, or an unparseable payload.
    """
    pre_tool_use_payload = json.load(sys.stdin)
    if not isinstance(pre_tool_use_payload, dict):
        return
    tool_name = pre_tool_use_payload.get("tool_name", "")
    tool_input = pre_tool_use_payload.get("tool_input", {})
    if not isinstance(tool_name, str) or not isinstance(tool_input, dict):
        return
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        return
    if is_ephemeral_path(file_path, pre_tool_use_payload):
        return
    proposed_content = reconstruct_proposed_content(tool_name, tool_input)
    if not proposed_content:
        return
    permission_mode = pre_tool_use_payload.get("permission_mode", "")
    session_id = pre_tool_use_payload.get("session_id", "")
    _decide_pre_tool_use(file_path, proposed_content, permission_mode, session_id)


def run_pre_tool_use_gate() -> int:
    """Run the PreToolUse gate, never crashing the tool call on an internal error.

    A hook that raises is rendered by the harness as a tool malfunction, so an
    unexpected failure here logs to stderr and returns 0 rather than propagating.

    Returns:
        Always 0 — the gate signals a block through the deny payload, not an
        exit code.
    """
    try:
        _evaluate_pre_tool_use_payload()
    except json.JSONDecodeError:
        return 0
    except Exception as error:
        sys.stderr.write(f"[run_all_validators] pre-tool-use gate error: {error}\n")
        sys.stderr.flush()
    return 0


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
    parser.add_argument(
        "--pre-tool-use",
        action="store_true",
        help="Run as a PreToolUse gate on the single proposed file write from stdin",
    )
    args = parser.parse_args()

    if args.pre_tool_use:
        return run_pre_tool_use_gate()

    if args.health:
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
