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


def _positional_and_keyword_arguments(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.arg]:
    """Return only the positional and keyword parameters, excluding ``*args``/``**kwargs``.

    Annotating ``*args: object`` types each element as ``object`` while the
    parameter binding itself is ``tuple[object, ...]``; ``**kwargs: object``
    binds ``dict[str, object]``. Method access on those concrete tuple/dict
    bindings (``args.count(...)``, ``kwargs.get(...)``) is type-safe and is not
    an unchecked ``object`` dereference, so the vararg and kwarg slots are out
    of scope for the object-dereference check.
    """
    arguments = function_node.args
    return [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]


def _comprehension_target_names(comprehension_node: ast.AST) -> set[str]:
    """Return the loop-target names a comprehension binds as its own locals."""
    target_names: set[str] = set()
    generators = getattr(comprehension_node, "generators", [])
    for each_generator in generators:
        for each_target in ast.walk(each_generator.target):
            if isinstance(each_target, ast.Name):
                target_names.add(each_target.id)
    return target_names


def _positional_and_keyword_arguments_of_lambda(lambda_node: ast.Lambda) -> list[ast.arg]:
    """Return a lambda's positional and keyword parameters, excluding ``*args``/``**kwargs``."""
    arguments = lambda_node.args
    return [*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs]


def _names_a_scope_rebinds(scope_node: ast.AST) -> frozenset[str]:
    """Return the names a single nested scope binds as its own locals.

    A nested function or lambda binds its positional and keyword parameters; a
    comprehension binds its loop targets. A name in this set, read inside the
    scope, resolves to the scope's own binding rather than to an enclosing
    parameter.
    """
    if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return frozenset(each_argument.arg for each_argument in _positional_and_keyword_arguments(scope_node))
    if isinstance(scope_node, ast.Lambda):
        return frozenset(each_argument.arg for each_argument in _positional_and_keyword_arguments_of_lambda(scope_node))
    if isinstance(scope_node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        return frozenset(_comprehension_target_names(scope_node))
    return frozenset()


def _parent_node_by_child(root_node: ast.AST) -> dict[int, ast.AST]:
    """Return a parent lookup keyed by each descendant node's identity."""
    parent_by_child_id: dict[int, ast.AST] = {}
    for each_parent in ast.walk(root_node):
        for each_child in ast.iter_child_nodes(each_parent):
            parent_by_child_id[id(each_child)] = each_parent
    return parent_by_child_id


def _read_is_shadowed_by_a_nested_scope(
    read_node: ast.Name,
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    parent_by_child_id: dict[int, ast.AST],
) -> bool:
    """Return True when a name read sits inside a nested scope that rebinds that name.

    The walk climbs from the read node up to the function node. A name-rebinding
    scope between the read and the function — a nested function or lambda whose
    parameter, or a comprehension whose loop target, reuses the read's name —
    means the read resolves to that inner binding, not the enclosing parameter.
    A class body is not such a scope: a method nested in a class still reads an
    enclosing-function local from the function scope, so the climb passes
    through ``ClassDef`` without suppressing the read.
    """
    read_name = read_node.id
    current_node: ast.AST = read_node
    while current_node is not function_node:
        enclosing_node = parent_by_child_id.get(id(current_node))
        if enclosing_node is None or enclosing_node is function_node:
            return False
        if read_name in _names_a_scope_rebinds(enclosing_node):
            return True
        current_node = enclosing_node
    return False


def _index_of_statement_in_enclosing_block(
    statement_node: ast.stmt,
    enclosing_node: ast.AST,
) -> tuple[int, int] | None:
    """Return the (block list identity, index) of a statement within its parent's statement block.

    A statement lives in one of its parent's statement-body lists (``body``,
    ``orelse``, ``finalbody``, and similar). The expression-level list fields a
    parent also holds — an ``Assign``'s ``targets``, a ``Call``'s ``args`` — are
    not statement blocks and are skipped, so the position locates the statement
    on its control-flow path rather than its slot inside an expression.
    """
    for _, each_field_value in ast.iter_fields(enclosing_node):
        if not isinstance(each_field_value, list):
            continue
        for each_index, each_block_member in enumerate(each_field_value):
            if each_block_member is statement_node:
                return (id(each_field_value), each_index)
    return None


def _statement_chain(
    target_node: ast.AST,
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    parent_by_child_id: dict[int, ast.AST],
) -> list[tuple[int, int]]:
    """Return the (block list identity, index) path of enclosing statements from the function body to a node.

    Each entry locates an enclosing statement within its parent's statement
    block, walking up from the target to the function body. Only statement nodes
    contribute a step, so a rebind's path and a read's path are both expressed in
    statement positions and compare directly: a rebind dominates a read only when
    its statement is a straight-line predecessor on the read's path, never a
    branch the read does not also enter.
    """
    all_statement_steps: list[tuple[int, int]] = []
    current_node: ast.AST = target_node
    while current_node is not function_node:
        enclosing_node = parent_by_child_id.get(id(current_node))
        if enclosing_node is None:
            break
        if isinstance(current_node, ast.stmt):
            block_position = _index_of_statement_in_enclosing_block(current_node, enclosing_node)
            if block_position is not None:
                all_statement_steps.append(block_position)
        current_node = enclosing_node
    all_statement_steps.reverse()
    return all_statement_steps


def _body_block_header_chain(
    all_body_statements: list[ast.stmt],
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    parent_by_child_id: dict[int, ast.AST],
) -> list[tuple[int, int]] | None:
    """Return a chain that locates the head of a statement body, before its first statement.

    An ``except ... as`` handler body, a ``match`` case body, and an
    ``if isinstance(...)`` then-branch each bind or narrow a name for the
    statements inside that body, the way a ``for`` header binds its loop target
    for the loop body. The chain reuses the first body statement's path with the
    final index replaced by a header sentinel that orders before every statement
    in the block, so it dominates exactly the reads inside that one body and no
    sibling body that shares the same parent.
    """
    if not all_body_statements:
        return None
    header_index_before_first_statement = -1
    first_statement_chain = _statement_chain(all_body_statements[0], function_node, parent_by_child_id)
    if not first_statement_chain:
        return None
    body_block_identity, _ = first_statement_chain[-1]
    return [*first_statement_chain[:-1], (body_block_identity, header_index_before_first_statement)]


def _rebind_dominates_read(
    all_rebind_steps: list[tuple[int, int]],
    all_read_steps: list[tuple[int, int]],
) -> bool:
    """Return True when a rebind statement is a straight-line predecessor of a read.

    The rebind's ancestor blocks above its own statement must match the read's
    path exactly (same block, same index), and at the rebind's own level the two
    share a block with the rebind ordered before the read. A rebind nested
    deeper than that shared level lies on a branch the read need not enter, so it
    does not dominate.

    A header rebind — a ``for`` target, a ``with ... as`` target, or a walrus
    ``:=`` in an ``if``/``while`` test — locates at the same (block, index) as the
    compound statement it heads, while a read nested in that statement's body
    locates one level deeper at that same position. When the rebind chain is a
    strict prefix of the read chain, the rebind heads a compound statement whose
    body contains the read, so it dominates every read inside that body.
    """
    if not all_rebind_steps or len(all_rebind_steps) > len(all_read_steps):
        return False
    all_ancestor_steps = all_rebind_steps[:-1]
    if all_ancestor_steps != all_read_steps[: len(all_ancestor_steps)]:
        return False
    rebind_block, rebind_index = all_rebind_steps[-1]
    read_block, read_index = all_read_steps[len(all_ancestor_steps)]
    if rebind_block != read_block:
        return False
    if rebind_index == read_index:
        return len(all_rebind_steps) < len(all_read_steps)
    return rebind_index < read_index


def _rebind_chains_by_name(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    parent_by_child_id: dict[int, ast.AST],
    all_object_parameter_names: frozenset[str],
) -> dict[str, list[list[tuple[int, int]]]]:
    """Return, per object-parameter name, the statement chain of each own-scope ``Store`` rebind.

    A ``Store`` inside a nested function, lambda, or comprehension binds that
    scope's own local rather than the enclosing parameter, so only ``Store``
    targets that resolve to the function's own scope are collected.
    """
    rebind_chains_by_name: dict[str, list[list[tuple[int, int]]]] = {}
    for each_node in ast.walk(function_node):
        if not isinstance(each_node, ast.Name) or not isinstance(each_node.ctx, ast.Store):
            continue
        if each_node.id not in all_object_parameter_names:
            continue
        if _read_is_shadowed_by_a_nested_scope(each_node, function_node, parent_by_child_id):
            continue
        all_rebind_steps = _statement_chain(each_node, function_node, parent_by_child_id)
        rebind_chains_by_name.setdefault(each_node.id, []).append(all_rebind_steps)
    return rebind_chains_by_name


def _capture_names_a_match_pattern_binds(pattern_node: ast.pattern) -> set[str]:
    """Return the names a ``case`` pattern binds to the matched subject.

    A bare capture (``case node``), an ``as`` binding (``case Point() as node``),
    and a star or double-star rest (``case [*rest]``, ``case {**rest}``) each bind
    a name via a string attribute rather than an ``ast.Name`` ``Store`` node, so
    the ``Store``-based collector never sees them.
    """
    bound_names: set[str] = set()
    for each_descendant in ast.walk(pattern_node):
        if isinstance(each_descendant, (ast.MatchAs, ast.MatchStar)) and each_descendant.name is not None:
            bound_names.add(each_descendant.name)
        if isinstance(each_descendant, ast.MatchMapping) and each_descendant.rest is not None:
            bound_names.add(each_descendant.rest)
    return bound_names


def _handler_and_case_binding_chains_by_name(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    parent_by_child_id: dict[int, ast.AST],
    all_object_parameter_names: frozenset[str],
) -> dict[str, list[list[tuple[int, int]]]]:
    """Return, per object-parameter name, the body-header chain of each ``except as`` or ``case`` rebind.

    An ``except E as name`` clause binds ``name`` to the caught exception via
    ``ExceptHandler.name`` (a string); a ``case`` capture binds via
    ``MatchAs``/``MatchStar``/``MatchMapping`` name attributes. Neither is an
    ``ast.Name`` ``Store`` node, so each is collected here as a body-header rebind
    that dominates only the reads inside its own handler or case body.
    """
    binding_chains_by_name: dict[str, list[list[tuple[int, int]]]] = {}
    for each_node in ast.walk(function_node):
        if isinstance(each_node, ast.ExceptHandler) and each_node.name in all_object_parameter_names:
            body_header_chain = _body_block_header_chain(each_node.body, function_node, parent_by_child_id)
            if body_header_chain is not None:
                binding_chains_by_name.setdefault(each_node.name, []).append(body_header_chain)
        if isinstance(each_node, ast.match_case):
            for each_bound_name in _capture_names_a_match_pattern_binds(each_node.pattern):
                if each_bound_name not in all_object_parameter_names:
                    continue
                body_header_chain = _body_block_header_chain(each_node.body, function_node, parent_by_child_id)
                if body_header_chain is not None:
                    binding_chains_by_name.setdefault(each_bound_name, []).append(body_header_chain)
    return binding_chains_by_name


def _isinstance_narrowed_name(isinstance_test: ast.expr) -> str | None:
    """Return the parameter name an ``isinstance(name, ...)`` test narrows, or None."""
    if not isinstance(isinstance_test, ast.Call):
        return None
    if not isinstance(isinstance_test.func, ast.Name) or isinstance_test.func.id != "isinstance":
        return None
    if not isinstance_test.args:
        return None
    narrowed_subject = isinstance_test.args[0]
    if isinstance(narrowed_subject, ast.Name):
        return narrowed_subject.id
    return None


def _branch_body_always_exits(all_body_statements: list[ast.stmt]) -> bool:
    """Return True when a statement body ends in a control-flow exit (return/raise/continue/break)."""
    if not all_body_statements:
        return False
    last_statement = all_body_statements[-1]
    return isinstance(last_statement, (ast.Return, ast.Raise, ast.Continue, ast.Break))


def _isinstance_narrowing_chains_by_name(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    parent_by_child_id: dict[int, ast.AST],
    all_object_parameter_names: frozenset[str],
) -> dict[str, list[list[tuple[int, int]]]]:
    """Return, per object-parameter name, the chains over which an ``isinstance`` guard narrows it.

    A positive ``if isinstance(name, T):`` narrows ``name`` for its then-branch, so
    its body-header chain dominates the reads inside that branch. A negated
    ``if not isinstance(name, T):`` whose body always exits narrows ``name`` on the
    fall-through, so the ``if`` statement's own chain dominates the same-block reads
    after it. A type checker checks ``name.attribute`` over either narrowed region,
    so a read there is not an unchecked ``object`` access.
    """
    narrowing_chains_by_name: dict[str, list[list[tuple[int, int]]]] = {}
    for each_node in ast.walk(function_node):
        if not isinstance(each_node, ast.If):
            continue
        guard_test = each_node.test
        is_negated_guard = isinstance(guard_test, ast.UnaryOp) and isinstance(guard_test.op, ast.Not)
        isinstance_test = guard_test.operand if isinstance(guard_test, ast.UnaryOp) else guard_test
        narrowed_name = _isinstance_narrowed_name(isinstance_test)
        if narrowed_name is None or narrowed_name not in all_object_parameter_names:
            continue
        if is_negated_guard:
            if not _branch_body_always_exits(each_node.body):
                continue
            fall_through_chain = _statement_chain(each_node, function_node, parent_by_child_id)
            narrowing_chains_by_name.setdefault(narrowed_name, []).append(fall_through_chain)
            continue
        body_header_chain = _body_block_header_chain(each_node.body, function_node, parent_by_child_id)
        if body_header_chain is not None:
            narrowing_chains_by_name.setdefault(narrowed_name, []).append(body_header_chain)
    return narrowing_chains_by_name


def _all_suppression_chains_by_name(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    parent_by_child_id: dict[int, ast.AST],
    all_object_parameter_names: frozenset[str],
) -> dict[str, list[list[tuple[int, int]]]]:
    """Return, per object-parameter name, every statement chain that suppresses a dereference.

    A read is suppressed when a chain in this map dominates it: an own-scope
    ``Store`` rebind, an ``except as`` or ``case`` capture rebind, or an
    ``isinstance`` narrowing guard. A read no chain dominates still resolves to the
    bare ``object`` parameter and counts as an unchecked dereference.
    """
    suppression_chains_by_name: dict[str, list[list[tuple[int, int]]]] = {}
    for each_collector in (
        _rebind_chains_by_name,
        _handler_and_case_binding_chains_by_name,
        _isinstance_narrowing_chains_by_name,
    ):
        for each_name, each_chain_list in each_collector(
            function_node, parent_by_child_id, all_object_parameter_names
        ).items():
            suppression_chains_by_name.setdefault(each_name, []).extend(each_chain_list)
    return suppression_chains_by_name


def _parameter_names_dereferenced_while_live(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    all_object_parameter_names: frozenset[str],
) -> frozenset[str]:
    """Return object-parameter names read as ``name.attribute`` while still bound to the parameter and unchecked.

    A read counts only when it resolves to the bare ``object`` parameter at the
    read site and no suppressor on the straight-line path to it makes the access
    type-checked. It is not counted when it sits in a scope that rebinds the name
    (a nested function, lambda, or comprehension that reuses the name), and not
    counted when a dominating suppressor precedes it: an own-scope ``Store``
    rebind, an ``except as`` or ``case`` capture rebind, or an ``isinstance``
    narrowing guard. A suppressor on a branch the read need not enter leaves the
    read bound to the bare parameter, so the read still counts.
    """
    parent_by_child_id = _parent_node_by_child(function_node)
    suppression_chains_by_name = _all_suppression_chains_by_name(
        function_node, parent_by_child_id, all_object_parameter_names
    )
    dereferenced_names: set[str] = set()
    for each_node in ast.walk(function_node):
        if not isinstance(each_node, ast.Attribute) or not isinstance(each_node.value, ast.Name):
            continue
        base_name = each_node.value.id
        if base_name not in all_object_parameter_names:
            continue
        if _read_is_shadowed_by_a_nested_scope(each_node.value, function_node, parent_by_child_id):
            continue
        all_read_steps = _statement_chain(each_node.value, function_node, parent_by_child_id)
        all_dominating_suppressors = suppression_chains_by_name.get(base_name, [])
        if any(
            _rebind_dominates_read(each_suppressor_chain, all_read_steps)
            for each_suppressor_chain in all_dominating_suppressors
        ):
            continue
        dereferenced_names.add(base_name)
    return frozenset(dereferenced_names)


def _find_object_annotated_parameter_lines(source: str) -> list[tuple[int, str]]:
    """Return (line, parameter) for positional/keyword parameters typed ``object`` then dereferenced.

    A positional or keyword parameter annotated as the bare builtin ``object``
    whose body reads an unchecked attribute on it is a type escape hatch: a read
    of a bare ``object`` value goes unchecked, because ``object`` declares no
    attributes. The decision is per read, so a parameter is flagged when at least
    one read of it resolves to the bare parameter at the read site. A parameter
    typed ``object`` that the body never dereferences (identity-only use) is
    honest and not flagged. A single read does not count when a dominating
    suppressor precedes it on the straight-line path — an own-scope ``Store``
    rebind, an ``except as`` or ``case`` capture rebind, or an ``isinstance``
    narrowing guard — or when the read sits inside a nested function, lambda, or
    comprehension that reuses the name as its own binding; a class body is not
    such a scope, so a method nested in a class that reads an enclosing-function
    parameter still counts. A read on a branch a non-dominating suppressor does
    not reach, and a top-level read whose name a later nested scope reuses, both
    still count. The ``*args``/``**kwargs`` slots are out of scope: ``object``
    there types the elements, while the binding is a concrete ``tuple``/``dict``.
    """
    try:
        parsed_tree = ast.parse(source)
    except SyntaxError:
        return []

    offending_parameters: list[tuple[int, str]] = []
    for each_node in _walk_skipping_type_checking_blocks(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        object_parameters = [
            each_argument
            for each_argument in _positional_and_keyword_arguments(each_node)
            if _annotation_is_bare_object(each_argument.annotation)
        ]
        if not object_parameters:
            continue
        object_parameter_names = frozenset(each_argument.arg for each_argument in object_parameters)
        dereferenced_names = _parameter_names_dereferenced_while_live(each_node, object_parameter_names)
        for each_argument in object_parameters:
            if each_argument.arg in dereferenced_names:
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
                f"'{each_parameter_name}.attribute' on a path where its type is not narrowed - a bare "
                "'object' read goes unchecked; narrow it with an isinstance guard before the read, or name "
                "the concrete type the body relies on"
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
