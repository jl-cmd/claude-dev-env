"""Constants-outside-config checks and the file-global constant use-count check."""

import ast
import re
import sys
from pathlib import Path
from typing import Optional

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_path_utils import (  # noqa: E402
    is_config_file,
)
from code_rules_shared import (  # noqa: E402
    _build_parent_map,
    get_file_extension,
    is_migration_file,
    is_test_file,
    is_workflow_registry_file,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_PYTHON_EXTENSIONS,
    FILE_GLOBAL_UPPER_SNAKE_PATTERN,
)


def check_constants_outside_config(content: str, file_path: str) -> list[str]:
    """Check for UPPER_SNAKE constants defined outside config files."""
    if is_config_file(file_path):
        return []

    if is_test_file(file_path):
        return []

    if is_workflow_registry_file(file_path):
        return []

    if is_migration_file(file_path):
        return []

    issues = []
    lines = content.split("\n")
    is_inside_function = False
    is_inside_class = False

    constant_pattern = re.compile(r"^([A-Z][A-Z0-9_]{2,})(?:\s*:\s*[^=]+)?\s*=\s*[^=]")

    for each_line_number, each_line in enumerate(lines, 1):
        stripped = each_line.strip()

        if not stripped:
            continue

        if re.match(r"^(async\s+)?def\s+\w+", stripped):
            is_inside_function = True
            continue

        if re.match(r"^class\s+\w+", stripped):
            is_inside_class = True
            is_inside_function = False
            continue

        indent = len(each_line) - len(each_line.lstrip())
        if indent == 0 and stripped and not stripped.startswith(("#", "@", ")")):
            is_inside_function = False
            is_inside_class = False

        if not is_inside_function and not is_inside_class:
            match = constant_pattern.match(stripped)
            if match:
                constant_name = match.group(1)
                if constant_name not in ("__all__",):
                    issues.append(f"Line {each_line_number}: Constant {constant_name} - move to config/")

    return issues


def _is_exempt_for_advisory_scan(file_path: str) -> bool:
    """Return True when the file is exempt from the function-local UPPER_SNAKE advisory."""
    if is_config_file(file_path):
        return True
    if is_test_file(file_path):
        return True
    if is_workflow_registry_file(file_path):
        return True
    if is_migration_file(file_path):
        return True
    return False


def _scan_function_body_constants(content: str) -> list[str]:
    """Return advisory messages for UPPER_SNAKE assignments inside function bodies.

    Only lines inside a function body (tracked via an indent stack) are
    flagged. Module-level assignments and class-body assignments are ignored.
    """
    advisory_issues: list[str] = []
    lines = content.split("\n")
    function_indent_stack: list[int] = []
    constant_pattern = re.compile(r"^([A-Z][A-Z0-9_]{2,})(?:\s*:\s*[^=]+)?\s*=\s*[^=]")

    for each_line_number, each_line in enumerate(lines, 1):
        stripped = each_line.strip()

        if not stripped:
            continue

        indent = len(each_line) - len(each_line.lstrip())

        while function_indent_stack and indent <= function_indent_stack[-1] and not stripped.startswith(("#", "@", ")")):
            function_indent_stack.pop()

        if re.match(r"^class\s+\w+", stripped):
            if indent == 0:
                function_indent_stack.clear()
            continue

        if re.match(r"^(async\s+)?def\s+\w+", stripped):
            function_indent_stack.append(indent)
            continue

        if function_indent_stack:
            match = constant_pattern.match(stripped)
            if match:
                constant_name = match.group(1)
                advisory_issues.append(
                    f"Line {each_line_number}: Function-local constant {constant_name} - consider moving to config/"
                )

    return advisory_issues


def check_constants_outside_config_advisory(content: str, file_path: str) -> list[str]:
    """Return advisory entries for UPPER_SNAKE assignments inside function bodies.

    Module-level UPPER_SNAKE outside config/ is blocking (see
    check_constants_outside_config). Function-local UPPER_SNAKE is a softer
    smell — it belongs in config/ but does not block the write. This function
    surfaces those as advisory so callers can route them to stderr rather than
    to the blocking deny payload.
    """
    if _is_exempt_for_advisory_scan(file_path):
        return []
    return _scan_function_body_constants(content)


def _is_upper_snake_constant_name(name: str) -> bool:
    """Return True for UPPER_SNAKE identifiers including those with a leading underscore."""
    return bool(FILE_GLOBAL_UPPER_SNAKE_PATTERN.match(name))


def _collect_module_level_upper_snake_constants(
    module_tree: ast.Module,
) -> dict[str, int]:
    """Return mapping of module-level UPPER_SNAKE constant name to its line number."""
    constants_by_name: dict[str, int] = {}
    for each_node in module_tree.body:
        if isinstance(each_node, ast.Assign):
            for each_target in each_node.targets:
                if isinstance(each_target, ast.Name) and _is_upper_snake_constant_name(each_target.id):
                    constants_by_name.setdefault(each_target.id, each_node.lineno)
        elif isinstance(each_node, ast.AnnAssign):
            if isinstance(each_node.target, ast.Name) and _is_upper_snake_constant_name(each_node.target.id):
                constants_by_name.setdefault(each_node.target.id, each_node.lineno)
    return constants_by_name


def _resolve_enclosing_function_qname(
    load_node: ast.Name,
    parent_by_child_id: dict[int, ast.AST],
) -> Optional[str]:
    """Return 'ClassName.function_name' or 'function_name' for the enclosing function.

    Returns None when the reference is at module scope (no enclosing function).
    Decorator expressions on a function/method count as belonging to that function.
    """
    enclosing_function_name: Optional[str] = None
    enclosing_class_name: Optional[str] = None
    current_ancestor = parent_by_child_id.get(id(load_node))
    while current_ancestor is not None:
        if isinstance(current_ancestor, (ast.FunctionDef, ast.AsyncFunctionDef)) and enclosing_function_name is None:
            enclosing_function_name = current_ancestor.name
        elif isinstance(current_ancestor, ast.ClassDef):
            enclosing_class_name = current_ancestor.name
            break
        current_ancestor = parent_by_child_id.get(id(current_ancestor))
    if enclosing_function_name is None:
        if enclosing_class_name is not None:
            return f"<class:{enclosing_class_name}>"
        return None
    if enclosing_class_name is not None:
        return f"{enclosing_class_name}.{enclosing_function_name}"
    return enclosing_function_name


def check_file_global_constants_use_count(content: str, file_path: str) -> list[str]:
    """Flag module-level UPPER_SNAKE constants referenced by only one function/method.

    Enforces the file-global-constants use-count rule: a constant used by just
    one caller belongs in that caller's scope. Test files, config files,
    workflow-registry files, and non-Python files are exempt. Constants with
    zero references are out of scope. The enforcer entry module
    (``hooks/blocking/code_rules_enforcer.py``) is exempt to avoid
    self-blocking.
    """
    if is_test_file(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path):
        return []
    if get_file_extension(file_path) not in ALL_PYTHON_EXTENSIONS:
        return []
    if file_path.replace("\\", "/").endswith("hooks/blocking/code_rules_enforcer.py"):
        return []

    try:
        module_tree = ast.parse(content)
    except SyntaxError:
        return []

    constants_by_name = _collect_module_level_upper_snake_constants(module_tree)
    if not constants_by_name:
        return []

    parent_by_child_id = _build_parent_map(module_tree)
    callers_by_constant: dict[str, set[str]] = {name: set() for name in constants_by_name}
    for each_node in ast.walk(module_tree):
        if not isinstance(each_node, ast.Name):
            continue
        if not isinstance(each_node.ctx, ast.Load):
            continue
        if each_node.id not in callers_by_constant:
            continue
        enclosing_qname = _resolve_enclosing_function_qname(each_node, parent_by_child_id)
        if enclosing_qname is None:
            callers_by_constant[each_node.id].add("<module-scope>")
        else:
            callers_by_constant[each_node.id].add(enclosing_qname)

    issues: list[str] = []
    for each_constant_name, each_line_number in sorted(constants_by_name.items(), key=lambda pair: pair[1]):
        caller_count = len(callers_by_constant[each_constant_name])
        if caller_count == 1:
            issues.append(
                f"Line {each_line_number}: File-global constant {each_constant_name} used by only 1 function/method - move to method scope or add a second caller"
            )

    return issues
