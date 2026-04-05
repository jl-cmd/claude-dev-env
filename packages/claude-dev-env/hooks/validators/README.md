# Python Style Validators

AST-based Python style checks for code quality enforcement.

## Checks Implemented

1. **Imports at top** - All import statements must be at the top of the file
2. **No empty line after decorators** - Decorators must be directly above functions (no blank lines)
3. **Single empty line between functions** - Exactly one blank line between top-level functions
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
    check_single_empty_line_between_functions,
    check_view_function_naming,
)

source = Path("myfile.py").read_text()
tree = ast.parse(source)

# Run individual checks
violations = check_imports_at_top(tree, "myfile.py")
violations = check_no_empty_line_after_decorators(source, "myfile.py")
violations = check_single_empty_line_between_functions(source, "myfile.py")
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

@decorator
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


def qux() -> None:  # VIOLATION: Expected 1 empty line, found 2
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
        entry: python hooks/validators/python_style_checks.py
        language: system
        types: [python]
```
