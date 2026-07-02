"""Constants-outside-config checks and the file-global constant use-count check.

Also carries check_config_duplicate_path_anchor, which flags a config module
that rebuilds a directory a sibling module in the same package already
anchors from its own location.
"""

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

from hooks_constants.blocking_check_limits import (  # noqa: E402
    MAX_CONFIG_DUPLICATE_PATH_ANCHOR_ISSUES,
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


def _references_dunder_file(node: ast.AST) -> bool:
    """Return True when the expression tree reads ``__file__``."""
    return any(
        isinstance(each_node, ast.Name) and each_node.id == "__file__"
        for each_node in ast.walk(node)
    )


def _file_anchor_up_count(node: ast.AST) -> Optional[int]:
    """Return how many directory levels a ``__file__`` anchor climbs, else None.

    A ``parents[N]`` subscript on a ``__file__``-rooted expression climbs
    ``N + 1`` levels; a chain of ``.parent`` attributes climbs one level per
    link. Any other expression returns None.
    """
    if isinstance(node, ast.Subscript):
        subscripted = node.value
        if (
            isinstance(subscripted, ast.Attribute)
            and subscripted.attr == "parents"
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, int)
            and _references_dunder_file(subscripted.value)
        ):
            return node.slice.value + 1
    parent_step_count = 0
    current_node = node
    while isinstance(current_node, ast.Attribute) and current_node.attr == "parent":
        parent_step_count += 1
        current_node = current_node.value
    if parent_step_count and _references_dunder_file(current_node):
        return parent_step_count
    return None


def _anchored_join_signature(node: ast.AST) -> Optional[tuple[int, str]]:
    """Return (up_count, first literal segment) for an anchored ``/`` join, else None.

    Flattens a left-leaning ``/`` chain, requires the left-most operand to be
    a ``__file__`` anchor, and requires the first joined segment to be a
    string literal.
    """
    if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
        return None
    all_segments: list[str] = []
    current_node: ast.expr = node
    while isinstance(current_node, ast.BinOp) and isinstance(current_node.op, ast.Div):
        right_operand = current_node.right
        if isinstance(right_operand, ast.Constant) and isinstance(right_operand.value, str):
            all_segments.insert(0, right_operand.value)
        else:
            all_segments.insert(0, "")
        current_node = current_node.left
    anchor_up_count = _file_anchor_up_count(current_node)
    if anchor_up_count is None or not all_segments or not all_segments[0]:
        return None
    return anchor_up_count, all_segments[0]


def _module_anchor_signatures(module_tree: ast.Module) -> dict[tuple[int, str], int]:
    """Return line numbers keyed by anchored-join signature for top-level assignments."""
    signatures_by_key: dict[tuple[int, str], int] = {}
    for each_statement in module_tree.body:
        if isinstance(each_statement, ast.Assign):
            assigned_expression = each_statement.value
        elif isinstance(each_statement, ast.AnnAssign) and each_statement.value is not None:
            assigned_expression = each_statement.value
        else:
            continue
        for each_node in ast.walk(assigned_expression):
            signature = _anchored_join_signature(each_node)
            if signature is not None:
                signatures_by_key.setdefault(signature, each_statement.lineno)
    return signatures_by_key


def check_config_duplicate_path_anchor(content: str, file_path: str) -> list[str]:
    """Flag a config module re-anchoring a path a sibling config module already builds.

    Two config modules in the same ``config/`` directory that each anchor
    ``Path(__file__)`` the same number of levels up and join the same first
    literal segment are two sources of truth for one directory: a rename in
    one module silently leaves the other pointing at the old folder. The
    check fires on a config-module write whose module-level assignment joins
    a ``__file__`` anchor (``parents[N]`` or a ``.parent`` chain) with a
    literal segment that a sibling module in the same directory also joins at
    the same depth. Compose one shared base constant and build the other path
    from it. Test files, non-Python files, and modules outside a config
    directory are exempt; an unreadable or unparseable sibling is skipped.

    Args:
        content: The Python source under validation.
        file_path: The destination path, used to locate sibling config modules.

    Returns:
        One issue line per duplicated anchor, capped at the configured maximum.
    """
    if not is_config_file(file_path):
        return []
    if is_test_file(file_path):
        return []
    if get_file_extension(file_path) not in ALL_PYTHON_EXTENSIONS:
        return []
    try:
        module_tree = ast.parse(content)
    except SyntaxError:
        return []
    written_signatures = _module_anchor_signatures(module_tree)
    if not written_signatures:
        return []
    config_directory = Path(file_path).parent
    if not config_directory.is_dir():
        return []
    owner_name_by_signature: dict[tuple[int, str], str] = {}
    written_name = Path(file_path).name
    for each_sibling_path in sorted(config_directory.glob("*.py")):
        if each_sibling_path.name == written_name or is_test_file(str(each_sibling_path)):
            continue
        try:
            sibling_tree = ast.parse(each_sibling_path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for each_signature in _module_anchor_signatures(sibling_tree):
            owner_name_by_signature.setdefault(each_signature, each_sibling_path.name)
    issues: list[str] = []
    for each_signature, each_line_number in sorted(written_signatures.items(), key=lambda pair: pair[1]):
        owner_name = owner_name_by_signature.get(each_signature)
        if owner_name is None:
            continue
        anchor_up_count, first_segment = each_signature
        issues.append(
            f"Line {each_line_number}: joins {first_segment} onto the same base, "
            f"{anchor_up_count} levels above this directory, that {owner_name} "
            "already builds - define the base once and compose both paths from it"
        )
        if len(issues) >= MAX_CONFIG_DUPLICATE_PATH_ANCHOR_ISSUES:
            break
    return issues
