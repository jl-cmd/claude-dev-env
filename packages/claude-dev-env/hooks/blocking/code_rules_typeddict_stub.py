"""TypedDict encode/decode pairing, stub-implementation, and thin-wrapper-module checks."""

import ast
import re
import sys
from pathlib import Path

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
    _statement_is_docstring,
    _walk_skipping_type_checking_blocks,
    is_hook_infrastructure,
    is_test_file,
)

from hooks_constants.blocking_check_limits import (  # noqa: E402
    MAX_STUB_IMPLEMENTATION_ISSUES,
    MAX_THIN_WRAPPER_ISSUES,
    MAX_TYPED_DICT_PAIR_ISSUES,
    MAX_ZERO_PAYLOAD_ALIAS_ISSUES,
)

def _pascal_to_snake_case(pascal_name: str) -> str:
    pascal_to_snake_word_boundary = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
    return pascal_to_snake_word_boundary.sub("_", pascal_name).lower()


def _class_inherits_from_typed_dict(class_node: ast.ClassDef) -> bool:
    for each_base in class_node.bases:
        if isinstance(each_base, ast.Name) and each_base.id == "TypedDict":
            return True
        if isinstance(each_base, ast.Attribute) and each_base.attr == "TypedDict":
            return True
    return False


def _collect_typed_dict_class_names(parsed_tree: ast.AST) -> list[tuple[str, int]]:
    typed_dict_entries: list[tuple[str, int]] = []
    for each_statement in parsed_tree.body:
        if isinstance(each_statement, ast.ClassDef) and _class_inherits_from_typed_dict(each_statement):
            typed_dict_entries.append((each_statement.name, each_statement.lineno))
    return typed_dict_entries


def _collect_module_function_names(parsed_tree: ast.AST) -> set[str]:
    module_function_names: set[str] = set()
    for each_statement in parsed_tree.body:
        if isinstance(each_statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            module_function_names.add(each_statement.name)
    return module_function_names


def _is_init_file(file_path: str) -> bool:
    return file_path.replace("\\", "/").rsplit("/", 1)[-1] == "__init__.py"


def _statement_is_dunder_all_assignment(statement_node: ast.stmt) -> bool:
    if isinstance(statement_node, ast.Assign):
        for each_target in statement_node.targets:
            if isinstance(each_target, ast.Name) and each_target.id == "__all__":
                return True
        return False
    if isinstance(statement_node, ast.AnnAssign):
        target = statement_node.target
        return isinstance(target, ast.Name) and target.id == "__all__"
    return False


def _statement_is_import_or_reexport(statement_node: ast.stmt) -> bool:
    if isinstance(statement_node, (ast.Import, ast.ImportFrom)):
        return True
    if _statement_is_dunder_all_assignment(statement_node):
        return True
    return False


def check_thin_wrapper_files(content: str, file_path: str) -> list[str]:
    """Flag non-`__init__.py` modules that are only imports + `__all__`.

    A re-export-only wrapper outside `__init__.py` forces callers through an
    indirection layer with no payload of its own. Callers should import from
    the real module. `__init__.py` is the canonical re-export surface and is
    exempt; test files, hook infrastructure, and `config/` are also exempt.
    """
    if (
        is_test_file(file_path)
        or is_hook_infrastructure(file_path)
        or is_config_file(file_path)
        or _is_init_file(file_path)
    ):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    body_statements = list(parsed_tree.body)
    if not body_statements:
        return []

    statements_after_docstring = (
        body_statements[1:]
        if _statement_is_docstring(body_statements[0])
        else body_statements
    )
    if not statements_after_docstring:
        return []

    for each_statement in statements_after_docstring:
        if not _statement_is_import_or_reexport(each_statement):
            return []

    issues = [
        f"Line 1: {file_path}: thin wrapper file — module body is only imports (optionally with __all__); "
        "callers should import from the real module instead of going through this indirection"
    ]
    return issues[:MAX_THIN_WRAPPER_ISSUES]


def _function_parameter_names_in_order(function_node: ast.FunctionDef) -> list[str]:
    arguments = function_node.args
    positional_arguments = [*arguments.posonlyargs, *arguments.args]
    return [each_argument.arg for each_argument in positional_arguments]


def _has_only_positional_parameters(function_node: ast.FunctionDef) -> bool:
    arguments = function_node.args
    return (
        not arguments.kwonlyargs
        and arguments.vararg is None
        and arguments.kwarg is None
    )


def _single_return_call(function_node: ast.FunctionDef) -> ast.Call | None:
    body_statements = function_node.body
    statements_after_docstring = (
        body_statements[1:]
        if body_statements and _statement_is_docstring(body_statements[0])
        else body_statements
    )
    if len(statements_after_docstring) != 1:
        return None
    only_statement = statements_after_docstring[0]
    if not isinstance(only_statement, ast.Return):
        return None
    return only_statement.value if isinstance(only_statement.value, ast.Call) else None


def _forwards_parameters_unchanged(call_node: ast.Call, all_parameter_names: list[str]) -> bool:
    if call_node.keywords:
        return False
    if len(call_node.args) != len(all_parameter_names):
        return False
    for each_argument, each_parameter_name in zip(call_node.args, all_parameter_names):
        if not isinstance(each_argument, ast.Name) or each_argument.id != each_parameter_name:
            return False
    return True


def _alias_target_name(call_node: ast.Call, all_sibling_function_names: set[str]) -> str:
    callee = call_node.func
    if not isinstance(callee, ast.Name):
        return ""
    return callee.id if callee.id in all_sibling_function_names else ""


def check_zero_payload_function_alias(content: str, file_path: str) -> list[str]:
    """Flag a module-level function that only forwards its parameters to a sibling.

    A function whose entire body (after an optional docstring) is a single
    `return sibling_function(first_param, second_param, ...)` that forwards its
    own parameters unchanged to another function defined in the same module is a
    second name for one behavior — indirection without payload, which CODE_RULES
    discourages. Callers should invoke the sibling directly.

    Hook infrastructure is intentionally NOT exempt — pass-through aliases inside
    hook modules are the motivating case. Test files and config files are exempt
    because re-binding aliases are legitimate scaffolding there.

    Args:
        content: The source under inspection.
        file_path: Path to the file, used for the test and config exemptions.

    Returns:
        One issue string per pass-through alias, capped at
        MAX_ZERO_PAYLOAD_ALIAS_ISSUES.
    """
    if is_test_file(file_path) or is_config_file(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    all_sibling_function_names = _collect_module_function_names(parsed_tree)
    issues: list[str] = []
    for each_statement in parsed_tree.body:
        if not isinstance(each_statement, ast.FunctionDef):
            continue
        if not _has_only_positional_parameters(each_statement):
            continue
        call_node = _single_return_call(each_statement)
        if call_node is None:
            continue
        target_name = _alias_target_name(call_node, all_sibling_function_names)
        if not target_name or target_name == each_statement.name:
            continue
        if not _forwards_parameters_unchanged(call_node, _function_parameter_names_in_order(each_statement)):
            continue
        issues.append(
            f"Line {each_statement.lineno}: {file_path}: zero-payload alias — "
            f"{each_statement.name} only forwards its parameters to {target_name}; "
            f"callers should call {target_name} directly (indirection without payload)"
        )
    return issues[:MAX_ZERO_PAYLOAD_ALIAS_ISSUES]


def check_typed_dict_encode_decode(content: str, file_path: str) -> list[str]:
    """Flag TypedDict declarations missing companion `_encode_*` / `_decode_*` functions."""
    if (
        is_test_file(file_path)
        or is_hook_infrastructure(file_path)
        or _is_init_file(file_path)
    ):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    typed_dict_entries = _collect_typed_dict_class_names(parsed_tree)
    if not typed_dict_entries:
        return []

    module_function_names = _collect_module_function_names(parsed_tree)

    issues: list[str] = []
    for each_typed_dict_name, each_typed_dict_line in typed_dict_entries:
        snake_name = _pascal_to_snake_case(each_typed_dict_name)
        encoder_function_name = f"_encode_{snake_name}"
        decoder_function_name = f"_decode_{snake_name}"
        is_encoder_present = encoder_function_name in module_function_names
        is_decoder_present = decoder_function_name in module_function_names
        if is_encoder_present and is_decoder_present:
            continue
        missing_companions: list[str] = []
        if not is_encoder_present:
            missing_companions.append(encoder_function_name)
        if not is_decoder_present:
            missing_companions.append(decoder_function_name)
        issues.append(
            f"Line {each_typed_dict_line}: TypedDict '{each_typed_dict_name}' missing companion "
            f"{' and '.join(missing_companions)} — add explicit encode/decode functions"
        )
        if len(issues) >= MAX_TYPED_DICT_PAIR_ISSUES:
            break

    return issues


def _function_decorator_is_abstractmethod(decorator_node: ast.expr) -> bool:
    if isinstance(decorator_node, ast.Name) and decorator_node.id == "abstractmethod":
        return True
    if isinstance(decorator_node, ast.Attribute) and decorator_node.attr == "abstractmethod":
        return True
    return False


def _function_is_abstract(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return any(
        _function_decorator_is_abstractmethod(each_decorator)
        for each_decorator in function_node.decorator_list
    )


def _function_is_overload(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for each_decorator in function_node.decorator_list:
        if isinstance(each_decorator, ast.Name) and each_decorator.id == "overload":
            return True
        if isinstance(each_decorator, ast.Attribute) and each_decorator.attr == "overload":
            return True
    return False


def _class_is_protocol(class_node: ast.ClassDef) -> bool:
    for each_base in class_node.bases:
        if isinstance(each_base, ast.Name) and each_base.id == "Protocol":
            return True
        if isinstance(each_base, ast.Attribute) and each_base.attr == "Protocol":
            return True
    return False


def _class_inherits_from_protocol_or_abc(class_node: ast.ClassDef) -> bool:
    for each_base in class_node.bases:
        if isinstance(each_base, ast.Name) and each_base.id in {"Protocol", "ABC"}:
            return True
        if isinstance(each_base, ast.Attribute) and each_base.attr in {"Protocol", "ABC"}:
            return True
    return False


def _statement_is_pass(statement_node: ast.stmt) -> bool:
    return isinstance(statement_node, ast.Pass)


def _statement_is_ellipsis(statement_node: ast.stmt) -> bool:
    return (
        isinstance(statement_node, ast.Expr)
        and isinstance(statement_node.value, ast.Constant)
        and statement_node.value.value is Ellipsis
    )


def _statement_is_raise_not_implemented(statement_node: ast.stmt) -> bool:
    if not isinstance(statement_node, ast.Raise):
        return False
    raised_expression = statement_node.exc
    if raised_expression is None:
        return False
    if isinstance(raised_expression, ast.Name) and raised_expression.id == "NotImplementedError":
        return True
    if (
        isinstance(raised_expression, ast.Call)
        and isinstance(raised_expression.func, ast.Name)
        and raised_expression.func.id == "NotImplementedError"
    ):
        return True
    return False


def _function_body_is_stub(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    body_statements = list(function_node.body)
    if body_statements and _statement_is_docstring(body_statements[0]):
        body_statements = body_statements[1:]
    if len(body_statements) != 1:
        return False
    sole_statement = body_statements[0]
    return (
        _statement_is_pass(sole_statement)
        or _statement_is_ellipsis(sole_statement)
        or _statement_is_raise_not_implemented(sole_statement)
    )


def check_stub_implementations(content: str, file_path: str) -> list[str]:
    """Flag production functions whose body is only pass/.../raise NotImplementedError.

    Stubs ship as placeholders that the rest of the system depends on but the
    function does not deliver. ABC/Protocol abstract methods are exempt — they
    are placeholders BY contract, not by oversight.
    """
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    abstract_class_function_ids: set[int] = set()
    for each_node in ast.walk(parsed_tree):
        if isinstance(each_node, ast.ClassDef) and _class_inherits_from_protocol_or_abc(each_node):
            is_protocol = _class_is_protocol(each_node)
            for each_class_member in each_node.body:
                if not isinstance(each_class_member, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if is_protocol or _function_is_abstract(each_class_member):
                    abstract_class_function_ids.add(id(each_class_member))

    stub_function_nodes: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _function_is_abstract(each_node) or _function_is_overload(each_node):
            continue
        if id(each_node) in abstract_class_function_ids:
            continue
        if _function_body_is_stub(each_node):
            stub_function_nodes.append(each_node)

    stub_function_nodes.sort(key=lambda each_function: each_function.lineno)

    issues: list[str] = []
    for each_function in stub_function_nodes:
        issues.append(
            f"Line {each_function.lineno}: Function '{each_function.name}' is a stub "
            "(pass/.../raise NotImplementedError) — implement or remove"
        )
        if len(issues) >= MAX_STUB_IMPLEMENTATION_ISSUES:
            break

    return issues
