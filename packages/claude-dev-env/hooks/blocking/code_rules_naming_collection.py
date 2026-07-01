"""Collection-prefix, stuttering-prefix, loop-variable, and polarity-name-contradiction naming checks."""

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

from code_rules_boolean_mustcheck import _called_terminal_name  # noqa: E402
from code_rules_shared import (  # noqa: E402
    _collect_annotated_arguments,
    _collect_target_names,
    is_migration_file,
    is_test_file,
    is_workflow_registry_file,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_COLLECTION_TYPE_NAMES,
    ALL_LOOP_INDEX_LETTER_EXEMPTIONS,
    ALL_POLARITY_ANTONYM_TOKEN_PAIRS,
    ALL_SUBSCRIPT_ONLY_COLLECTION_TYPE_NAMES,
    ALL_UNION_TYPING_NAMES,
    BARE_EACH_TOKEN,
    COLLECTION_BY_NAME_PATTERN,
    EACH_PREFIX,
    POLARITY_TOKEN_BOUNDARY_PATTERN,
    UPPER_SNAKE_CONSTANT_PATTERN,
)
from hooks_constants.blocking_check_limits import (  # noqa: E402
    MAX_POLARITY_CONTRADICTION_ISSUES,
)
from hooks_constants.stuttering_check_config import (  # noqa: E402
    MAX_STUTTERING_PREFIX_ISSUES,
    STUTTERING_ALL_PREFIX_PATTERN,
)
from hooks_constants.stuttering_import_binding_constants import (  # noqa: E402
    AST_LINENO_ATTRIBUTE,
    MODULE_PATH_SEPARATOR,
    WILDCARD_IMPORT_SENTINEL,
)


def _annotation_names_collection(annotation_node: ast.expr | None) -> bool:
    if annotation_node is None:
        return False
    if isinstance(annotation_node, ast.Name):
        return annotation_node.id in ALL_COLLECTION_TYPE_NAMES
    if isinstance(annotation_node, ast.Attribute):
        return annotation_node.attr in ALL_COLLECTION_TYPE_NAMES
    if isinstance(annotation_node, ast.BinOp) and isinstance(annotation_node.op, ast.BitOr):
        return (
            _annotation_names_collection(annotation_node.left)
            or _annotation_names_collection(annotation_node.right)
        )
    if isinstance(annotation_node, ast.Subscript):
        outer_value = annotation_node.value
        is_optional_or_union_subscript = (
            (isinstance(outer_value, ast.Name) and outer_value.id in ALL_UNION_TYPING_NAMES)
            or (isinstance(outer_value, ast.Attribute) and outer_value.attr in ALL_UNION_TYPING_NAMES)
        )
        if is_optional_or_union_subscript:
            slice_node = annotation_node.slice
            if isinstance(slice_node, ast.Tuple):
                return any(
                    _annotation_names_collection(each_element)
                    for each_element in slice_node.elts
                )
            return _annotation_names_collection(slice_node)
        is_subscript_only_collection_type = (
            (isinstance(outer_value, ast.Name) and outer_value.id in ALL_SUBSCRIPT_ONLY_COLLECTION_TYPE_NAMES)
            or (isinstance(outer_value, ast.Attribute) and outer_value.attr in ALL_SUBSCRIPT_ONLY_COLLECTION_TYPE_NAMES)
        )
        if is_subscript_only_collection_type:
            return True
        return _annotation_names_collection(outer_value)
    return False


def check_collection_prefix(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_node in tree.body:
        target_name: str | None = None
        target_line = 0
        is_collection_value = False
        if isinstance(each_node, ast.AnnAssign) and isinstance(each_node.target, ast.Name):
            target_name = each_node.target.id
            target_line = each_node.lineno
            is_collection_value = _annotation_names_collection(each_node.annotation)
        elif isinstance(each_node, ast.Assign) and len(each_node.targets) == 1 and isinstance(each_node.targets[0], ast.Name):
            target_name = each_node.targets[0].id
            target_line = each_node.lineno
            is_collection_value = isinstance(each_node.value, (ast.Tuple, ast.List, ast.Set, ast.Dict))
        if target_name is None or not is_collection_value:
            continue
        if not UPPER_SNAKE_CONSTANT_PATTERN.match(target_name):
            continue
        if target_name.startswith("ALL_") or COLLECTION_BY_NAME_PATTERN.match(target_name.lower()):
            continue
        issues.append(
            f"Line {target_line}: Collection constant {target_name} - prefix with ALL_ (CODE_RULES §5)"
        )
    for each_walked_node in ast.walk(tree):
        if not isinstance(each_walked_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_arg in _collect_annotated_arguments(each_walked_node):
            if not _annotation_names_collection(each_arg.annotation):
                continue
            if each_arg.arg in {"self", "cls"}:
                continue
            if each_arg.arg.startswith("all_") or COLLECTION_BY_NAME_PATTERN.match(each_arg.arg):
                continue
            issues.append(
                f"Line {each_arg.lineno}: Collection parameter {each_arg.arg} - prefix with all_ (CODE_RULES §5)"
            )
    return issues


def _is_stuttering_all_name(name: str) -> bool:
    return bool(STUTTERING_ALL_PREFIX_PATTERN.match(name))


def _walk_assignment_targets(target: ast.expr) -> list[ast.Name]:
    """Recursively collect ast.Name targets through tuple/list/starred unpacking."""
    if isinstance(target, ast.Name):
        return [target]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[ast.Name] = []
        for each_element in target.elts:
            names.extend(_walk_assignment_targets(each_element))
        return names
    if isinstance(target, ast.Starred):
        return _walk_assignment_targets(target.value)
    return []


def _collect_stuttering_name_bindings(tree: ast.Module) -> list[tuple[str, int]]:
    """Return (name, line_number) for bindings whose introduced name stutters all_/ALL_ prefixes.

    Covers assignments, loops, parameters, walrus targets, comprehensions, with/except
    aliases, import aliases, and class definitions.
    """
    bindings: list[tuple[str, int]] = []
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.Assign):
            for each_target in each_node.targets:
                for each_name in _walk_assignment_targets(each_target):
                    if _is_stuttering_all_name(each_name.id):
                        bindings.append((each_name.id, each_name.lineno))
        elif isinstance(each_node, ast.AnnAssign) and isinstance(each_node.target, ast.Name):
            if _is_stuttering_all_name(each_node.target.id):
                bindings.append((each_node.target.id, each_node.target.lineno))
        elif isinstance(each_node, (ast.For, ast.AsyncFor)):
            for each_name in _walk_assignment_targets(each_node.target):
                if _is_stuttering_all_name(each_name.id):
                    bindings.append((each_name.id, each_name.lineno))
        elif isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _is_stuttering_all_name(each_node.name):
                bindings.append((each_node.name, each_node.lineno))
            for each_arg in _collect_annotated_arguments(each_node):
                if _is_stuttering_all_name(each_arg.arg):
                    bindings.append((each_arg.arg, each_arg.lineno))
        elif isinstance(each_node, ast.NamedExpr) and isinstance(each_node.target, ast.Name):
            if _is_stuttering_all_name(each_node.target.id):
                bindings.append((each_node.target.id, each_node.target.lineno))
        elif isinstance(each_node, ast.comprehension):
            for each_name in _walk_assignment_targets(each_node.target):
                if _is_stuttering_all_name(each_name.id):
                    bindings.append((each_name.id, each_name.lineno))
        elif isinstance(each_node, (ast.With, ast.AsyncWith)):
            for each_with_item in each_node.items:
                if each_with_item.optional_vars is None:
                    continue
                for each_name in _walk_assignment_targets(each_with_item.optional_vars):
                    if _is_stuttering_all_name(each_name.id):
                        bindings.append((each_name.id, each_name.lineno))
        elif isinstance(each_node, ast.ExceptHandler):
            if each_node.name is not None and _is_stuttering_all_name(each_node.name):
                bindings.append((each_node.name, each_node.lineno))
        elif isinstance(each_node, ast.Import):
            for each_alias in each_node.names:
                bound_name = (
                    each_alias.asname
                    if each_alias.asname is not None
                    else each_alias.name.split(MODULE_PATH_SEPARATOR, 1)[0]
                )
                if _is_stuttering_all_name(bound_name):
                    line_number = getattr(each_alias, AST_LINENO_ATTRIBUTE, None) or each_node.lineno
                    bindings.append((bound_name, line_number))
        elif isinstance(each_node, ast.ImportFrom):
            for each_alias in each_node.names:
                if each_alias.name == WILDCARD_IMPORT_SENTINEL:
                    continue
                bound_name = (
                    each_alias.asname
                    if each_alias.asname is not None
                    else each_alias.name
                )
                if _is_stuttering_all_name(bound_name):
                    line_number = getattr(each_alias, AST_LINENO_ATTRIBUTE, None) or each_node.lineno
                    bindings.append((bound_name, line_number))
        elif isinstance(each_node, ast.ClassDef):
            if _is_stuttering_all_name(each_node.name):
                bindings.append((each_node.name, each_node.lineno))
    return bindings


def check_stuttering_collection_prefix(content: str, file_path: str) -> list[str]:
    """Flag identifiers stuttering the all_/ALL_ collection prefix (e.g., all_all_users)."""
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_name, each_line_number in _collect_stuttering_name_bindings(tree):
        issues.append(
            f"Line {each_line_number}: Stuttering collection prefix {each_name!r}"
            f" - use a single all_/ALL_ prefix (CODE_RULES §5)"
        )
        if len(issues) >= MAX_STUTTERING_PREFIX_ISSUES:
            break
    return issues


def check_loop_variable_naming(content: str, file_path: str) -> list[str]:
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, (ast.For, ast.AsyncFor)):
            continue
        for each_name_node in _collect_target_names(each_node.target):
            target_name = each_name_node.id
            if target_name in ALL_LOOP_INDEX_LETTER_EXEMPTIONS:
                continue
            if target_name == BARE_EACH_TOKEN:
                issues.append(
                    f"Line {each_name_node.lineno}: loop variable 'each' is a bare token without subject"
                    f" - rename to each_<subject> (CODE_RULES §5)"
                )
                continue
            if target_name.startswith(EACH_PREFIX) and len(target_name) > len(EACH_PREFIX):
                continue
            issues.append(
                f"Line {each_name_node.lineno}: loop variable {target_name!r} - prefix with each_ (CODE_RULES §5)"
            )
    return issues


def _name_carries_token(name: str, token: str) -> bool:
    """True when name carries token as a whole underscore-delimited word."""
    return re.search(POLARITY_TOKEN_BOUNDARY_PATTERN % re.escape(token), name) is not None


def _contradicting_polarity_pair(target_name: str, called_name: str) -> tuple[str, str] | None:
    """The (target_token, called_token) antonym pair when target and callee assert opposite polarity."""
    target_lower = target_name.lower()
    called_lower = called_name.lower()
    for each_positive_token, each_negative_token in ALL_POLARITY_ANTONYM_TOKEN_PAIRS:
        if _name_carries_token(target_lower, each_positive_token) and _name_carries_token(
            called_lower, each_negative_token
        ):
            return each_positive_token, each_negative_token
        if _name_carries_token(target_lower, each_negative_token) and _name_carries_token(
            called_lower, each_positive_token
        ):
            return each_negative_token, each_positive_token
    return None


def check_polarity_name_contradiction(content: str, file_path: str) -> list[str]:
    """Flag a boolean assignment whose target and callee assert opposite polarity.

    Catches the self-contradicting statement ``is_inside_allowed =
    _point_hits_any_forbidden(...)`` — a target name carrying one polarity token
    (``allowed``) assigned directly from a single call whose callee name carries
    the antonym token (``forbidden``). One side lies about the behavior, so the
    reader cannot trust either name. Rename the callee to a neutral form that
    reads truthfully at every call site.
    """
    if is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_node in ast.walk(tree):
        target_name: str | None = None
        value_node: ast.expr | None = None
        target_line = 0
        if isinstance(each_node, ast.Assign) and len(each_node.targets) == 1 and isinstance(
            each_node.targets[0], ast.Name
        ):
            target_name = each_node.targets[0].id
            value_node = each_node.value
            target_line = each_node.lineno
        elif isinstance(each_node, ast.AnnAssign) and isinstance(each_node.target, ast.Name):
            target_name = each_node.target.id
            value_node = each_node.value
            target_line = each_node.lineno
        if target_name is None or not isinstance(value_node, ast.Call):
            continue
        called_name = _called_terminal_name(value_node)
        if called_name is None:
            continue
        contradicting_pair = _contradicting_polarity_pair(target_name, called_name)
        if contradicting_pair is None:
            continue
        target_token, called_token = contradicting_pair
        issues.append(
            f"Line {target_line}: {target_name!r} (says {target_token!r}) is assigned from"
            f" {called_name!r} (says {called_token!r}) - the name contradicts the value; rename the"
            f" callee to a neutral form so each call site reads truthfully (CODE_RULES §5)"
        )
        if len(issues) >= MAX_POLARITY_CONTRADICTION_ISSUES:
            break
    return issues
