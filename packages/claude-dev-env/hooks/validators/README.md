# Python Style Validators

AST-based Python style checks for code quality enforcement.

The checks live in `python_style_checks.py`. Shared source-line splitting, function discovery, and statement classification live in `python_style_helpers.py`. `python_style_import_bootstrap.py` recognizes the repo's sys.path bootstrap-guard idiom so the imports-at-top check does not penalize a file for following it. `fast_save_validators.py` runs the twelve non-Mypy, non-Ruff checks in-process for the Write/Edit save-path gate, with no per-check subprocess.

## Production modules

| File | Role |
|---|---|
| `abbreviation_checks.py` | Abbreviation and single-letter name checks |
| `code_quality_checks.py` | Function, nesting, and file length checks |
| `comment_checks.py` | Comment detection for the opt-in diff-aware linter |
| `exempt_paths.py` | Shared config, test, and hook-infrastructure path exemptions |
| `fast_save_validators.py` | In-process Write/Edit save-path validator roster |
| `file_structure_checks.py` | File structure checks for pre-PR validation |
| `git_checks.py` | Git and GitHub checks for pre-push review |
| `health_check.py` | Validator availability, dependency, and version checks |
| `magic_value_checks.py` | Hardcoded magic-number checks |
| `mypy_integration.py` | Mypy static type checking integration |
| `output_formatter.py` | Colored, diff, progress, and JSON validator output |
| `pr_reference_checks.py` | PR and commit reference checks in comments |
| `project_roots.py` | Project-root resolution from a path |
| `pyproject_config_discovery.py` | Walk-up discovery of tool pyproject tables |
| `python_antipattern_checks.py` | Mutable defaults, bare except, and print checks |
| `python_style_checks.py` | Import placement, decorator spacing, blank lines, and view naming |
| `python_style_helpers.py` | Source-line splitting and function-discovery helpers |
| `python_style_import_bootstrap.py` | sys.path bootstrap-guard recognizer |
| `react_checks.py` | React class-component and error-boundary checks |
| `ruff_integration.py` | Ruff lint integration |
| `run_all_validators.py` | Pre-push validator orchestration and report |
| `security_checks.py` | Hardcoded-secret, SQL injection, and XSS checks |
| `system_temporary_roots.py` | System temp-root membership for staged copies |
| `todo_checks.py` | TODO/FIXME tracking with issue-reference requirement |
| `type_safety_checks.py` | Missing type hints and Any usage checks |
| `useless_test_checks.py` | Useless-test detection |
| `validator_base.py` | Shared validator dataclasses, source read, and parse |
| `validator_defaults.py` | Shared constants for the validators package |

## Checks Implemented

1. **Imports at top** - All import statements must be at the top of the file
2. **No empty line after decorators** - Decorators must be directly above functions (no blank lines)
3. **Two empty lines between functions** - Exactly two blank lines between top-level functions
4. **View function naming** - Functions in `views.py` with `request` parameter must end with `_view`

## Usage

### Command Line

```bash
python python_style_checks.py file1.py file2.py ...
```

Exit codes:
- `0` - All files pass
- `1` - Violations found or error

### Python API

```python
from python_style_checks import validate_file, Violation
from pathlib import Path

violations = validate_file(Path("myfile.py"))
for v in violations:
    print(v)  # Prints: file:line: message
```

### Individual Checks

```python
import ast
from python_style_checks import (
    check_imports_at_top,
    check_no_empty_line_after_decorators,
    check_blank_lines_between_functions,
    check_view_function_naming,
)

source = Path("myfile.py").read_text()
tree = ast.parse(source)

# Run individual checks
violations = check_imports_at_top(tree, "myfile.py")
violations = check_no_empty_line_after_decorators(source, "myfile.py")
violations = check_blank_lines_between_functions(source, "myfile.py")
violations = check_view_function_naming(tree, "views.py")
```

## Testing

```bash
pytest test_python_style_checks.py -v
```

## Examples

### Valid Code

```python
"""Module docstring."""

import os
import sys
from typing import List


def foo() -> None:
    """Do something."""
    pass


def bar() -> None:
    """Another function."""
    pass
```

### Invalid Code

```python
# Import not at top
def foo() -> None:
    pass

import os  # VIOLATION: Import must be at top

# Empty line after decorator
@decorator

def bar() -> None:  # VIOLATION: No empty line after decorator
    pass

# Wrong spacing between functions
def baz() -> None:
    pass

def qux() -> None:  # VIOLATION: Expected 2 empty lines, found 1
    pass

# View naming (in views.py)
def user_profile(request):  # VIOLATION: Must end with _view
    pass
```

## Integration with Pre-Commit Hooks

Example `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: python-style-checks
        name: Python Style Checks
        entry: python packages/claude-dev-env/hooks/validators/python_style_checks.py
        args: []
        pass_filenames: true
        # Invokes the script directly via its ``__main__`` block so the
        # ``validators`` package qualifier does not need PYTHONPATH setup.
        language: system
        types: [python]
```
