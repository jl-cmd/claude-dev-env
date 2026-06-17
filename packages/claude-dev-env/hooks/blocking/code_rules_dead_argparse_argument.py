"""Dead argparse-argument check: an optional CLI flag whose value is never read."""

import ast
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_shared import (  # noqa: E402
    is_migration_file,
    is_test_file,
)

from hooks_constants.dead_argparse_argument_constants import (  # noqa: E402
    ACTION_KEYWORD_NAME,
    ADD_ARGUMENT_METHOD_NAME,
    ALL_PARSE_METHOD_NAMES,
    ALL_SUPPRESSED_ACTION_NAMES,
    ATTRGETTER_FUNCTION_NAME,
    DEAD_ARGPARSE_ARGUMENT_GUIDANCE,
    DEST_KEYWORD_NAME,
    DEST_WORD_JOINER,
    DEST_WORD_SEPARATOR,
    EXPORTED_NAMES_ATTRIBUTE,
    GETATTR_FUNCTION_NAME,
    GETATTR_NAME_ARGUMENT_MINIMUM,
    LONG_OPTION_PREFIX,
    MAX_DEAD_ARGPARSE_ARGUMENT_ISSUES,
    NAMESPACE_DICT_ATTRIBUTE_NAME,
    OPTION_PREFIX,
    VARS_FUNCTION_NAME,
)


def _string_constant_literal(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _keyword_string_literal(call_node: ast.Call, keyword_name: str) -> str | None:
    """Return the string literal of a keyword argument, or None when absent."""
    for each_keyword in call_node.keywords:
        if each_keyword.arg == keyword_name:
            return _string_constant_literal(each_keyword.value)
    return None


def _option_string_arguments(call_node: ast.Call) -> list[str]:
    """Return the leading positional string-literal arguments of an add_argument call."""
    option_strings: list[str] = []
    for each_argument in call_node.args:
        literal_value = _string_constant_literal(each_argument)
        if literal_value is None:
            break
        option_strings.append(literal_value)
    return option_strings


def _dest_from_option_string(option_string: str) -> str:
    return option_string.lstrip(OPTION_PREFIX).replace(DEST_WORD_SEPARATOR, DEST_WORD_JOINER)


def _argument_dest_name(call_node: ast.Call) -> str | None:
    """Return the dest name an optional add_argument call declares, or None.

    A ``dest="name"`` keyword wins outright. Otherwise the dest derives from the
    first long option (``--repo`` -> ``repo``, ``--dry-run`` -> ``dry_run``) and
    falls back to the first short option when no long option is present. A bare
    positional argument (no leading dash) is a required positional, never an
    optional flag, and yields None so the caller skips it.
    """
    explicit_dest = _keyword_string_literal(call_node, DEST_KEYWORD_NAME)
    if explicit_dest is not None:
        return explicit_dest
    option_strings = _option_string_arguments(call_node)
    if not option_strings:
        return None
    if not option_strings[0].startswith(OPTION_PREFIX):
        return None
    for each_option in option_strings:
        if each_option.startswith(LONG_OPTION_PREFIX):
            return _dest_from_option_string(each_option)
    return _dest_from_option_string(option_strings[0])


def _has_suppressed_action(call_node: ast.Call) -> bool:
    action_name = _keyword_string_literal(call_node, ACTION_KEYWORD_NAME)
    return action_name in ALL_SUPPRESSED_ACTION_NAMES


def _is_add_argument_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == ADD_ARGUMENT_METHOD_NAME
    )


def _argument_dest_definitions(tree: ast.Module) -> list[tuple[str, int]]:
    """Return (dest_name, line) for each optional add_argument call in the module.

    Positional arguments (a bare name with no leading dash) and the argparse
    auto-actions ``help`` and ``version`` are excluded, since their parsed value
    is never a meaningful readable dest.
    """
    dest_definitions: list[tuple[str, int]] = []
    for each_node in ast.walk(tree):
        if not _is_add_argument_call(each_node):
            continue
        assert isinstance(each_node, ast.Call)
        if _has_suppressed_action(each_node):
            continue
        dest_name = _argument_dest_name(each_node)
        if dest_name is None:
            continue
        dest_definitions.append((dest_name, each_node.lineno))
    return dest_definitions


def _attribute_read_names(tree: ast.Module) -> set[str]:
    """Return every attribute name read or augmented-assigned in the module.

    A read in Load context (``parsed_args.repo``) names the attribute, and an
    augmented assignment (``parsed_args.count += 1``) reads the attribute before
    writing it, so both count as a read of the dest name.
    """
    read_names: set[str] = set()
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.Attribute) and isinstance(each_node.ctx, ast.Load):
            read_names.add(each_node.attr)
        if isinstance(each_node, ast.AugAssign) and isinstance(each_node.target, ast.Attribute):
            read_names.add(each_node.target.attr)
    return read_names


def _dynamic_read_names(tree: ast.Module) -> set[str]:
    """Return literal attribute names read via ``getattr`` and ``attrgetter``.

    ``getattr(namespace, "repo")`` names its attribute in the second positional
    argument, while ``attrgetter("a", "b")`` names one attribute per positional
    argument; each literal string contributes a read name.
    """
    literal_names: set[str] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Call):
            continue
        function_name = None
        if isinstance(each_node.func, ast.Name):
            function_name = each_node.func.id
        elif isinstance(each_node.func, ast.Attribute):
            function_name = each_node.func.attr
        if function_name == GETATTR_FUNCTION_NAME:
            if len(each_node.args) >= GETATTR_NAME_ARGUMENT_MINIMUM:
                literal_name = _string_constant_literal(each_node.args[1])
                if literal_name is not None:
                    literal_names.add(literal_name)
        elif function_name == ATTRGETTER_FUNCTION_NAME:
            for each_argument in each_node.args:
                literal_name = _string_constant_literal(each_argument)
                if literal_name is not None:
                    literal_names.add(literal_name)
    return literal_names


def _exported_names(tree: ast.Module) -> set[str]:
    """Return names listed in a module-level ``__all__`` literal."""
    exported: set[str] = set()
    for each_node in tree.body:
        if not isinstance(each_node, ast.Assign):
            continue
        targets_all = any(
            isinstance(each_target, ast.Name) and each_target.id == EXPORTED_NAMES_ATTRIBUTE
            for each_target in each_node.targets
        )
        if not targets_all:
            continue
        if isinstance(each_node.value, (ast.List, ast.Tuple, ast.Set)):
            for each_element in each_node.value.elts:
                literal_name = _string_constant_literal(each_element)
                if literal_name is not None:
                    exported.add(literal_name)
    return exported


def _target_namespace_names(assign_target: ast.expr) -> set[str]:
    """Return names an assignment target binds the namespace to.

    A bare ``ast.Name`` target (``parsed = parse_args()``) binds one namespace
    name. A tuple- or list-unpack target (``parsed, remaining =
    parse_known_args()``) binds the namespace to its first ``ast.Name`` element,
    matching the documented ``(namespace, remaining)`` return shape.
    """
    if isinstance(assign_target, ast.Name):
        return {assign_target.id}
    if isinstance(assign_target, (ast.Tuple, ast.List)):
        for each_element in assign_target.elts:
            if isinstance(each_element, ast.Name):
                return {each_element.id}
    return set()


def _parse_call_namespace_names(tree: ast.Module) -> set[str]:
    """Return names bound directly to a ``parse_args``/``parse_known_args`` result."""
    parse_call_names: set[str] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Assign):
            continue
        if not isinstance(each_node.value, ast.Call):
            continue
        function_node = each_node.value.func
        if not isinstance(function_node, ast.Attribute):
            continue
        if function_node.attr not in ALL_PARSE_METHOD_NAMES:
            continue
        for each_target in each_node.targets:
            parse_call_names |= _target_namespace_names(each_target)
    return parse_call_names


def _alias_namespace_names(tree: ast.Module, all_parse_call_names: set[str]) -> set[str]:
    """Return names bound by re-assigning an existing namespace variable.

    A simple ``alias = parsed_arguments`` re-binding aliases the namespace, and a
    chain (``second = alias``) aliases it again, so the set grows to a fixed point
    before it is returned.
    """
    all_namespace_names = set(all_parse_call_names)
    keeps_growing = True
    while keeps_growing:
        keeps_growing = False
        for each_node in ast.walk(tree):
            if not isinstance(each_node, ast.Assign):
                continue
            if not isinstance(each_node.value, ast.Name):
                continue
            if each_node.value.id not in all_namespace_names:
                continue
            for each_target in each_node.targets:
                if isinstance(each_target, ast.Name) and each_target.id not in all_namespace_names:
                    all_namespace_names.add(each_target.id)
                    keeps_growing = True
    return all_namespace_names


def _namespace_variable_names(tree: ast.Module) -> set[str]:
    """Return names bound to a ``parse_args``/``parse_known_args`` result or its alias.

    A direct binding (``parsed = parse_args()``), the first element of a
    tuple-unpack of the documented ``(namespace, remaining)`` return
    (``parsed, remaining = parse_known_args()``), and a simple re-binding chain
    (``alias = parsed``) each name the same namespace.
    """
    parse_call_names = _parse_call_namespace_names(tree)
    return _alias_namespace_names(tree, parse_call_names)


def _namespace_escapes(tree: ast.Module, all_namespace_names: set[str]) -> bool:
    """Return whether a namespace variable is consumed in a way that hides reads.

    A namespace whose attributes the static scan cannot see makes any single dest
    unprovably dead, so the check suppresses. Each of the following is such an
    escape: a namespace forwarded as a bare argument to a call, double-star
    unpacked, passed to ``vars``, or read through ``__dict__``; a namespace Name
    nested anywhere inside a call's argument subtrees (for example inside a
    container literal), unless it is only the value of an attribute read; a
    ``parse_args``/``parse_known_args`` result bound to an attribute- or
    subscript-target the scan cannot track; and a ``parse_args``/``parse_known_args``
    bound method referenced as an aliased value rather than called inline.
    """
    if _parse_method_is_aliased(tree):
        return True
    if _parse_result_binds_untracked_target(tree):
        return True
    for each_node in ast.walk(tree):
        if (
            isinstance(each_node, ast.Attribute)
            and each_node.attr == NAMESPACE_DICT_ATTRIBUTE_NAME
            and isinstance(each_node.value, ast.Name)
            and each_node.value.id in all_namespace_names
        ):
            return True
        if isinstance(each_node, ast.Starred) and _references_namespace(
            each_node.value, all_namespace_names
        ):
            return True
        if isinstance(each_node, ast.Call) and _call_forwards_namespace(each_node, all_namespace_names):
            return True
    return False


def _references_namespace(node: ast.expr, all_namespace_names: set[str]) -> bool:
    return isinstance(node, ast.Name) and node.id in all_namespace_names


def _argument_subtree_forwards_namespace(
    argument_node: ast.expr, all_namespace_names: set[str]
) -> bool:
    """Return whether a namespace Name appears anywhere inside an argument subtree.

    A namespace nested inside a container literal (``run({'args': namespace})``)
    forwards the whole namespace object, so its attributes escape static view. A
    Name that is only the ``.value`` of an ``ast.Attribute`` (``namespace.repo``)
    is a per-attribute read, not a forward of the namespace object, and is skipped
    so true-positive detection of a single dead dest survives.
    """
    all_attribute_value_name_ids = {
        id(each_descendant.value)
        for each_descendant in ast.walk(argument_node)
        if isinstance(each_descendant, ast.Attribute)
    }
    for each_descendant in ast.walk(argument_node):
        if not isinstance(each_descendant, ast.Name):
            continue
        if each_descendant.id not in all_namespace_names:
            continue
        if id(each_descendant) in all_attribute_value_name_ids:
            continue
        return True
    return False


def _call_forwards_namespace(call_node: ast.Call, all_namespace_names: set[str]) -> bool:
    """Return whether a call forwards a namespace as a bare argument or into ``vars``.

    A namespace passed as a direct bare positional argument, or nested anywhere
    inside a positional argument subtree (for example inside a container literal),
    forwards the namespace object. A ``vars`` call forwards through its positional
    argument only, so its keyword arguments are not inspected; for every other call
    a namespace nested in a keyword-argument subtree forwards it as well.
    """
    function_node = call_node.func
    is_vars_call = isinstance(function_node, ast.Name) and function_node.id == VARS_FUNCTION_NAME
    for each_argument in call_node.args:
        if _argument_subtree_forwards_namespace(each_argument, all_namespace_names):
            return True
    if is_vars_call:
        return False
    for each_keyword in call_node.keywords:
        if _argument_subtree_forwards_namespace(each_keyword.value, all_namespace_names):
            return True
    return False


def _parse_method_is_aliased(tree: ast.Module) -> bool:
    """Return whether a ``parse_args``/``parse_known_args`` method is referenced uncalled.

    The bound method is aliased when its attribute (``parser.parse_args``) appears
    as a value rather than as the ``func`` of an enclosing call — assigned to a
    name or passed around — so the resulting namespace is produced by a call the
    scan cannot follow back to ``parse_args``.
    """
    all_called_function_ids = {
        id(each_node.func) for each_node in ast.walk(tree) if isinstance(each_node, ast.Call)
    }
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Attribute):
            continue
        if each_node.attr not in ALL_PARSE_METHOD_NAMES:
            continue
        if id(each_node) not in all_called_function_ids:
            return True
    return False


def _parse_result_binds_untracked_target(tree: ast.Module) -> bool:
    """Return whether a parse-method result binds to a target the scan cannot track.

    A ``parse_args``/``parse_known_args`` result assigned to a plain ``ast.Name``
    target, or to a tuple/list whose first element is a plain ``ast.Name``, is
    tracked as a namespace variable. A result assigned to an attribute target
    (``self.args``) or a subscript target binds the namespace where the scan
    cannot follow its attribute reads, so it escapes.
    """
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Assign):
            continue
        if not isinstance(each_node.value, ast.Call):
            continue
        function_node = each_node.value.func
        if not isinstance(function_node, ast.Attribute):
            continue
        if function_node.attr not in ALL_PARSE_METHOD_NAMES:
            continue
        for each_target in each_node.targets:
            if not _target_namespace_names(each_target):
                return True
    return False


def check_dead_argparse_arguments(
    content: str, file_path: str, full_file_content: str | None = None
) -> list[str]:
    """Flag an optional argparse flag whose parsed value the same file never reads.

    An optional ``add_argument("--flag", ...)`` is dead when its dest name never
    appears as an attribute read, an augmented-assignment target, or a literal
    ``getattr``/``attrgetter`` access anywhere in the file, the name is not listed
    in a module-level ``__all__``, and no parsed namespace escapes static view.
    A namespace escapes by being forwarded as a bare call argument, double-star
    unpacked, passed to ``vars``, read through ``__dict__``, nested anywhere inside
    a call's argument subtrees (for example inside a container literal), bound to
    an attribute- or subscript-target the scan cannot track, or produced by a
    ``parse_args``/``parse_known_args`` bound method referenced as an aliased value
    rather than called inline. Positional arguments and the argparse
    ``help``/``version`` auto-actions are never flagged. Whole-file analysis runs
    against ``full_file_content`` when supplied so an Edit fragment is judged
    against the reconstructed post-edit file.

    Args:
        content: The new content under validation (Edit fragment or whole file).
        file_path: The destination path, used for the test/migration exemptions.
        full_file_content: The reconstructed post-edit whole-file content for an
            Edit, or None for a Write where ``content`` is already the whole file.

    Returns:
        One violation message per dead optional argument, capped at the configured
        maximum.
    """
    if is_test_file(file_path):
        return []
    if is_migration_file(file_path):
        return []
    effective_content = content if full_file_content is None else full_file_content
    try:
        tree = ast.parse(effective_content)
    except SyntaxError:
        return []
    dest_definitions = _argument_dest_definitions(tree)
    if not dest_definitions:
        return []
    all_namespace_names = _namespace_variable_names(tree)
    if _namespace_escapes(tree, all_namespace_names):
        return []
    read_names = _attribute_read_names(tree) | _dynamic_read_names(tree) | _exported_names(tree)
    issues: list[str] = []
    for each_dest_definition in dest_definitions:
        dest_name, dest_line = each_dest_definition
        if dest_name in read_names:
            continue
        issues.append(
            f"Line {dest_line}: CLI argument {dest_name!r} - {DEAD_ARGPARSE_ARGUMENT_GUIDANCE}"
        )
        if len(issues) >= MAX_DEAD_ARGPARSE_ARGUMENT_ISSUES:
            return issues
    return issues
