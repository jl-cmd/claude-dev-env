"""File suffixes and report text the save-path validator roster reuses.

Config files are exempt from the string-literal magic-value checks, so the
per-language file suffixes and shared report strings live here rather than
inline in ``fast_save_validators.py``.
"""

from hooks_constants.mypy_integration_constants import PYTHON_SOURCE_SUFFIX

TYPESCRIPT_SOURCE_SUFFIX = ".ts"
REACT_TYPESCRIPT_SOURCE_SUFFIX = ".tsx"
JAVASCRIPT_SOURCE_SUFFIX = ".js"
REACT_JAVASCRIPT_SOURCE_SUFFIX = ".jsx"

ALL_REACT_COMPONENT_FILE_SUFFIXES: tuple[str, ...] = (
    REACT_TYPESCRIPT_SOURCE_SUFFIX,
    REACT_JAVASCRIPT_SOURCE_SUFFIX,
)
ALL_CODE_REFERENCE_FILE_SUFFIXES: tuple[str, ...] = (
    PYTHON_SOURCE_SUFFIX,
    TYPESCRIPT_SOURCE_SUFFIX,
    REACT_TYPESCRIPT_SOURCE_SUFFIX,
    JAVASCRIPT_SOURCE_SUFFIX,
    REACT_JAVASCRIPT_SOURCE_SUFFIX,
)

NO_PYTHON_FILES_MESSAGE = "No Python files to check"
NO_TEST_FILES_MESSAGE = "No test files to check"
NO_REACT_FILES_MESSAGE = "No React files to check"
NO_CODE_REFERENCE_FILES_MESSAGE = "No code files to check"
NO_VIOLATIONS_FOUND_MESSAGE = "All checks passed"
VIOLATION_REPORT_LINE_SEPARATOR = "\n"
