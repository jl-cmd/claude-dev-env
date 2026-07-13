"""Content analysis for the TDD-enforcer constants and import-only exemptions.

Answers two questions about a payload: is the written module only module-level
constants (no behavior to test), and does an Edit or MultiEdit merely remove or
reorder imports on a file that already has no behavior worth a fresh test.
"""

import ast
from collections import Counter


def _constants_only_allowed_node_types() -> tuple[type, ...]:
    return (ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign)


def _is_module_docstring_expression(module_level_node: ast.stmt) -> bool:
    if not isinstance(module_level_node, ast.Expr):
        return False
    expression_value = module_level_node.value
    if not isinstance(expression_value, ast.Constant):
        return False
    return isinstance(expression_value.value, str)


def _safe_constant_functions() -> frozenset[str]:
    return frozenset({"Path", "frozenset"})


def _safe_constant_attribute_calls() -> frozenset[tuple[str, str]]:
    return frozenset({("re", "compile")})


def _node_is_unsafe_construct(subnode: ast.AST) -> bool:
    return isinstance(
        subnode,
        (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp, ast.Lambda),
    )


def _attribute_call_is_unsafe(function_node: ast.Attribute) -> bool:
    if not isinstance(function_node.value, ast.Name):
        return True
    pair = (function_node.value.id, function_node.attr)
    return pair not in _safe_constant_attribute_calls()


def _call_is_unsafe(call_node: ast.Call) -> bool:
    function_node = call_node.func
    if isinstance(function_node, ast.Name):
        return function_node.id not in _safe_constant_functions()
    if isinstance(function_node, ast.Attribute):
        return _attribute_call_is_unsafe(function_node)
    return True


def _rhs_has_unsafe_call(rhs_node: ast.AST) -> bool:
    """Return True when a constant's value contains a non-allowlisted call.

    Safe calls are value constructors (``Path(...)``, ``re.compile(...)``) that
    build objects without side effects; any other call or a comprehension reads
    as import-time behavior.

    Args:
        rhs_node: The assignment's right-hand-side expression node.

    Returns:
        True when an unsafe call or comprehension appears anywhere within it.
    """
    for each_subnode in ast.walk(rhs_node):
        if isinstance(each_subnode, ast.Call) and _call_is_unsafe(each_subnode):
            return True
        if _node_is_unsafe_construct(each_subnode):
            return True
    return False


def _assignment_rhs_is_safe(node: ast.stmt) -> bool:
    right_hand_side = getattr(node, "value", None)
    if right_hand_side is None:
        return True
    return not _rhs_has_unsafe_call(right_hand_side)


def _top_level_node_is_constant(node: ast.stmt) -> bool:
    if isinstance(node, (ast.Assign, ast.AnnAssign)):
        return _assignment_rhs_is_safe(node)
    if isinstance(node, _constants_only_allowed_node_types()):
        return True
    return _is_module_docstring_expression(node)


def _is_constants_only_python_content(content: str) -> bool:
    """Return whether module source declares only constants, imports, docstring.

    Args:
        content: Python source text.

    Returns:
        True when every top-level statement is an import, a safe constant
        assignment, or the module docstring; False on empty or unparseable
        content, or any statement that carries behavior.
    """
    if not content.strip():
        return False
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return False
    if not parsed_tree.body:
        return False
    return all(_top_level_node_is_constant(each_node) for each_node in parsed_tree.body)


def _apply_edit_to_content(
    existing_content: str, old_str: str, new_str: str, should_replace_all: bool
) -> str:
    if should_replace_all:
        return existing_content.replace(old_str, new_str)
    return existing_content.replace(old_str, new_str, 1)


def _future_module_name() -> str:
    return "__future__"


def _is_future_import(node: ast.stmt) -> bool:
    return isinstance(node, ast.ImportFrom) and node.module == _future_module_name()


def _is_removable_import(node: ast.stmt) -> bool:
    if isinstance(node, ast.Import):
        return True
    if isinstance(node, ast.ImportFrom):
        return not _is_future_import(node)
    return False


def _future_import_signatures(content: str) -> list[str] | None:
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return None
    return [ast.dump(each_node) for each_node in parsed_tree.body if _is_future_import(each_node)]


def _top_level_signatures(content: str) -> tuple[list[str], list[str]] | None:
    """Split top-level statements into removable-import and other signatures.

    ``from __future__`` imports and every non-import statement land in the
    second list, so editing a future import reads as a behavior edit rather than
    a removable-import edit. Signatures omit line and column attributes.

    Args:
        content: Python source text.

    Returns:
        A pair ``(import_signatures, other_signatures)`` in source order, or
        None when the content does not parse.
    """
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return None
    import_signatures: list[str] = []
    non_import_signatures: list[str] = []
    for each_node in parsed_tree.body:
        if _is_removable_import(each_node):
            import_signatures.append(ast.dump(each_node))
        else:
            non_import_signatures.append(ast.dump(each_node))
    return import_signatures, non_import_signatures


def _post_edit_content_for_edit(existing_content: str, tool_input: dict) -> str | None:
    old_str = tool_input.get("old_string", "") or ""
    new_str = tool_input.get("new_string", "") or ""
    if not old_str:
        return None
    should_replace_all = bool(tool_input.get("replace_all", False))
    return _apply_edit_to_content(existing_content, old_str, new_str, should_replace_all)


def _post_edit_content_for_multiedit(existing_content: str, tool_input: dict) -> str | None:
    all_edits = tool_input.get("edits", []) or []
    post_edit_content = existing_content
    for each_edit in all_edits:
        if not isinstance(each_edit, dict):
            return None
        each_old = each_edit.get("old_string", "") or ""
        each_new = each_edit.get("new_string", "") or ""
        if not each_old:
            return None
        should_replace_all = bool(each_edit.get("replace_all", False))
        post_edit_content = _apply_edit_to_content(
            post_edit_content, each_old, each_new, should_replace_all
        )
    return post_edit_content


def _compute_post_edit_content(
    existing_content: str, tool_name: str, tool_input: dict
) -> str | None:
    if tool_name == "Edit":
        return _post_edit_content_for_edit(existing_content, tool_input)
    if tool_name == "MultiEdit":
        return _post_edit_content_for_multiedit(existing_content, tool_input)
    return None


def _is_post_edit_constants_only(existing_content: str, tool_name: str, tool_input: dict) -> bool:
    """Return whether an Edit or MultiEdit keeps a constants-only file so.

    Both the existing content and the post-edit result must be constants-only,
    and the ``from __future__`` imports must be unchanged, so a future-import
    edit faces the gate rather than slipping through this exemption.

    Args:
        existing_content: Current file text.
        tool_name: The intercepted tool (Edit or MultiEdit).
        tool_input: The intercepted tool's input payload.

    Returns:
        True when the file was and stays constants-only across the edit.
    """
    if not _is_constants_only_python_content(existing_content):
        return False
    post_edit_content = _compute_post_edit_content(existing_content, tool_name, tool_input)
    if post_edit_content is None:
        return False
    if _future_import_signatures(existing_content) != _future_import_signatures(post_edit_content):
        return False
    return _is_constants_only_python_content(post_edit_content)


def _import_signatures_are_reorder_or_removal(
    all_existing_signatures: tuple[list[str], list[str]],
    all_post_edit_signatures: tuple[list[str], list[str]],
) -> bool:
    existing_imports, existing_rest = all_existing_signatures
    post_imports, post_rest = all_post_edit_signatures
    if post_rest != existing_rest or post_imports == existing_imports:
        return False
    return Counter(post_imports) <= Counter(existing_imports)


def _is_post_edit_import_only(existing_content: str, tool_name: str, tool_input: dict) -> bool:
    """Return whether an Edit or MultiEdit only removes or reorders imports.

    Args:
        existing_content: Current file text.
        tool_name: The intercepted tool (Edit or MultiEdit).
        tool_input: The intercepted tool's input payload.

    Returns:
        True when the edit is a pure reordering or removal of imports.
    """
    existing_signatures = _top_level_signatures(existing_content)
    if existing_signatures is None:
        return False
    if tool_name == "MultiEdit" and not (tool_input.get("edits") or []):
        return False
    post_edit_content = _compute_post_edit_content(existing_content, tool_name, tool_input)
    if post_edit_content is None:
        return False
    post_edit_signatures = _top_level_signatures(post_edit_content)
    if post_edit_signatures is None:
        return False
    return _import_signatures_are_reorder_or_removal(existing_signatures, post_edit_signatures)
