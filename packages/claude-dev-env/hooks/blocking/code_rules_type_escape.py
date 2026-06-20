"""Type escape-hatch and boundary-type checks: Any imports, cast(), unjustified type: ignore, object-typed dereferenced parameters, and Any in signatures."""

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

from code_rules_comments import (  # noqa: E402
    _comment_tokens,
)
from code_rules_shared import (  # noqa: E402
    _collect_annotated_arguments,
    _walk_skipping_type_checking_blocks,
    is_hook_infrastructure,
    is_test_file,
)

from hooks_constants.any_type_config import (  # noqa: E402
    ALL_ANY_ALLOWED_PATTERNS,
)
from hooks_constants.blocking_check_limits import (  # noqa: E402
    ALL_BOUNDARY_TYPE_EXEMPT_FILENAMES,
    MAX_BOUNDARY_TYPE_ISSUES,
    MAX_TYPE_ESCAPE_HATCH_ISSUES,
)


def _render_annotation_source(annotation_node: ast.expr) -> str:
    """Return a textual representation of an annotation AST node."""
    unparse_function = getattr(ast, "unparse", None)
    if unparse_function is not None:
        return unparse_function(annotation_node)
    sys.stderr.write(
        "code_rules_enforcer: ast.unparse unavailable on this interpreter; "
        "falling back to ast.dump for Any detection.\n"
    )
    return ast.dump(annotation_node)


def _annotation_uses_any(annotation_node: Optional[ast.expr]) -> bool:
    """Return True when an annotation AST node textually references Any."""
    if annotation_node is None:
        return False
    annotation_source = _render_annotation_source(annotation_node)
    return bool(re.search(r"\bAny\b", annotation_source))


def _find_any_annotation_lines(source: str) -> list[int]:
    """Return line numbers of annotations that textually reference Any."""
    try:
        parsed_tree = ast.parse(source)
    except SyntaxError:
        return []

    offending_line_numbers: list[int] = []
    already_reported_lines: set[int] = set()
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if isinstance(each_node, ast.AnnAssign) and _annotation_uses_any(each_node.annotation):
            if each_node.lineno not in already_reported_lines:
                offending_line_numbers.append(each_node.lineno)
                already_reported_lines.add(each_node.lineno)
            continue
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if _annotation_uses_any(each_node.returns) and each_node.lineno not in already_reported_lines:
                offending_line_numbers.append(each_node.lineno)
                already_reported_lines.add(each_node.lineno)
            for each_argument in _collect_annotated_arguments(each_node):
                if _annotation_uses_any(each_argument.annotation) and each_argument.lineno not in already_reported_lines:
                    offending_line_numbers.append(each_argument.lineno)
                    already_reported_lines.add(each_argument.lineno)
    return offending_line_numbers


def _find_unjustified_type_ignore_lines(source: str) -> list[int]:
    """Return line numbers of # type: ignore comments lacking a trailing reason."""
    ignore_pattern = re.compile(r"#\s*type:\s*ignore(?:\[[^\]]*\])?(.*)$")
    minimum_justification_characters = len("xxxxx")
    offending_line_numbers: list[int] = []
    for each_comment_token in _comment_tokens(source):
        matched = ignore_pattern.search(each_comment_token.string)
        if not matched:
            continue
        line_number = each_comment_token.start[0]
        trailing_text = matched.group(1).strip()
        if not trailing_text.startswith("#"):
            offending_line_numbers.append(line_number)
            continue
        justification_text = trailing_text.lstrip("#").strip()
        if len(justification_text) < minimum_justification_characters:
            offending_line_numbers.append(line_number)
    return offending_line_numbers


def _find_typing_any_imports(source: str) -> list[int]:
    """Return line numbers of `from typing import ... Any ...` statements."""
    try:
        parsed_tree = ast.parse(source)
    except SyntaxError:
        return []

    offending_line_numbers: list[int] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, ast.ImportFrom):
            continue
        if each_node.module != "typing":
            continue
        for each_alias in each_node.names:
            if each_alias.name == "Any":
                offending_line_numbers.append(each_node.lineno)
                break
    return offending_line_numbers


def _find_typing_wildcard_imports(source: str) -> list[int]:
    """Return line numbers of `from typing import *` statements."""
    try:
        parsed_tree = ast.parse(source)
    except SyntaxError:
        return []

    offending_line_numbers: list[int] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, ast.ImportFrom):
            continue
        if each_node.module != "typing":
            continue
        for each_alias in each_node.names:
            if each_alias.name == "*":
                offending_line_numbers.append(each_node.lineno)
                break
    return offending_line_numbers


def _collect_typing_cast_import_names(source: str) -> frozenset[str]:
    """Return the set of names bound to typing.cast via `from typing import cast`."""
    try:
        parsed_tree = ast.parse(source)
    except SyntaxError:
        return frozenset()

    cast_names: set[str] = set()
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, ast.ImportFrom):
            continue
        if each_node.module != "typing":
            continue
        for each_alias in each_node.names:
            if each_alias.name == "cast":
                cast_names.add(each_alias.asname or each_alias.name)
    return frozenset(cast_names)


def _is_typing_cast_call(call_node: ast.Call, all_cast_import_names: frozenset[str]) -> bool:
    """Return True when a Call node represents a typing.cast() or known bare cast()."""
    function_node = call_node.func
    if isinstance(function_node, ast.Attribute) and function_node.attr == "cast":
        if isinstance(function_node.value, ast.Name) and function_node.value.id == "typing":
            return True
    if isinstance(function_node, ast.Name) and function_node.id in all_cast_import_names:
        return True
    return False


def _find_cast_call_lines(source: str) -> list[int]:
    """Return line numbers of cast(...) calls (typing.cast or bare cast)."""
    try:
        parsed_tree = ast.parse(source)
    except SyntaxError:
        return []

    all_cast_import_names = _collect_typing_cast_import_names(source)

    offending_line_numbers: list[int] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if isinstance(each_node, ast.Call) and _is_typing_cast_call(each_node, all_cast_import_names):
            offending_line_numbers.append(each_node.lineno)
    return offending_line_numbers


def _file_path_matches_any_exemption(file_path: str) -> bool:
    filename = file_path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return filename in {each_pattern.lower() for each_pattern in ALL_ANY_ALLOWED_PATTERNS}


def _annotation_is_bare_object(annotation_node: Optional[ast.expr]) -> bool:
    """Return True when an annotation is the bare builtin ``object`` name."""
    return isinstance(annotation_node, ast.Name) and annotation_node.id == "object"


def _parameter_names_read_as_attribute_base(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> frozenset[str]:
    """Return parameter names the body reads as ``name.attribute``."""
    attribute_base_names: set[str] = set()
    for each_descendant in ast.walk(function_node):
        if not isinstance(each_descendant, ast.Attribute):
            continue
        base_node = each_descendant.value
        if isinstance(base_node, ast.Name):
            attribute_base_names.add(base_node.id)
    return frozenset(attribute_base_names)


def _find_object_annotated_parameter_lines(source: str) -> list[tuple[int, str]]:
    """Return (line, parameter) for parameters typed ``object`` then read as ``param.attribute``.

    A parameter annotated as the bare builtin ``object`` whose body accesses an
    attribute on it is a type escape hatch: ``object`` declares no attributes,
    so every ``param.attribute`` read goes unchecked. A parameter typed
    ``object`` that the body never dereferences (identity-only use) is honest
    and not flagged.
    """
    try:
        parsed_tree = ast.parse(source)
    except SyntaxError:
        return []

    offending_parameters: list[tuple[int, str]] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        attribute_base_names = _parameter_names_read_as_attribute_base(each_node)
        for each_argument in _collect_annotated_arguments(each_node):
            if not _annotation_is_bare_object(each_argument.annotation):
                continue
            if each_argument.arg in attribute_base_names:
                offending_parameters.append((each_argument.lineno, each_argument.arg))
    return offending_parameters


def check_type_escape_hatches(content: str, file_path: str) -> list[str]:
    """Flag Any annotations, Any imports, cast() calls, object-typed dereferenced parameters, and unjustified # type: ignore."""
    if is_test_file(file_path) or is_hook_infrastructure(file_path):
        return []

    issues: list[str] = []
    is_any_exempt = _file_path_matches_any_exemption(file_path)

    if not is_any_exempt:
        any_annotation_issues: list[str] = []
        for each_any_line in _find_any_annotation_lines(content):
            any_annotation_issues.append(f"Line {each_any_line}: Any annotation - replace with explicit type")
        issues.extend(any_annotation_issues[:MAX_TYPE_ESCAPE_HATCH_ISSUES])

        any_import_issues: list[str] = []
        for each_import_line in _find_typing_any_imports(content):
            any_import_issues.append(
                f"Line {each_import_line}: 'from typing import Any' - remove the Any import and use explicit types"
            )
        issues.extend(any_import_issues[:MAX_TYPE_ESCAPE_HATCH_ISSUES])

        wildcard_issues: list[str] = []
        for each_wildcard_line in _find_typing_wildcard_imports(content):
            wildcard_issues.append(
                f"Line {each_wildcard_line}: 'from typing import *' wildcard import - import explicit names instead"
            )
        issues.extend(wildcard_issues[:MAX_TYPE_ESCAPE_HATCH_ISSUES])

        cast_issues: list[str] = []
        for each_cast_line in _find_cast_call_lines(content):
            cast_issues.append(
                f"Line {each_cast_line}: cast() call - escape hatch around the type system; use explicit types or runtime validation"
            )
        issues.extend(cast_issues[:MAX_TYPE_ESCAPE_HATCH_ISSUES])

        object_parameter_issues: list[str] = []
        for each_object_line, each_parameter_name in _find_object_annotated_parameter_lines(content):
            object_parameter_issues.append(
                f"Line {each_object_line}: parameter '{each_parameter_name}' typed 'object' but read as "
                f"'{each_parameter_name}.attribute' - 'object' declares no attributes, so every access goes "
                "unchecked; name the concrete type the body relies on"
            )
        issues.extend(object_parameter_issues[:MAX_TYPE_ESCAPE_HATCH_ISSUES])

    type_ignore_issues: list[str] = []
    for each_ignore_line in _find_unjustified_type_ignore_lines(content):
        type_ignore_issues.append(
            f"Line {each_ignore_line}: Unjustified # type: ignore - add trailing '# reason' explaining why"
        )
    issues.extend(type_ignore_issues[:MAX_TYPE_ESCAPE_HATCH_ISSUES])

    return issues


def _annotation_node_references_any(annotation_node: ast.expr | None) -> bool:
    if annotation_node is None:
        return False
    for each_descendant in ast.walk(annotation_node):
        if isinstance(each_descendant, ast.Name) and each_descendant.id == "Any":
            return True
        if isinstance(each_descendant, ast.Attribute) and each_descendant.attr == "Any":
            return True
    return False


def _file_has_exempt_boundary_filename(file_path: str) -> bool:
    filename = file_path.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return filename in {each_name.lower() for each_name in ALL_BOUNDARY_TYPE_EXEMPT_FILENAMES}


def _signature_annotations(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[
    tuple[ast.expr, str, int]
]:
    collected_annotations: list[tuple[ast.expr, str, int]] = []
    function_name = function_node.name
    for each_argument in function_node.args.args:
        if each_argument.annotation is not None:
            collected_annotations.append(
                (each_argument.annotation, f"{function_name}({each_argument.arg})", each_argument.lineno)
            )
    for each_argument in function_node.args.posonlyargs:
        if each_argument.annotation is not None:
            collected_annotations.append(
                (each_argument.annotation, f"{function_name}({each_argument.arg})", each_argument.lineno)
            )
    for each_argument in function_node.args.kwonlyargs:
        if each_argument.annotation is not None:
            collected_annotations.append(
                (each_argument.annotation, f"{function_name}({each_argument.arg})", each_argument.lineno)
            )
    if function_node.args.vararg is not None and function_node.args.vararg.annotation is not None:
        collected_annotations.append(
            (function_node.args.vararg.annotation, f"{function_name}(*{function_node.args.vararg.arg})", function_node.args.vararg.lineno)
        )
    if function_node.args.kwarg is not None and function_node.args.kwarg.annotation is not None:
        collected_annotations.append(
            (function_node.args.kwarg.annotation, f"{function_name}(**{function_node.args.kwarg.arg})", function_node.args.kwarg.lineno)
        )
    if function_node.returns is not None:
        collected_annotations.append(
            (function_node.returns, f"{function_name} -> return", function_node.returns.lineno)
        )
    return collected_annotations


def _class_attribute_annotations(class_node: ast.ClassDef) -> list[tuple[ast.expr, str, int]]:
    collected_annotations: list[tuple[ast.expr, str, int]] = []
    for each_statement in class_node.body:
        if isinstance(each_statement, ast.AnnAssign) and isinstance(each_statement.target, ast.Name):
            collected_annotations.append(
                (
                    each_statement.annotation,
                    f"{class_node.name}.{each_statement.target.id}",
                    each_statement.lineno,
                )
            )
    return collected_annotations


def check_boundary_types(content: str, file_path: str) -> list[str]:
    """Flag `Any` appearing in function signatures or class attribute annotations.

    Module boundaries (function parameters, return types, class attributes)
    must name the concrete shape they accept and produce. Local variable
    annotations are private and exempt; `protocols.py` and `types.py` are
    interface-declaration files and exempt.
    """
    if (
        is_test_file(file_path)
        or is_hook_infrastructure(file_path)
        or _file_has_exempt_boundary_filename(file_path)
    ):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for each_annotation, each_label, each_line_number in _signature_annotations(each_node):
                if _annotation_node_references_any(each_annotation):
                    issues.append(
                        f"Line {each_line_number}: {each_label} uses Any at module boundary — "
                        "name the concrete shape callers receive/produce"
                    )
        elif isinstance(each_node, ast.ClassDef):
            for each_annotation, each_label, each_line_number in _class_attribute_annotations(each_node):
                if _annotation_node_references_any(each_annotation):
                    issues.append(
                        f"Line {each_line_number}: {each_label} uses Any at class boundary — "
                        "name the concrete shape this attribute holds"
                    )
        if len(issues) >= MAX_BOUNDARY_TYPE_ISSUES:
            break
    return issues[:MAX_BOUNDARY_TYPE_ISSUES]
