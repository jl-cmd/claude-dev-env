"""Python style validation package.

Importing this package places the hooks tree on ``sys.path`` before any
submodule body runs, so sibling ``blocking`` and ``hooks_constants`` packages
resolve regardless of the order a submodule lists its own imports.
"""

import sys
from pathlib import Path

_hooks_directory_on_path = str(Path(__file__).resolve().parent.parent)
if _hooks_directory_on_path not in sys.path:
    sys.path.insert(0, _hooks_directory_on_path)

from .python_style_checks import (  # noqa: E402
    Violation,
    check_blank_lines_between_functions,
    check_imports_at_top,
    check_no_empty_line_after_decorators,
    check_view_function_naming,
    validate_file,
)

__all__ = [
    "Violation",
    "check_blank_lines_between_functions",
    "check_imports_at_top",
    "check_no_empty_line_after_decorators",
    "check_view_function_naming",
    "validate_file",
]
