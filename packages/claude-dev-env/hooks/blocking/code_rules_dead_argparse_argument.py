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
    NAMESPACE_KEYWORD_NAME,
    OPTION_PREFIX,
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


def _keyword_value_node(call_node: ast.Call, keyword_name: str) -> ast.expr | None:
    """Return the value node of a keyword argument, or None when absent."""
    for each_keyword in call_node.keywords:
        if each_keyword.arg == keyword_name:
            return each_keyword.value
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


def _has_keyword_argument(call_node: ast.Call, keyword_name: str) -> bool:
    """Return whether the call passes a keyword argument with the given name."""
    return any(each_keyword.arg == keyword_name for each_keyword in call_node.keywords)


def _argument_dest_name(call_node: ast.Call) -> str | None:
    """Return the dest name an optional add_argument call declares, or None.

    A ``dest=`` keyword determines the dest outright: a string-literal value
    (``dest="name"``) names it, while a non-literal ``dest=`` (a variable or
    expression whose value the static scan cannot resolve) makes the real dest
    unknowable, so the argument is skipped (None). Without a ``dest=`` keyword the
    dest derives from the first long option (``--repo`` -> ``repo``, ``--dry-run``
    -> ``dry_run``) and falls back to the first short option when no long option
    is present. A bare positional argument (no leading dash) is a required
    positional, never an optional flag, and yields None so the caller skips it.
    """
    if _has_keyword_argument(call_node, DEST_KEYWORD_NAME):
        return _keyword_string_literal(call_node, DEST_KEYWORD_NAME)
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


def _namespace_keyword_argument_names(tree: ast.Module) -> set[str]:
    """Return names passed as the ``namespace=`` keyword to a parse-method call.

    ``parser.parse_args(namespace=options)`` populates the pre-existing
    ``options`` object, so its attribute reads name dests even though the parse
    result is never bound; the keyword's ``ast.Name`` value names that namespace.
    """
    keyword_names: set[str] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Call):
            continue
        function_node = each_node.func
        if not isinstance(function_node, ast.Attribute):
            continue
        if function_node.attr not in ALL_PARSE_METHOD_NAMES:
            continue
        keyword_value = _keyword_value_node(each_node, NAMESPACE_KEYWORD_NAME)
        if isinstance(keyword_value, ast.Name):
            keyword_names.add(keyword_value.id)
    return keyword_names


def _namespace_variable_names(tree: ast.Module) -> set[str]:
    """Return names bound to a parse result, a ``namespace=`` object, or an alias.

    A direct binding (``parsed = parse_args()``), the first element of a
    tuple-unpack of the documented ``(namespace, remaining)`` return
    (``parsed, remaining = parse_known_args()``), a ``namespace=`` keyword object
    (``parse_args(namespace=options)``), and a simple re-binding chain
    (``alias = parsed``) each name the same namespace.
    """
    seed_names = _parse_call_namespace_names(tree) | _namespace_keyword_argument_names(tree)
    return _alias_namespace_names(tree, seed_names)


def _attribute_value_name_ids(tree: ast.Module) -> set[int]:
    """Return ``id()`` of every Name that is the object of an attribute access.

    The Name in ``namespace.repo`` is the ``.value`` of an ``ast.Attribute``, so it
    is a per-attribute read rather than a use of the namespace object itself.
    """
    return {
        id(each_node.value)
        for each_node in ast.walk(tree)
        if isinstance(each_node, ast.Attribute) and isinstance(each_node.value, ast.Name)
    }


def _namespace_keyword_value_name_ids(tree: ast.Module) -> set[int]:
    """Return ``id()`` of every Name passed as the ``namespace=`` keyword to a parse call.

    ``parse_args(namespace=options)`` binds the namespace at this position rather
    than consuming it, so this Name is excluded from the escape scan the way an
    attribute-read object is.
    """
    keyword_value_ids: set[int] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Call):
            continue
        function_node = each_node.func
        if not isinstance(function_node, ast.Attribute):
            continue
        if function_node.attr not in ALL_PARSE_METHOD_NAMES:
            continue
        keyword_value = _keyword_value_node(each_node, NAMESPACE_KEYWORD_NAME)
        if isinstance(keyword_value, ast.Name):
            keyword_value_ids.add(id(keyword_value))
    return keyword_value_ids


def _namespace_used_as_value(tree: ast.Module, all_namespace_names: set[str]) -> bool:
    """Return whether a tracked namespace Name is used as a value rather than an attribute read.

    A tracked namespace Name read in Load context anywhere in the module -- passed
    to a call, returned, aliased, double-star unpacked, or nested inside a container
    literal -- uses the namespace object itself and hides which attributes are read.
    Two positions are excluded: the object of an attribute access (``namespace.repo``
    is a per-attribute read) and a Name passed as the ``namespace=`` keyword to a
    parse call (a binding site, not a consumption).
    """
    excluded_name_ids = _attribute_value_name_ids(tree) | _namespace_keyword_value_name_ids(tree)
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Name):
            continue
        if not isinstance(each_node.ctx, ast.Load):
            continue
        if each_node.id not in all_namespace_names:
            continue
        if id(each_node) in excluded_name_ids:
            continue
        return True
    return False


def _namespace_dict_accessed(tree: ast.Module, all_namespace_names: set[str]) -> bool:
    """Return whether a tracked namespace exposes all attributes via ``__dict__``."""
    for each_node in ast.walk(tree):
        if (
            isinstance(each_node, ast.Attribute)
            and each_node.attr == NAMESPACE_DICT_ATTRIBUTE_NAME
            and isinstance(each_node.value, ast.Name)
            and each_node.value.id in all_namespace_names
        ):
            return True
    return False


def _namespace_escapes(tree: ast.Module, all_namespace_names: set[str]) -> bool:
    """Return whether a namespace is consumed in a way that hides which dests are read.

    A namespace whose attributes the static scan cannot enumerate makes any single
    dest unprovably dead, so the check suppresses. Each of the following is such an
    escape: a ``parse_args``/``parse_known_args`` bound method referenced as an
    aliased value rather than called inline; a parse result bound to an attribute-
    or subscript-target the scan cannot track; a parse result consumed inline within
    a larger expression rather than bound to an assignment or a bare statement; a
    tracked namespace read through ``__dict__``; and a tracked namespace Name used as
    a value rather than an attribute read (passed to a call, returned, aliased,
    double-star unpacked, or nested inside a container literal), excluding the object
    of an attribute access and a Name passed as the ``namespace=`` keyword to a parse
    call.
    """
    if _parse_method_is_aliased(tree):
        return True
    if _parse_result_binds_untracked_target(tree):
        return True
    if _parse_call_consumed_inline(tree):
        return True
    if _namespace_dict_accessed(tree, all_namespace_names):
        return True
    return _namespace_used_as_value(tree, all_namespace_names)


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


def _parse_call_consumed_inline(tree: ast.Module) -> bool:
    """Return whether a parse-method result is consumed inline rather than bound to a target.

    A ``parse_args``/``parse_known_args`` call is statically trackable only when its
    result is the value of an assignment (``parsed = parser.parse_args()``) or of a
    bare expression statement (``parser.parse_args(namespace=options)``, whose result
    is discarded after populating the keyword object). Consumed inside a larger
    expression instead -- returned directly, passed to ``vars``, double-star
    unpacked, or bound by a walrus -- the namespace never reaches a tracked name, so
    the check suppresses.
    """
    statement_bound_call_ids: set[int] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, (ast.Assign, ast.Expr)):
            continue
        bound_value = each_node.value
        if not isinstance(bound_value, ast.Call):
            continue
        function_node = bound_value.func
        if isinstance(function_node, ast.Attribute) and function_node.attr in ALL_PARSE_METHOD_NAMES:
            statement_bound_call_ids.add(id(bound_value))
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Call):
            continue
        function_node = each_node.func
        if not isinstance(function_node, ast.Attribute):
            continue
        if function_node.attr not in ALL_PARSE_METHOD_NAMES:
            continue
        if id(each_node) not in statement_bound_call_ids:
            return True
    return False


def check_dead_argparse_arguments(
    content: str, file_path: str, full_file_content: str | None = None
) -> list[str]:
    """Flag an optional argparse flag whose parsed value the same file never reads.

    An optional ``add_argument("--flag", ...)`` is dead when its dest name never
    appears as an attribute read, an augmented-assignment target, or a literal
    ``getattr``/``attrgetter`` access anywhere in the file, the name is not listed
    in a module-level ``__all__``, and no parsed namespace escapes static view. A
    namespace escapes when a ``parse_args``/``parse_known_args`` bound method is
    referenced as an aliased value rather than called inline, when a parse result
    binds to an attribute- or subscript-target the scan cannot track, when a parse
    result is consumed inline within a larger expression rather than bound to an
    assignment or a bare statement, when a tracked namespace is read through
    ``__dict__``, or when a tracked namespace Name is used as a value rather than an
    attribute read (passed to a call, returned, aliased, double-star unpacked, or
    nested inside a container literal), excluding the object of an attribute access
    and a Name passed as the ``namespace=`` keyword to a parse call. A namespace
    name is tracked when it binds a parse result, a tuple-unpacked
    parse result, a ``namespace=`` keyword object, or an alias of one of these.
    Positional arguments and the argparse ``help``/``version`` auto-actions are never
    flagged. Whole-file analysis runs against ``full_file_content`` when supplied so
    an Edit fragment is judged against the reconstructed post-edit file.

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
