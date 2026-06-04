"""Unused-optional-parameter and duplicated-format-pattern checks."""

import ast
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
    _extract_fstring_literal_parts,
    is_hook_infrastructure,
    is_migration_file,
    is_test_file,
    is_workflow_registry_file,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    DUPLICATED_FORMAT_MINIMUM_LITERAL_CHARACTER_COUNT,
    DUPLICATED_FORMAT_MINIMUM_REPETITION_COUNT,
)


def _collect_optional_param_defaults(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, ast.expr]:
    """Return mapping of param name to its default AST node for params with defaults."""
    arguments = function_node.args
    all_args = arguments.posonlyargs + arguments.args
    defaults_aligned = [None] * (len(all_args) - len(arguments.defaults)) + list(arguments.defaults)
    param_defaults: dict[str, ast.expr] = {}
    for each_arg, each_default in zip(all_args, defaults_aligned):
        if each_default is not None:
            param_defaults[each_arg.arg] = each_default
    for each_kwarg, each_kwdefault in zip(arguments.kwonlyargs, arguments.kw_defaults):
        if each_kwdefault is not None:
            param_defaults[each_kwarg.arg] = each_kwdefault
    return param_defaults


_NON_LITERAL_DEFAULT_SENTINEL = object()


def _is_non_literal_default(candidate_default: object) -> bool:
    """Return True when a value is the sentinel for a non-literal default."""
    return candidate_default is _NON_LITERAL_DEFAULT_SENTINEL


def _ast_constant_value(node: ast.expr) -> object:
    """Return the Python value of a Constant node, or a stable sentinel for non-constants.

    Non-literal defaults (e.g. DEFAULT_TIMEOUT) return a single shared sentinel
    so that the unused-optional check can identify and skip them rather than
    treating every non-literal as automatically different.
    """
    if isinstance(node, ast.Constant):
        return node.value
    return _NON_LITERAL_DEFAULT_SENTINEL


def _call_passes_keyword_argument_differing_from_default(
    call_node: ast.Call,
    param_name: str,
    default_value: object,
) -> bool:
    """Return True when a Call passes param_name with a value different from default.

    Returns True conservatively when **kwargs expansion is present, because the
    expansion may pass the parameter with an unknown value — treating it as
    indeterminate prevents false positives from the unused-optional check.
    """
    for each_keyword in call_node.keywords:
        if each_keyword.arg is None:
            return True
        if each_keyword.arg == param_name:
            passed_value = _ast_constant_value(each_keyword.value)
            return passed_value != default_value
    return False


def _call_has_kwargs_expansion(call_node: ast.Call) -> bool:
    """Return True when a Call contains a **kwargs expansion (arg=None in AST keywords)."""
    return any(each_keyword.arg is None for each_keyword in call_node.keywords)


def _call_has_starargs_expansion(call_node: ast.Call) -> bool:
    """Return True when a Call contains a *args expansion (Starred node in positional args)."""
    return any(isinstance(each_arg, ast.Starred) for each_arg in call_node.args)


def _call_passes_positional_argument_for_param(
    call_node: ast.Call,
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    param_name: str,
    default_value: object,
) -> bool:
    """Return True when a Call passes param_name positionally with a varied value.

    Returns False when **kwargs expansion is present (the keyword helper covers
    that case). Returns True conservatively when *args expansion is present,
    because the expanded iterable may provide the parameter at runtime.
    """
    if _call_has_kwargs_expansion(call_node):
        return False
    if _call_has_starargs_expansion(call_node):
        return True
    all_args = function_node.args.posonlyargs + function_node.args.args
    try:
        param_index = next(
            each_index
            for each_index, each_arg in enumerate(all_args)
            if each_arg.arg == param_name
        )
    except StopIteration:
        return False
    if param_index >= len(call_node.args):
        return False
    passed_value = _ast_constant_value(call_node.args[param_index])
    return passed_value != default_value


def _function_name_from_call(call_node: ast.Call) -> str | None:
    """Return the function name for direct calls only, or None.

    Only direct calls (ast.Name) are matched as same-file call sites.
    Attribute calls like obj.foo() are not counted because the receiver
    object may not be the same file's definition — returning the attr name
    would cause false positives against any local function sharing that name.
    """
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id
    return None


def check_unused_optional_parameters(content: str, file_path: str) -> list[str]:
    """Flag optional parameters never varied at same-file call sites.

    A parameter with a default value that every same-file caller either omits
    or always passes with the identical default literal is never varied and
    should be inlined or dropped per the YAGNI API surface rule.

    Skips test files, config files, workflow registry files, migration files,
    and hook infrastructure files.  Only checks functions that have at least
    one same-file call site.

    Scope limit (v1): only module-level functions are analyzed. Methods defined
    inside a ClassDef are skipped because the positional-index calculation would
    need to account for the implicit self/cls parameter, which is absent at
    call sites using attribute access (obj.method(...)). Method analysis is out
    of scope for this version.
    """
    if is_test_file(file_path):
        return []
    if is_config_file(file_path):
        return []
    if is_workflow_registry_file(file_path):
        return []
    if is_migration_file(file_path):
        return []
    if is_hook_infrastructure(file_path):
        return []

    try:
        module_tree = ast.parse(content)
    except SyntaxError:
        return []

    all_function_nodes: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for each_node in module_tree.body:
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            all_function_nodes[each_node.name] = each_node

    all_call_nodes: list[ast.Call] = [
        each_node
        for each_node in ast.walk(module_tree)
        if isinstance(each_node, ast.Call)
    ]

    issues: list[str] = []
    for each_function_name, each_function_node in all_function_nodes.items():
        param_defaults = _collect_optional_param_defaults(each_function_node)
        if not param_defaults:
            continue

        same_file_calls = [
            each_call
            for each_call in all_call_nodes
            if _function_name_from_call(each_call) == each_function_name
        ]
        if not same_file_calls:
            continue

        for each_param_name, each_default_node in param_defaults.items():
            default_value = _ast_constant_value(each_default_node)
            if _is_non_literal_default(default_value):
                continue
            is_param_varied = any(
                _call_passes_keyword_argument_differing_from_default(
                    each_call, each_param_name, default_value
                )
                or _call_passes_positional_argument_for_param(
                    each_call, each_function_node, each_param_name, default_value
                )
                for each_call in same_file_calls
            )
            if not is_param_varied:
                issues.append(
                    f"Line {each_function_node.lineno}: optional parameter {each_param_name}"
                    f" is never varied — inline default or drop"
                )

    return issues


def _build_fstring_skeleton(joined_str_node: ast.JoinedStr) -> str:
    """Collapse interpolations in an f-string to a placeholder to form a pattern skeleton.

    Injects the skeleton placeholder directly via _extract_fstring_literal_parts
    instead of post-processing, so literal text in the source that happens to
    contain the default placeholder (or any other substring) is preserved
    verbatim and cannot collide with interpolation slots.
    """
    skeleton_interpolation_placeholder = "<x>"
    _display_body, shape_body = _extract_fstring_literal_parts(
        joined_str_node,
        interpolation_placeholder=skeleton_interpolation_placeholder,
    )
    return shape_body


def check_duplicated_format_patterns(content: str, file_path: str) -> None:
    """Emit stderr advisories when an f-string skeleton repeats in a production file.

    Collapses each f-string's interpolations to '<x>' placeholders, then counts
    skeleton occurrences per file. When any skeleton appears three or more times,
    it suggests the pattern belongs in a helper or model method.

    This is advisory-only (no return value, no blocking). Skips test files,
    config files, workflow registry files, migration files, and hook infrastructure.
    """
    if is_test_file(file_path):
        return
    if is_config_file(file_path):
        return
    if is_workflow_registry_file(file_path):
        return
    if is_migration_file(file_path):
        return
    if is_hook_infrastructure(file_path):
        return

    try:
        module_tree = ast.parse(content)
    except SyntaxError:
        return

    minimum_repetition_count = DUPLICATED_FORMAT_MINIMUM_REPETITION_COUNT
    minimum_literal_character_count = DUPLICATED_FORMAT_MINIMUM_LITERAL_CHARACTER_COUNT

    skeleton_occurrences: dict[str, list[int]] = {}
    literal_length_by_skeleton: dict[str, int] = {}
    for each_node in ast.walk(module_tree):
        if not isinstance(each_node, ast.JoinedStr):
            continue
        skeleton = _build_fstring_skeleton(each_node)
        literal_body, _shape_body = _extract_fstring_literal_parts(each_node)
        if skeleton not in skeleton_occurrences:
            skeleton_occurrences[skeleton] = []
            literal_length_by_skeleton[skeleton] = len(literal_body)
        skeleton_occurrences[skeleton].append(each_node.lineno)

    for each_skeleton, each_line_numbers in skeleton_occurrences.items():
        if len(each_line_numbers) < minimum_repetition_count:
            continue
        if literal_length_by_skeleton[each_skeleton] < minimum_literal_character_count:
            continue
        print(
            f"[CODE_RULES advisory] f-string pattern {each_skeleton!r} appears"
            f" {len(each_line_numbers)} times — consider encapsulating in a helper or model.",
            file=sys.stderr,
        )
