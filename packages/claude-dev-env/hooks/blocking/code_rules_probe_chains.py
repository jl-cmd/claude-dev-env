"""Attribute-chain and os.environ alias-resolution primitives for the test-isolation check."""

import ast
import sys
from collections.abc import Iterator
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_CANONICAL_DOTTED_NAMES_BY_BARE_IMPORT,
    ALL_ENVIRONMENT_GETTER_DOTTED_NAMES,
    ALL_PROBE_ALIASABLE_CANONICAL_PREFIXES,
    ALL_PROBE_RELEVANT_MODULE_CANONICAL_NAMES,
    ENVIRON_GET_METHOD_NAME,
    OS_ENVIRON_DOTTED_NAME,
)


def _dotted_call_attribute_chain(call_node: ast.Call) -> str | None:
    """Return the dotted name path of *call_node*'s callee, or None.

    For ``pathlib.Path.home()`` returns ``"pathlib.Path.home"``; for
    ``Path.home()`` returns ``"Path.home"``; for ``tempfile.gettempdir()``
    returns ``"tempfile.gettempdir"``. Returns ``None`` when the call target
    is not a pure attribute chain rooted at an ``ast.Name`` (for example,
    ``obj.method()`` where ``obj`` is the result of another expression).
    """
    chain_parts: list[str] = []
    walker: ast.expr = call_node.func
    while isinstance(walker, ast.Attribute):
        chain_parts.append(walker.attr)
        walker = walker.value
    if not isinstance(walker, ast.Name):
        return None
    chain_parts.append(walker.id)
    chain_parts.reverse()
    return ".".join(chain_parts)


def _record_probe_import_aliases(
    import_node: ast.Import | ast.ImportFrom,
    all_canonical_names_by_alias: dict[str, str],
) -> None:
    """Record the probe-relevant alias entries from a single import statement.

    Module aliases are recorded only for the probe-relevant modules in
    ``ALL_PROBE_RELEVANT_MODULE_CANONICAL_NAMES``. Bare-imported names are
    recorded only for the ``(module, name)`` pairs in
    ``ALL_CANONICAL_DOTTED_NAMES_BY_BARE_IMPORT``. Imports outside those sets are
    ignored so unrelated bindings never rewrite a chain.

    Args:
        import_node: A single ``ast.Import`` or ``ast.ImportFrom`` statement.
        all_canonical_names_by_alias: The alias map to mutate in place with any
            probe-relevant local-name to canonical-dotted-prefix entries.
    """
    if isinstance(import_node, ast.Import):
        for each_alias in import_node.names:
            if each_alias.name not in ALL_PROBE_RELEVANT_MODULE_CANONICAL_NAMES:
                continue
            local_name = each_alias.asname or each_alias.name
            all_canonical_names_by_alias[local_name] = each_alias.name
        return
    for each_alias in import_node.names:
        canonical_dotted = ALL_CANONICAL_DOTTED_NAMES_BY_BARE_IMPORT.get(
            (import_node.module or "", each_alias.name)
        )
        if canonical_dotted is None:
            continue
        local_name = each_alias.asname or each_alias.name
        all_canonical_names_by_alias[local_name] = canonical_dotted


def _node_is_lexically_inside_function_or_class(
    node: ast.AST, parent_by_child_id: dict[int, ast.AST],
) -> bool:
    """Return True when *node* is nested inside a function or class body.

    Walks ancestors via *parent_by_child_id*. A node nested only inside
    module-level ``try``/``if``/``with`` blocks has no enclosing function or
    class and is module-scoped; a node inside a
    ``FunctionDef``/``AsyncFunctionDef``/``ClassDef`` body is scoped to that
    enclosing definition and is not module-scoped. A class-body import binds
    its alias only within the class namespace, so it must not enter the
    module-wide alias map any more than a function-local import does.

    Args:
        node: The node whose lexical scope is being classified.
        parent_by_child_id: Child-``id()``-to-parent map from
            ``_build_parent_map``.

    Returns:
        True when an enclosing
        ``FunctionDef``/``AsyncFunctionDef``/``ClassDef`` exists.
    """
    current_ancestor = parent_by_child_id.get(id(node))
    while current_ancestor is not None:
        if isinstance(
            current_ancestor,
            (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef),
        ):
            return True
        current_ancestor = parent_by_child_id.get(id(current_ancestor))
    return False


def _canonical_probe_prefix_for_value(
    node: ast.expr, all_canonical_names_by_alias: dict[str, str],
) -> str | None:
    if isinstance(node, ast.Name):
        candidate_prefix = all_canonical_names_by_alias.get(node.id, node.id)
    elif isinstance(node, ast.Attribute):
        attribute_chain = _dotted_attribute_chain(node)
        if attribute_chain is None:
            return None
        candidate_prefix = _resolve_chain_through_aliases(
            attribute_chain, all_canonical_names_by_alias
        )
    else:
        return None
    if candidate_prefix in ALL_PROBE_ALIASABLE_CANONICAL_PREFIXES:
        return candidate_prefix
    return None


def _attribute_chain_resolves_to_os_environ(
    node: ast.expr, all_canonical_names_by_alias: dict[str, str],
) -> bool:
    if not isinstance(node, ast.Attribute):
        return False
    chain = _dotted_attribute_chain(node)
    if chain is None:
        return False
    canonical_chain = _resolve_chain_through_aliases(
        chain, all_canonical_names_by_alias
    )
    return canonical_chain == OS_ENVIRON_DOTTED_NAME


def _dotted_attribute_chain(attribute_node: ast.Attribute) -> str | None:
    chain_parts: list[str] = []
    walker: ast.expr = attribute_node
    while isinstance(walker, ast.Attribute):
        chain_parts.append(walker.attr)
        walker = walker.value
    if not isinstance(walker, ast.Name):
        return None
    chain_parts.append(walker.id)
    chain_parts.reverse()
    return ".".join(chain_parts)


def _resolve_chain_through_aliases(
    chain: str, all_canonical_names_by_alias: dict[str, str],
) -> str:
    """Rewrite the leading segment of *chain* through the alias map.

    Args:
        chain: A dotted callee chain such as ``"P.home"``,
            ``"op.expanduser"``, or ``"o.path.expanduser"``.
        all_canonical_names_by_alias: Local-binding-to-canonical-prefix
            mapping from ``_build_alias_canonicalization_map``.

    Returns:
        The chain with its leading segment replaced by the canonical
        (possibly multi-segment) prefix when a binding matches; otherwise
        the chain unchanged.
    """
    first_segment, separator, remainder = chain.partition(".")
    canonical_prefix = all_canonical_names_by_alias.get(first_segment)
    if canonical_prefix is None:
        return chain
    if not separator:
        return canonical_prefix
    return f"{canonical_prefix}{separator}{remainder}"


def _environ_key_string_from_call(
    call_node: ast.Call,
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
) -> str | None:
    if not _call_is_environment_getter(call_node, all_canonical_names_by_alias, all_environ_local_bindings):
        return None
    if not call_node.args:
        return None
    first_argument = call_node.args[0]
    if isinstance(first_argument, ast.Constant) and isinstance(first_argument.value, str):
        return first_argument.value
    return None


def _call_is_environment_getter(
    call_node: ast.Call,
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
) -> bool:
    """Return True when *call_node* reads an env var via a recognized getter.

    Recognizes the canonical ``os.getenv(...)`` / ``os.environ.get(...)``
    chains and the local-alias ``e.get(...)`` form where ``e`` is a name in
    *all_environ_local_bindings* (a binding to ``os.environ`` collected from
    the same test function).

    Args:
        call_node: The call to inspect.
        all_canonical_names_by_alias: Import-alias map from
            ``_build_alias_canonicalization_map``.
        all_environ_local_bindings: Local names bound to ``os.environ`` within
            the test function being analyzed.

    Returns:
        True when the call is an environment getter whose key argument is
        worth inspecting.
    """
    if _call_targets_local_environ_get(call_node, all_environ_local_bindings):
        return True
    raw_chain = _dotted_call_attribute_chain(call_node)
    if raw_chain is None:
        return False
    canonical_chain = _resolve_chain_through_aliases(raw_chain, all_canonical_names_by_alias)
    return canonical_chain in ALL_ENVIRONMENT_GETTER_DOTTED_NAMES


def _call_targets_local_environ_get(
    call_node: ast.Call, all_environ_local_bindings: set[str],
) -> bool:
    callee = call_node.func
    if not isinstance(callee, ast.Attribute):
        return False
    if callee.attr != ENVIRON_GET_METHOD_NAME:
        return False
    receiver = callee.value
    return isinstance(receiver, ast.Name) and receiver.id in all_environ_local_bindings


def _environ_key_string_from_subscript(
    subscript_node: ast.Subscript,
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
) -> str | None:
    if not _subscript_target_is_os_environ(
        subscript_node.value, all_canonical_names_by_alias, all_environ_local_bindings
    ):
        return None
    key_node = subscript_node.slice
    if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
        return key_node.value
    return None


def _subscript_target_is_os_environ(
    target_node: ast.expr,
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
) -> bool:
    if isinstance(target_node, ast.Name):
        if target_node.id in all_environ_local_bindings:
            return True
        return all_canonical_names_by_alias.get(target_node.id) == OS_ENVIRON_DOTTED_NAME
    if isinstance(target_node, ast.Attribute):
        return _attribute_chain_resolves_to_os_environ(target_node, all_canonical_names_by_alias)
    return False


def _children_to_descend_into(node: ast.AST) -> list[ast.AST]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
        return []
    if isinstance(node, ast.ClassDef):
        return list(node.body)
    return list(ast.iter_child_nodes(node))


def _descend_within_test_scope(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> Iterator[ast.AST]:
    """Yield every descendant of *function_node* on the test's own runtime path.

    Bounded traversal that shares ``_children_to_descend_into`` so every caller
    treats the same nodes as in scope. Nested function definitions, methods, and
    lambdas are scope boundaries — Python does not run a callable's body just
    because the callable (or its enclosing class) is defined, so a binding or
    probe inside one does not leak onto the test's runtime path. Nested
    ``ClassDef`` bodies stay in scope because their class-creation statements
    (class attribute initializers) run as the ``class`` statement executes
    during the test; descent stops at the methods declared in that class body.

    Args:
        function_node: The test function whose in-scope descendants to yield.

    Yields:
        Each descendant node within the test's bounded scope, in stack-pop
        order.
    """
    nodes_to_visit: list[ast.AST] = list(ast.iter_child_nodes(function_node))
    while nodes_to_visit:
        each_descendant = nodes_to_visit.pop()
        yield each_descendant
        nodes_to_visit.extend(_children_to_descend_into(each_descendant))
