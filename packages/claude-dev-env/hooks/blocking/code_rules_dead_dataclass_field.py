"""Dead dataclass-field check: a @dataclass field assigned but never read in the same file."""

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

from hooks_constants.dead_dataclass_field_constants import (  # noqa: E402
    ALL_DATACLASS_DECORATOR_NAMES,
    ALL_WHOLE_INSTANCE_STRINGIFY_NAMES,
    ATTRGETTER_FUNCTION_NAME,
    CLASSVAR_ANNOTATION_NAME,
    DEAD_DATACLASS_FIELD_GUIDANCE,
    GETATTR_FUNCTION_NAME,
    GETATTR_NAME_ARGUMENT_MINIMUM,
    MAX_DEAD_DATACLASS_FIELD_ISSUES,
    ALL_REFLECTIVE_FIELD_CONSUMER_NAMES,
    WHOLE_INSTANCE_DICT_ATTRIBUTE_NAME,
)


def _decorator_calls_dataclass(decorator_node: ast.expr) -> bool:
    """Return whether a decorator expression applies @dataclass (bare or called)."""
    target_node = (
        decorator_node.func if isinstance(decorator_node, ast.Call) else decorator_node
    )
    if isinstance(target_node, ast.Name):
        return target_node.id in ALL_DATACLASS_DECORATOR_NAMES
    if isinstance(target_node, ast.Attribute):
        return target_node.attr in ALL_DATACLASS_DECORATOR_NAMES
    return False


def _is_dataclass(class_node: ast.ClassDef) -> bool:
    return any(
        _decorator_calls_dataclass(each_decorator)
        for each_decorator in class_node.decorator_list
    )


def _annotation_is_classvar(annotation_node: ast.expr | None) -> bool:
    if annotation_node is None:
        return False
    if isinstance(annotation_node, ast.Name):
        return annotation_node.id == CLASSVAR_ANNOTATION_NAME
    if isinstance(annotation_node, ast.Attribute):
        return annotation_node.attr == CLASSVAR_ANNOTATION_NAME
    if isinstance(annotation_node, ast.Subscript):
        return _annotation_is_classvar(annotation_node.value)
    return False


def _dataclass_field_definitions(class_node: ast.ClassDef) -> list[tuple[str, int]]:
    """Return (field_name, line) for each instance field declared in a dataclass body."""
    fields: list[tuple[str, int]] = []
    for each_statement in class_node.body:
        if not isinstance(each_statement, ast.AnnAssign):
            continue
        if not isinstance(each_statement.target, ast.Name):
            continue
        if _annotation_is_classvar(each_statement.annotation):
            continue
        fields.append((each_statement.target.id, each_statement.lineno))
    return fields


def _string_constant_literal(node: ast.expr) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _dynamic_access_names(tree: ast.Module) -> tuple[set[str], bool]:
    """Return literal attribute-name reads and whether the check must be suppressed.

    Walks every ``getattr(obj, "name")`` and ``operator.attrgetter("a", "b")``
    call, contributing each literal string name as a read attribute name —
    ``getattr`` names its attribute in the second positional argument while
    ``attrgetter`` names one attribute per positional argument. A non-literal
    name argument, or any reflective whole-instance consumer (``asdict``,
    ``astuple``, ``fields``, ``replace``, ``vars``) that reads every field at
    once, means a field cannot be proven unread, so the boolean signals the
    caller to suppress the check for the whole file.
    """
    literal_names: set[str] = set()
    should_suppress_check = False
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Call):
            continue
        function_node = each_node.func
        function_name = None
        if isinstance(function_node, ast.Name):
            function_name = function_node.id
        elif isinstance(function_node, ast.Attribute):
            function_name = function_node.attr
        if function_name in ALL_REFLECTIVE_FIELD_CONSUMER_NAMES:
            should_suppress_check = True
            continue
        if function_name not in {GETATTR_FUNCTION_NAME, ATTRGETTER_FUNCTION_NAME}:
            continue
        string_arguments = [
            argument
            for argument in each_node.args
            if not isinstance(argument, ast.Starred)
        ]
        if function_name == GETATTR_FUNCTION_NAME:
            name_arguments = (
                [string_arguments[1]]
                if len(string_arguments) >= GETATTR_NAME_ARGUMENT_MINIMUM
                else []
            )
        else:
            name_arguments = string_arguments
        if not name_arguments:
            should_suppress_check = True
            continue
        for each_name_argument in name_arguments:
            literal_name = _string_constant_literal(each_name_argument)
            if literal_name is None:
                should_suppress_check = True
            else:
                literal_names.add(literal_name)
    return literal_names, should_suppress_check


def _augmented_assignment_attribute_names(tree: ast.Module) -> set[str]:
    """Return attribute names that an augmented assignment reads before writing.

    ``obj.field += value`` parses to an ``ast.Attribute`` target in Store
    context, yet ``+=`` reads the current attribute value before storing the
    result, so the target attribute counts as a read.
    """
    augmented_read_names: set[str] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.AugAssign):
            continue
        if isinstance(each_node.target, ast.Attribute):
            augmented_read_names.add(each_node.target.attr)
    return augmented_read_names


def _attribute_read_names(tree: ast.Module) -> tuple[set[str], bool]:
    """Return literal attribute-name reads and whether the check must be suppressed.

    Walks every attribute read (Load context) and every augmented-assignment
    target in the module, contributing each attribute name as a read name —
    ``obj.field += value`` reads ``field`` before writing it. A read of
    ``__dict__`` consumes every field of an instance at once, so it cannot prove
    any single field unread and the boolean signals the caller to suppress the
    check for the whole file.
    """
    read_names: set[str] = _augmented_assignment_attribute_names(tree)
    should_suppress_check = False
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.Attribute) or not isinstance(
            each_node.ctx, ast.Load
        ):
            continue
        if each_node.attr == WHOLE_INSTANCE_DICT_ATTRIBUTE_NAME:
            should_suppress_check = True
            continue
        read_names.add(each_node.attr)
    return read_names, should_suppress_check


def _match_pattern_attribute_names(tree: ast.Module) -> set[str]:
    """Return field names that a class pattern reads in a ``match`` statement.

    A class pattern ``case Row(url=found):`` reads the ``url`` field through
    ``ast.MatchClass.kwd_attrs``, so each keyword-pattern attribute name counts
    as a read name even though it never appears as an attribute access.
    """
    matched_names: set[str] = set()
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.MatchClass):
            matched_names.update(each_node.kwd_attrs)
    return matched_names


def _exported_names(tree: ast.Module) -> set[str]:
    """Return names listed in a module-level ``__all__`` literal."""
    exported: set[str] = set()
    for each_node in tree.body:
        if not isinstance(each_node, ast.Assign):
            continue
        targets_all = any(
            isinstance(each_target, ast.Name) and each_target.id == "__all__"
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


def _constructed_class_names(tree: ast.Module) -> set[str]:
    """Return names of classes instantiated by a direct call anywhere in the module."""
    constructed: set[str] = set()
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.Call) and isinstance(each_node.func, ast.Name):
            constructed.add(each_node.func.id)
    return constructed


def _is_whole_instance_stringify_call(node: ast.AST) -> bool:
    """Return whether a call stringifies a whole instance via ``str``/``repr``/``format``."""
    if not isinstance(node, ast.Call):
        return False
    function_node = node.func
    if isinstance(function_node, ast.Name):
        return function_node.id in ALL_WHOLE_INSTANCE_STRINGIFY_NAMES
    if isinstance(function_node, ast.Attribute):
        return function_node.attr in ALL_WHOLE_INSTANCE_STRINGIFY_NAMES
    return False


def _uses_dataclass_dunder_field_reads(tree: ast.Module) -> bool:
    """Return whether the file relies on auto-generated dataclass dunders to read fields.

    ``@dataclass`` synthesizes ``__eq__`` (and ``__lt__``/``__hash__`` under
    ``order``/``frozen``) plus the always-present ``__repr__``, each of which
    reads every field without naming it as an attribute access. Comparing two
    instances, placing instances in a set or dict, formatted-string conversion,
    or stringifying a whole instance therefore reads fields the static scan
    cannot otherwise observe, so the check is suppressed for the whole file.
    """
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.Compare):
            return True
        if isinstance(each_node, (ast.Set, ast.SetComp, ast.Dict, ast.DictComp)):
            return True
        if isinstance(each_node, ast.FormattedValue):
            return True
        if _is_whole_instance_stringify_call(each_node):
            return True
    return False


def check_dead_dataclass_fields(
    content: str, file_path: str, full_file_content: str | None = None
) -> list[str]:
    """Flag a @dataclass field that the same file constructs but never reads.

    A field is dead when its dataclass is instantiated somewhere in the file
    (so the class is live), the field name never appears as an attribute read,
    an augmented-assignment target, a class-pattern keyword, or a literal
    ``getattr``/``attrgetter`` access anywhere in the file, and the file contains
    no non-literal dynamic access, reflective whole-instance consumer
    (``asdict``, ``astuple``, ``fields``, ``replace``, ``vars``), ``__dict__``
    read, or auto-generated dataclass dunder field read (comparison, set/dict
    membership, or whole-instance stringification) that could read it
    indirectly. Whole-file analysis runs against ``full_file_content`` when
    supplied so an Edit fragment is judged against the reconstructed post-edit
    file.

    Args:
        content: The new content under validation (Edit fragment or whole file).
        file_path: The destination path, used for the test/registry exemptions.
        full_file_content: The reconstructed post-edit whole-file content for an
            Edit, or None for a Write where ``content`` is already the whole file.

    Returns:
        One violation message per dead dataclass field, capped at the configured
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
    if _uses_dataclass_dunder_field_reads(tree):
        return []
    dynamic_literal_names, dynamic_access_suppresses_check = _dynamic_access_names(tree)
    attribute_read_names, instance_dict_suppresses_check = _attribute_read_names(tree)
    if dynamic_access_suppresses_check or instance_dict_suppresses_check:
        return []
    read_names = (
        attribute_read_names
        | dynamic_literal_names
        | _match_pattern_attribute_names(tree)
        | _exported_names(tree)
    )
    constructed_class_names = _constructed_class_names(tree)
    issues: list[str] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.ClassDef) or not _is_dataclass(each_node):
            continue
        if each_node.name not in constructed_class_names:
            continue
        for each_field_definition in _dataclass_field_definitions(each_node):
            field_name, field_line = each_field_definition
            if field_name in read_names:
                continue
            issues.append(
                f"Line {field_line}: dataclass field {field_name!r} on {each_node.name}"
                f" - {DEAD_DATACLASS_FIELD_GUIDANCE}"
            )
            if len(issues) >= MAX_DEAD_DATACLASS_FIELD_ISSUES:
                return issues
    return issues
