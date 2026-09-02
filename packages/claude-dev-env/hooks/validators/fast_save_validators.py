"""In-process, Mypy-free validator roster for the Write/Edit save-path gate.

``run_all_validators.py``'s PreToolUse gate calls ``run_fast_save_validators``
in place of the CLI/full mode's per-check subprocess and its Mypy pass.

::

    save path (this module):    12 checks, in-process, no Mypy, no subprocess
    CLI / full mode (run_all_validators.main): the same 12 checks, plus Mypy
        and Ruff, each still its own subprocess -- unchanged by this module

Every check here calls the exact same ``validate_file`` (or check) function
the CLI mode calls. A save-path finding matches the CLI mode's finding for
the same validator; only Mypy and the process-per-check overhead are gone.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from hooks_constants.mypy_integration_constants import PYTHON_SOURCE_SUFFIX

from .abbreviation_checks import validate_file as validate_abbreviation_file
from .code_quality_checks import validate_file as validate_code_quality_file
from .config.fast_save_validator_constants import (
    ALL_CODE_REFERENCE_FILE_SUFFIXES,
    ALL_REACT_COMPONENT_FILE_SUFFIXES,
    NO_CODE_REFERENCE_FILES_MESSAGE,
    NO_PYTHON_FILES_MESSAGE,
    NO_REACT_FILES_MESSAGE,
    NO_TEST_FILES_MESSAGE,
    NO_VIOLATIONS_FOUND_MESSAGE,
    VIOLATION_REPORT_LINE_SEPARATOR,
)
from .magic_value_checks import validate_file as validate_magic_literal_file
from .pr_reference_checks import validate_file as validate_pr_reference_file
from .python_antipattern_checks import validate_file as validate_python_antipattern_file
from .python_style_checks import validate_file as validate_python_style_file
from .react_checks import check_no_class_components
from .security_checks import validate_file as validate_security_file
from .test_safety_checks import (
    check_debug_guard_in_dev_scripts,
    check_no_skip_decorators,
)
from .todo_checks import validate_file as validate_todo_file
from .type_safety_checks import validate_file as validate_type_safety_file
from .useless_test_checks import validate_file as validate_useless_test_file
from .validator_base import ValidatorResult

FilePredicate = Callable[[Path], bool]
FileViolationLineCollector = Callable[[Path], "list[str]"]
_RawFileValidator = Callable[[Path], "Sequence[object]"]


def _violation_lines_from(raw_validate_file: _RawFileValidator) -> FileViolationLineCollector:
    """Wrap a ``validate_file`` returning check-specific Violation objects.

    ::

        wrap(abbreviation_checks.validate_file) -> Callable[[Path], list[str]]

    Each check module defines its own ``Violation``-shaped dataclass with a
    matching ``__str__``, so formatting through ``str()`` here needs no shared
    base type across the four differently-typed modules that define one.

    Args:
        raw_validate_file: A module's own ``validate_file(path) -> [Violation, ...]``.

    Returns:
        A collector returning each violation's ``str()`` line, not the
        object itself.
    """

    def _collect(file_path: Path) -> list[str]:
        return [str(each_violation) for each_violation in raw_validate_file(file_path)]

    return _collect


def _is_python_file(file_path: Path) -> bool:
    return file_path.suffix == PYTHON_SOURCE_SUFFIX


def _is_test_python_file(file_path: Path) -> bool:
    return "test" in file_path.name.lower() and file_path.suffix == PYTHON_SOURCE_SUFFIX


def _is_react_file(file_path: Path) -> bool:
    return file_path.suffix in ALL_REACT_COMPONENT_FILE_SUFFIXES


def _is_code_reference_file(file_path: Path) -> bool:
    return file_path.suffix in ALL_CODE_REFERENCE_FILE_SUFFIXES


def _collect_test_safety_violation_lines(file_path: Path) -> "list[str]":
    """Adapt test_safety_checks's whole-batch ``main`` into one file at a time."""
    try:
        code = file_path.read_text(encoding="utf-8")
    except OSError:
        return []
    filepath = str(file_path)
    all_violations = [
        *check_no_skip_decorators(code, filepath),
        *check_debug_guard_in_dev_scripts(code, filepath),
    ]
    return [str(each_violation) for each_violation in all_violations]


def _collect_react_violation_lines(file_path: Path) -> "list[str]":
    """Adapt react_checks's whole-batch ``check_no_class_components`` to one file."""
    return [
        str(each_violation)
        for each_violation in check_no_class_components([str(file_path)])
    ]


@dataclass(frozen=True)
class _FastSaveValidatorSpecification:
    """One save-path validator: display name, check numbers, and how to run it."""

    display_name: str
    checks: str
    applies_to_file: FilePredicate
    collect_violation_lines: FileViolationLineCollector
    no_matching_files_message: str


def _all_fast_save_validator_specifications() -> (
    "tuple[_FastSaveValidatorSpecification, ...]"
):
    """Return the save-path roster: every non-Mypy, non-Ruff file-scoped check."""
    return (
        # Python naming, style, and constants.
        _FastSaveValidatorSpecification(
            "Python Style",
            "1,2,3,4",
            _is_python_file,
            _violation_lines_from(validate_python_style_file),
            NO_PYTHON_FILES_MESSAGE,
        ),
        _FastSaveValidatorSpecification(
            "Abbreviations",
            "5",
            _is_python_file,
            _violation_lines_from(validate_abbreviation_file),
            NO_PYTHON_FILES_MESSAGE,
        ),
        _FastSaveValidatorSpecification(
            "Magic Values",
            "7",
            _is_python_file,
            _violation_lines_from(validate_magic_literal_file),
            NO_PYTHON_FILES_MESSAGE,
        ),
        # Python code quality and TODO tracking.
        _FastSaveValidatorSpecification(
            "TODO Tracking",
            "36",
            _is_python_file,
            _violation_lines_from(validate_todo_file),
            NO_PYTHON_FILES_MESSAGE,
        ),
        _FastSaveValidatorSpecification(
            "Security",
            "27,28,29",
            _is_python_file,
            _violation_lines_from(validate_security_file),
            NO_PYTHON_FILES_MESSAGE,
        ),
        _FastSaveValidatorSpecification(
            "Code Quality",
            "30,31,32",
            _is_python_file,
            _violation_lines_from(validate_code_quality_file),
            NO_PYTHON_FILES_MESSAGE,
        ),
        # Python anti-patterns and typing.
        _FastSaveValidatorSpecification(
            "Python Anti-patterns",
            "33,34,35",
            _is_python_file,
            _violation_lines_from(validate_python_antipattern_file),
            NO_PYTHON_FILES_MESSAGE,
        ),
        _FastSaveValidatorSpecification(
            "Type Safety",
            "39,40",
            _is_python_file,
            _violation_lines_from(validate_type_safety_file),
            NO_PYTHON_FILES_MESSAGE,
        ),
        # Scoped to a test_*.py-shaped file.
        _FastSaveValidatorSpecification(
            "Test Safety",
            "11,21",
            _is_test_python_file,
            _collect_test_safety_violation_lines,
            NO_TEST_FILES_MESSAGE,
        ),
        _FastSaveValidatorSpecification(
            "Useless Tests",
            "12",
            _is_test_python_file,
            _violation_lines_from(validate_useless_test_file),
            NO_TEST_FILES_MESSAGE,
        ),
        # Non-Python or multi-language files.
        _FastSaveValidatorSpecification(
            "React",
            "17",
            _is_react_file,
            _collect_react_violation_lines,
            NO_REACT_FILES_MESSAGE,
        ),
        _FastSaveValidatorSpecification(
            "PR References",
            "6",
            _is_code_reference_file,
            _violation_lines_from(validate_pr_reference_file),
            NO_CODE_REFERENCE_FILES_MESSAGE,
        ),
    )


def _fast_save_outcome(
    specification: _FastSaveValidatorSpecification,
    is_clean: bool,
    violation_report: str,
) -> ValidatorResult:
    """Build one result from a specification's display name and check numbers."""
    return ValidatorResult(
        name=specification.display_name,
        checks=specification.checks,
        passed=is_clean,
        output=violation_report,
    )


def _run_specification(
    specification: _FastSaveValidatorSpecification, files: "list[Path]"
) -> ValidatorResult:
    """Run one validator's violation collector in-process over its matching files."""
    matching_files = [
        each_file for each_file in files if specification.applies_to_file(each_file)
    ]
    if not matching_files:
        return _fast_save_outcome(
            specification, True, specification.no_matching_files_message
        )
    all_violation_lines = [
        each_line
        for each_file in matching_files
        for each_line in specification.collect_violation_lines(each_file)
    ]
    if not all_violation_lines:
        return _fast_save_outcome(specification, True, NO_VIOLATIONS_FOUND_MESSAGE)
    violation_report = VIOLATION_REPORT_LINE_SEPARATOR.join(all_violation_lines)
    return _fast_save_outcome(specification, False, violation_report)


def run_fast_save_validators(files: "list[Path]") -> "list[ValidatorResult]":
    """Run every save-path validator in-process, skipping Mypy and Ruff.

    Args:
        files: The files under validation -- one reconstructed file in gate mode.

    Returns:
        One result per in-process validator, in roster order. The caller adds
        Ruff and never adds Mypy.
    """
    return [
        _run_specification(each_specification, files)
        for each_specification in _all_fast_save_validator_specifications()
    ]
