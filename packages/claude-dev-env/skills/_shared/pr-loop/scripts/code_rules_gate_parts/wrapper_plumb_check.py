"""Flag public calls that drop a same-file delegate's optional keyword arguments.

A thin public wrapper that forwards to a module-level helper should keep the
helper's optional keyword surface. When the wrapper narrows it, a caller varying
that keyword hits the wrapper's default instead. This check walks the AST and
reports each such dropped keyword.
"""

import ast
from collections.abc import Iterator
from pathlib import Path

from pr_loop_shared_constants.code_rules_gate_constants import (
    ALL_CODE_FILE_EXTENSIONS,
    ALL_TEST_FILENAME_GLOB_SUFFIXES,
    ALL_TEST_FILENAME_SUFFIXES,
    MAX_VIOLATIONS_PER_CHECK,
    PYTHON_FILE_EXTENSION,
    TEST_CONFTEST_FILENAME,
    TEST_FILENAME_PREFIX,
    TESTS_PATH_SEGMENT,
)


def is_code_path(file_path: Path) -> bool:
    """Return True when *file_path* carries a recognized code extension."""
    return file_path.suffix.lower() in ALL_CODE_FILE_EXTENSIONS


def is_test_path(file_path: str) -> bool:
    """Return True when *file_path* matches a test-file detection pattern.

    ::

        ok(test): test_x.py, x_test.py, x.spec.ts, conftest.py, a/tests/x.py
        ok(not):  regular_module.py

    Args:
        file_path: Path string to classify; backslashes are normalized first.

    Returns:
        True when the path matches any test-file pattern; False otherwise.
    """
    normalized_posix = file_path.replace("\\", "/")
    filename_only = normalized_posix.rsplit("/", maxsplit=1)[-1]
    if TESTS_PATH_SEGMENT in normalized_posix:
        return True
    if filename_only == TEST_CONFTEST_FILENAME:
        return True
    if filename_only.startswith(TEST_FILENAME_PREFIX) and filename_only.endswith(
        PYTHON_FILE_EXTENSION
    ):
        return True
    if any(filename_only.endswith(each) for each in ALL_TEST_FILENAME_SUFFIXES):
        return True
    return any(each in filename_only for each in ALL_TEST_FILENAME_GLOB_SUFFIXES)


def _iter_calls_excluding_nested_functions(node: ast.AST) -> Iterator[ast.Call]:
    """Yield calls under *node*, skipping bodies of nested function definitions."""
    for each_child in ast.iter_child_nodes(node):
        if isinstance(each_child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if isinstance(each_child, ast.Call):
            yield each_child
            continue
        yield from _iter_calls_excluding_nested_functions(each_child)


def _optional_kwargs_of(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> set[str]:
    """Return the names of every optional keyword the function accepts."""
    optional_kwargs: set[str] = set()
    for each_kwonly, each_default in zip(
        function_node.args.kwonlyargs, function_node.args.kw_defaults, strict=False
    ):
        if each_default is not None:
            optional_kwargs.add(each_kwonly.arg)
    positional_defaults = function_node.args.defaults
    if positional_defaults:
        for each_arg in function_node.args.args[-len(positional_defaults) :]:
            optional_kwargs.add(each_arg.arg)
    return optional_kwargs


def _module_level_optional_kwargs_by_name(tree: ast.Module) -> dict[str, set[str]]:
    """Return a map from module-level function name to its optional kwargs."""
    all_function_signatures: dict[str, set[str]] = {}
    for each_node in ast.iter_child_nodes(tree):
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            all_function_signatures[each_node.name] = _optional_kwargs_of(each_node)
    return all_function_signatures


def _method_ids_in_class(class_def: ast.ClassDef) -> set[int]:
    """Return the object ids of every method defined directly in *class_def*."""
    return {
        id(each_node)
        for each_node in class_def.body
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _class_method_node_ids(tree: ast.Module) -> set[int]:
    """Return the object ids of every method defined in any class in the tree."""
    class_method_node_ids: set[int] = set()
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.ClassDef):
            class_method_node_ids.update(_method_ids_in_class(each_node))
    return class_method_node_ids


def _delegate_name_of(call_node: ast.Call) -> str | None:
    """Return the callee name of *call_node*, or None for a non-name callee."""
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id
    if isinstance(call_node.func, ast.Attribute):
        return call_node.func.attr
    return None


def _wrapper_dropped_kwarg_findings(
    wrapper_node: ast.FunctionDef | ast.AsyncFunctionDef,
    all_kwargs_by_function_name: dict[str, set[str]],
) -> Iterator[str]:
    """Yield one finding per optional kwarg *wrapper_node* drops from a delegate."""
    wrapper_kwargs = all_kwargs_by_function_name.get(wrapper_node.name, set())
    for each_call in _iter_calls_excluding_nested_functions(wrapper_node):
        delegate_name = _delegate_name_of(each_call)
        if delegate_name is None:
            continue
        delegate_kwargs = all_kwargs_by_function_name.get(delegate_name)
        if delegate_kwargs is None:
            continue
        missing = delegate_kwargs - wrapper_kwargs
        if missing:
            yield (
                f"Line {wrapper_node.lineno}: Wrapper {wrapper_node.name!r} drops "
                f"optional kwargs {sorted(missing)!r} of delegate {delegate_name!r}"
            )


def _wrapper_candidate_nodes(
    tree: ast.Module, all_class_method_node_ids: set[int]
) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yield each public module function that is not a class method."""
    for each_node in ast.walk(tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if id(each_node) in all_class_method_node_ids:
            continue
        if not each_node.name.startswith("_"):
            yield each_node


def _wrapper_findings_from_tree(tree: ast.Module) -> list[str]:
    """Collect capped wrapper-plumb-through findings from a parsed module."""
    all_signatures = _module_level_optional_kwargs_by_name(tree)
    class_method_node_ids = _class_method_node_ids(tree)
    issues: list[str] = []
    for each_node in _wrapper_candidate_nodes(tree, class_method_node_ids):
        issues.extend(_wrapper_dropped_kwarg_findings(each_node, all_signatures))
        if len(issues) >= MAX_VIOLATIONS_PER_CHECK:
            return issues[:MAX_VIOLATIONS_PER_CHECK]
    return issues


def _is_non_python_or_test(file_path: str) -> bool:
    """Return True for a non-Python code file or a test file."""
    non_python_code_extensions = ALL_CODE_FILE_EXTENSIONS - {PYTHON_FILE_EXTENSION}
    lowercase_file_path = file_path.lower()
    if any(lowercase_file_path.endswith(each) for each in non_python_code_extensions):
        return True
    return is_test_path(file_path)


def check_wrapper_plumb_through(content: str, file_path: str) -> list[str]:
    """Flag public calls that drop a same-file delegate's optional kwargs.

    ::

        def build(name, verbose=False): ...   def wrap(name): return build(name)
        flag: wrap drops optional kwarg 'verbose' of delegate 'build'
        ok:   def wrap(name, verbose=False): return build(name, verbose=verbose)

    Only module-level functions contribute signatures; class methods are skipped
    as signature sources and as wrapper candidates. Emission caps at
    ``MAX_VIOLATIONS_PER_CHECK`` findings.

    Args:
        content: File content as a single string for AST parsing.
        file_path: Repository-relative POSIX path, for skipping non-Python and
            test files early.

    Returns:
        Violation strings, one per dropped optional kwarg; empty for a
        non-Python file, a test file, or a syntax error.
    """
    if _is_non_python_or_test(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    return _wrapper_findings_from_tree(tree)
