"""Run every file-scoped validator against a proposed file, failing closed."""

import tempfile
from pathlib import Path
from typing import Callable, List, Tuple

from .config import (
    ALL_CODE_FILE_EXTENSIONS,
    ALL_REACT_FILE_EXTENSIONS,
    MYPY_OUTPUT_TRUNCATION_LIMIT,
    PYTHON_EXTENSION,
)
from .mypy_integration import check_mypy_available, run_mypy_check
from .ruff_integration import check_ruff_available, run_ruff_check
from .validator_result import ValidatorResult, run_with_fallback
from .validator_subprocess import invoke_validator_module


def run_python_style_checks(files: List[Path]) -> ValidatorResult:
    """Run Python style checks on files."""
    py_files = [each_file for each_file in files if each_file.suffix == PYTHON_EXTENSION]
    if not py_files:
        return ValidatorResult(
            name="Python Style",
            checks="1,2,3,4",
            passed=True,
            output="No Python files to check",
        )

    result = invoke_validator_module("python_style_checks", [str(each_file) for each_file in py_files])

    return ValidatorResult(
        name="Python Style",
        checks="1,2,3,4",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_test_safety_checks(files: List[Path]) -> ValidatorResult:
    """Run test safety checks on test files."""
    test_files = [each_file for each_file in files if "test" in each_file.name.lower() and each_file.suffix == PYTHON_EXTENSION]
    if not test_files:
        return ValidatorResult(
            name="Test Safety",
            checks="11,21",
            passed=True,
            output="No test files to check",
        )

    result = invoke_validator_module("test_safety_checks", [str(each_file) for each_file in test_files])

    return ValidatorResult(
        name="Test Safety",
        checks="11,21",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_react_checks(files: List[Path]) -> ValidatorResult:
    """Run React checks on TSX/JSX files."""
    react_files = [each_file for each_file in files if each_file.suffix in ALL_REACT_FILE_EXTENSIONS]
    if not react_files:
        return ValidatorResult(
            name="React",
            checks="17",
            passed=True,
            output="No React files to check",
        )

    result = invoke_validator_module("react_checks", [str(each_file) for each_file in react_files])

    return ValidatorResult(
        name="React",
        checks="17",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
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
        output=result.output[:MYPY_OUTPUT_TRUNCATION_LIMIT] if len(result.output) > MYPY_OUTPUT_TRUNCATION_LIMIT else result.output,
    )


def run_abbreviation_checks(files: List[Path]) -> ValidatorResult:
    """Run abbreviation checks on Python files."""
    py_files = [each_file for each_file in files if each_file.suffix == PYTHON_EXTENSION]
    if not py_files:
        return ValidatorResult(
            name="Abbreviations",
            checks="5",
            passed=True,
            output="No Python files to check",
        )

    result = invoke_validator_module("abbreviation_checks", [str(each_file) for each_file in py_files])

    return ValidatorResult(
        name="Abbreviations",
        checks="5",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_pr_reference_checks(files: List[Path]) -> ValidatorResult:
    """Run PR reference checks on code files."""
    code_files = [each_file for each_file in files if each_file.suffix in ALL_CODE_FILE_EXTENSIONS]
    if not code_files:
        return ValidatorResult(
            name="PR References",
            checks="6",
            passed=True,
            output="No code files to check",
        )

    result = invoke_validator_module("pr_reference_checks", [str(each_file) for each_file in code_files])

    return ValidatorResult(
        name="PR References",
        checks="6",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_magic_value_checks(files: List[Path]) -> ValidatorResult:
    """Run magic value checks on Python files."""
    py_files = [each_file for each_file in files if each_file.suffix == PYTHON_EXTENSION]
    if not py_files:
        return ValidatorResult(
            name="Magic Values",
            checks="7",
            passed=True,
            output="No Python files to check",
        )

    result = invoke_validator_module("magic_value_checks", [str(each_file) for each_file in py_files])

    return ValidatorResult(
        name="Magic Values",
        checks="7",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_useless_test_checks(files: List[Path]) -> ValidatorResult:
    """Run useless test checks on test files."""
    test_files = [each_file for each_file in files if "test" in each_file.name.lower() and each_file.suffix == PYTHON_EXTENSION]
    if not test_files:
        return ValidatorResult(
            name="Useless Tests",
            checks="12",
            passed=True,
            output="No test files to check",
        )

    result = invoke_validator_module("useless_test_checks", [str(each_file) for each_file in test_files])

    return ValidatorResult(
        name="Useless Tests",
        checks="12",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_security_checks(files: List[Path]) -> ValidatorResult:
    """Run security checks on Python files."""
    py_files = [each_file for each_file in files if each_file.suffix == PYTHON_EXTENSION]
    if not py_files:
        return ValidatorResult(
            name="Security",
            checks="27,28,29",
            passed=True,
            output="No Python files to check",
        )

    result = invoke_validator_module("security_checks", [str(each_file) for each_file in py_files])

    return ValidatorResult(
        name="Security",
        checks="27,28,29",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_code_quality_checks(files: List[Path]) -> ValidatorResult:
    """Run code quality checks on Python files."""
    py_files = [each_file for each_file in files if each_file.suffix == PYTHON_EXTENSION]
    if not py_files:
        return ValidatorResult(
            name="Code Quality",
            checks="30,31,32",
            passed=True,
            output="No Python files to check",
        )

    result = invoke_validator_module("code_quality_checks", [str(each_file) for each_file in py_files])

    return ValidatorResult(
        name="Code Quality",
        checks="30,31,32",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_python_antipattern_checks(files: List[Path]) -> ValidatorResult:
    """Run Python anti-pattern checks on Python files."""
    py_files = [each_file for each_file in files if each_file.suffix == PYTHON_EXTENSION]
    if not py_files:
        return ValidatorResult(
            name="Python Anti-patterns",
            checks="33,34,35",
            passed=True,
            output="No Python files to check",
        )

    result = invoke_validator_module("python_antipattern_checks", [str(each_file) for each_file in py_files])

    return ValidatorResult(
        name="Python Anti-patterns",
        checks="33,34,35",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_todo_checks(files: List[Path]) -> ValidatorResult:
    """Run TODO/FIXME checks on Python files."""
    py_files = [each_file for each_file in files if each_file.suffix == PYTHON_EXTENSION]
    if not py_files:
        return ValidatorResult(
            name="TODO Tracking",
            checks="36",
            passed=True,
            output="No Python files to check",
        )

    result = invoke_validator_module("todo_checks", [str(each_file) for each_file in py_files])

    return ValidatorResult(
        name="TODO Tracking",
        checks="36",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_type_safety_checks(files: List[Path]) -> ValidatorResult:
    """Run type safety checks on Python files."""
    py_files = [each_file for each_file in files if each_file.suffix == PYTHON_EXTENSION]
    if not py_files:
        return ValidatorResult(
            name="Type Safety",
            checks="39,40",
            passed=True,
            output="No Python files to check",
        )

    result = invoke_validator_module("type_safety_checks", [str(each_file) for each_file in py_files])

    return ValidatorResult(
        name="Type Safety",
        checks="39,40",
        passed=result.returncode == 0,
        output=result.stdout or result.stderr or "All checks passed",
    )


def run_file_scoped_validators(all_files: List[Path]) -> List[ValidatorResult]:
    """Run every validator scoped to individual files against *all_files*.

    Excludes the branch-scoped File Structure and Git validators, which grade
    the whole project rather than a single proposed file.

    Args:
        all_files: The files under validation — a single reconstructed file in
            gate mode.

    Returns:
        One ValidatorResult per file-scoped validator, in run order. A validator
        that raises yields a fail-closed result naming it, so one crash cannot
        take down the batch or silently skip its check.
    """
    file_scoped_validators: List[Tuple[str, str, Callable[[], ValidatorResult]]] = [
        ("Python Style", "1,2,3,4", lambda: run_python_style_checks(all_files)),
        ("Test Safety", "11,21", lambda: run_test_safety_checks(all_files)),
        ("React", "17", lambda: run_react_checks(all_files)),
        ("Ruff", "37", lambda: run_ruff_checks(all_files)),
        ("Mypy", "39,40", lambda: run_mypy_checks(all_files)),
        ("Abbreviations", "5", lambda: run_abbreviation_checks(all_files)),
        ("PR References", "6", lambda: run_pr_reference_checks(all_files)),
        ("Magic Values", "7", lambda: run_magic_value_checks(all_files)),
        ("Useless Tests", "12", lambda: run_useless_test_checks(all_files)),
        ("Security", "27,28,29", lambda: run_security_checks(all_files)),
        ("Code Quality", "30,31,32", lambda: run_code_quality_checks(all_files)),
        ("Python Anti-patterns", "33,34,35", lambda: run_python_antipattern_checks(all_files)),
        ("TODO Tracking", "36", lambda: run_todo_checks(all_files)),
        ("Type Safety", "39,40", lambda: run_type_safety_checks(all_files)),
    ]
    return [
        run_with_fallback(each_validator_call, each_name, each_checks)
        for each_name, each_checks, each_validator_call in file_scoped_validators
    ]


def validate_proposed_file(
    file_path: str, proposed_content: str
) -> List[ValidatorResult]:
    """Validate *proposed_content* as if written to *file_path*.

    Writes the content to a temporary file that carries the target's basename so
    suffix-based and test-name-based validator filtering matches the real path,
    then runs the file-scoped validators against it.

    Args:
        file_path: The destination path the write or edit targets.
        proposed_content: The reconstructed post-edit content of that file.

    Returns:
        One ValidatorResult per file-scoped validator.
    """
    base_name = Path(file_path).name
    with tempfile.TemporaryDirectory() as temporary_directory:
        temporary_file = Path(temporary_directory) / base_name
        temporary_file.write_text(proposed_content, encoding="utf-8")
        return run_file_scoped_validators([temporary_file])
