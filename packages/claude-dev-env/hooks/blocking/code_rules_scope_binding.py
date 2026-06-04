"""Lexical scope-binding collectors used by the unused-import check."""

import ast

from hooks_constants.stuttering_import_binding_constants import (
    WILDCARD_IMPORT_SENTINEL,
)


def _attribute_root_name_if_loaded(attribute_node: ast.Attribute) -> ast.Name | None:
    current: ast.expr = attribute_node
    while isinstance(current, ast.Attribute):
        current = current.value
    if isinstance(current, ast.Name) and isinstance(current.ctx, ast.Load):
        return current
    return None


class _ScopeBindingCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.binding_names: set[str] = set()
        self.global_names: set[str] = set()

    def collect_arguments(self, arguments: ast.arguments) -> None:
        for each_argument in (
            arguments.posonlyargs
            + arguments.args
            + arguments.kwonlyargs
        ):
            self.binding_names.add(each_argument.arg)
        if arguments.vararg is not None:
            self.binding_names.add(arguments.vararg.arg)
        if arguments.kwarg is not None:
            self.binding_names.add(arguments.kwarg.arg)

    def visit_Global(self, node: ast.Global) -> None:
        self.global_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.binding_names.update(node.names)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.binding_names.add(node.name)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.binding_names.add(node.name)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.binding_names.add(node.name)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return None

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            self.binding_names.add(node.id)

    def visit_Import(self, node: ast.Import) -> None:
        for each_alias in node.names:
            self.binding_names.add(each_alias.asname or each_alias.name.split(".")[0])

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for each_alias in node.names:
            if each_alias.name != WILDCARD_IMPORT_SENTINEL:
                self.binding_names.add(each_alias.asname or each_alias.name)

    def visit_ListComp(self, node: ast.ListComp) -> None:
        return None

    def visit_SetComp(self, node: ast.SetComp) -> None:
        return None

    def visit_DictComp(self, node: ast.DictComp) -> None:
        return None

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        return None

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name is not None:
            self.binding_names.add(node.name)
        self.generic_visit(node)


def _scope_binding_names(scope_node: ast.AST) -> tuple[set[str], set[str]]:
    collector = _ScopeBindingCollector()
    if isinstance(scope_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        collector.collect_arguments(scope_node.args)
        for each_statement in scope_node.body:
            collector.visit(each_statement)
    elif isinstance(scope_node, ast.Lambda):
        collector.collect_arguments(scope_node.args)
        collector.visit(scope_node.body)
    elif isinstance(scope_node, ast.ClassDef):
        for each_statement in scope_node.body:
            collector.visit(each_statement)
    return collector.binding_names, collector.global_names


def _load_name_is_shadowed(
    load_node: ast.AST,
    name: str,
    parent_by_node_id: dict[int, ast.AST],
) -> bool:
    current = parent_by_node_id.get(id(load_node))
    has_passed_function_scope = False
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            has_passed_function_scope = True
            binding_names, global_names = _scope_binding_names(current)
            if name in global_names:
                return False
            if name in binding_names:
                return True
        elif isinstance(current, ast.ClassDef) and not has_passed_function_scope:
            # Class body bindings are order-dependent (name resolution is
            # dynamic, unlike function locals). A load before an assignment
            # still resolves to the module-level name, so conservatively
            # skip class-body shadow detection to avoid false positives.
            pass
        current = parent_by_node_id.get(id(current))
    return False


def _names_from_annotation_text(annotation_text: str) -> set[str]:
    try:
        annotation_tree = ast.parse(annotation_text, mode="eval")
    except SyntaxError:
        return set()
    referenced_names: set[str] = set()
    for each_node in ast.walk(annotation_tree):
        if isinstance(each_node, ast.Name):
            referenced_names.add(each_node.id)
        elif isinstance(each_node, ast.Attribute):
            root_name = _attribute_root_name_if_loaded(each_node)
            if root_name is not None:
                referenced_names.add(root_name.id)
    return referenced_names


def _collect_string_annotation_names(tree: ast.Module) -> set[str]:
    referenced_names: set[str] = set()
    for each_node in ast.walk(tree):
        annotation = None
        if isinstance(each_node, ast.arg):
            annotation = each_node.annotation
        elif isinstance(each_node, (ast.AnnAssign, ast.FunctionDef, ast.AsyncFunctionDef)):
            annotation = each_node.annotation if isinstance(each_node, ast.AnnAssign) else each_node.returns
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            referenced_names.update(_names_from_annotation_text(annotation.value))
    return referenced_names
