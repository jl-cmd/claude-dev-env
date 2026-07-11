"""Pytest test-function collection, isolation-fixture detection, and probe recording for the test-isolation check."""

import ast
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_probe_chains import (  # noqa: E402
    _descend_within_test_scope,
    _dotted_attribute_chain,
    _dotted_call_attribute_chain,
    _environ_key_string_from_call,
    _environ_key_string_from_subscript,
    _resolve_chain_through_aliases,
)
from code_rules_probe_detection import (  # noqa: E402
    _expanduser_argument_references_home,
    _expanduser_method_call_targets_pathlib_path,
    _expandvars_argument_references_home_or_temp,
    _tempfile_factory_call_is_isolated_by_dir,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_DIR_ACCEPTING_TEMPFILE_FACTORY_DOTTED_NAMES,
    ALL_FILESYSTEM_HOME_PROBE_DOTTED_NAMES,
    ALL_HOME_DIRECTORY_ENV_VAR_NAMES,
    ALL_PATHLIB_STATIC_EXPANDUSER_DOTTED_NAMES,
    ALL_PYTEST_FILESYSTEM_ISOLATION_FIXTURE_NAMES,
    EXPANDUSER_DOTTED_NAME,
    EXPANDVARS_DOTTED_NAME,
    PATHLIB_EXPANDUSER_METHOD_NAME,
    PYTEST_TEST_CLASS_NAME_PREFIX,
    PYTEST_USEFIXTURES_MARKER_NAME,
)


def _collect_pytest_collectable_test_functions(
    syntax_tree: ast.Module,
) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Enumerate the function nodes pytest would actually collect as tests.

    Walks module-level statements and the top-level methods of module-level
    classes only. Functions nested inside other functions or lambdas are
    excluded because pytest does not collect nested callables. Module-level
    classes whose name does not start with the
    ``PYTEST_TEST_CLASS_NAME_PREFIX`` (``Test``) are skipped because the
    repo's ``pytest.ini`` declares ``python_classes = Test*``; methods on
    non-``Test*`` helper classes are never collected by pytest.
    """
    collectable: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for each_module_statement in syntax_tree.body:
        if isinstance(each_module_statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                each_module_statement.name.startswith("test_")
                or each_module_statement.name.startswith("should_")
            ):
                collectable.append(each_module_statement)
        elif isinstance(each_module_statement, ast.ClassDef):
            if not each_module_statement.name.startswith(PYTEST_TEST_CLASS_NAME_PREFIX):
                continue
            for each_class_member in each_module_statement.body:
                if isinstance(each_class_member, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
                    each_class_member.name.startswith("test_")
                    or each_class_member.name.startswith("should_")
                ):
                    collectable.append(each_class_member)
    return collectable


def _detect_home_or_temp_probes_in_body(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
    all_path_local_bindings: set[str],
) -> list[tuple[int, str]]:
    """Yield ``(line, probe_label)`` pairs for HOME/TMP probes in *function_node*.

    The walk descends into ``ClassDef`` nodes nested inside the test body and
    into their class-level statements. Class-level statements (class attribute
    initializers) run at class-creation time as the ``class`` statement
    executes during the test, so a probe in an initializer such as ``root =
    Path.home()`` is on the test's runtime path and is reported. A method of a
    nested class is a callable-scope boundary: Python does not run a method
    just because its class is defined, so the walk does not descend into method
    bodies. Standalone nested helper functions and lambdas defined anywhere are
    likewise scope boundaries — each runs in its own callable scope and carries
    its own isolation contract. Probes that genuinely execute on the test path
    (top-level statements and class-level initializers) are still detected.

    Args:
        function_node: The test function whose body is being scanned.
        all_canonical_names_by_alias: Local-binding-to-canonical-prefix mapping used to resolve
            aliased imports before probe membership checks.
        all_environ_local_bindings: Local names bound to ``os.environ`` (scoped
            to *function_node*) used to attribute subscript and ``.get(...)``
            reads to a HOME/TMP env probe.
        all_path_local_bindings: Local names bound to a ``pathlib.Path``
            construction (scoped to *function_node*) used to attribute a
            ``.expanduser()`` method call to a home-directory probe.

    Returns:
        A list of ``(line_number, probe_label)`` tuples for each HOME/TMP
        probe attributed to the test, in stack-pop order.
    """
    probes: list[tuple[int, str]] = []
    for each_descendant in _descend_within_test_scope(function_node):
        _record_home_or_temp_probe(
            each_descendant,
            probes,
            all_canonical_names_by_alias,
            all_environ_local_bindings,
            all_path_local_bindings,
        )
    probes.sort(key=lambda each_probe: each_probe[0])
    return probes


def _record_home_or_temp_probe(
    node: ast.AST,
    all_probes: list[tuple[int, str]],
    all_canonical_names_by_alias: dict[str, str],
    all_environ_local_bindings: set[str],
    all_path_local_bindings: set[str],
) -> None:
    if isinstance(node, ast.Call):
        if _expanduser_method_call_targets_pathlib_path(
            node, all_canonical_names_by_alias, all_path_local_bindings
        ):
            all_probes.append((node.lineno, f"Path.{PATHLIB_EXPANDUSER_METHOD_NAME}()"))
            return
        raw_chain = _dotted_call_attribute_chain(node)
        if raw_chain is None:
            return
        canonical_chain = _resolve_chain_through_aliases(raw_chain, all_canonical_names_by_alias)
        if canonical_chain == EXPANDVARS_DOTTED_NAME:
            if _expandvars_argument_references_home_or_temp(node):
                all_probes.append((node.lineno, f"{canonical_chain}()"))
            return
        if canonical_chain == EXPANDUSER_DOTTED_NAME:
            if _expanduser_argument_references_home(node):
                all_probes.append((node.lineno, f"{canonical_chain}()"))
            return
        if canonical_chain in ALL_PATHLIB_STATIC_EXPANDUSER_DOTTED_NAMES:
            if _expanduser_argument_references_home(node):
                all_probes.append((node.lineno, f"{canonical_chain}()"))
            return
        if canonical_chain in ALL_FILESYSTEM_HOME_PROBE_DOTTED_NAMES:
            if (
                canonical_chain in ALL_DIR_ACCEPTING_TEMPFILE_FACTORY_DOTTED_NAMES
                and _tempfile_factory_call_is_isolated_by_dir(
                    node, all_canonical_names_by_alias, all_environ_local_bindings
                )
            ):
                return
            all_probes.append((node.lineno, f"{canonical_chain}()"))
            return
        environ_key = _environ_key_string_from_call(
            node, all_canonical_names_by_alias, all_environ_local_bindings
        )
        if environ_key in ALL_HOME_DIRECTORY_ENV_VAR_NAMES:
            all_probes.append((node.lineno, f"os env probe '{environ_key}'"))
        return
    if isinstance(node, ast.Subscript):
        environ_key = _environ_key_string_from_subscript(
            node, all_canonical_names_by_alias, all_environ_local_bindings
        )
        if environ_key in ALL_HOME_DIRECTORY_ENV_VAR_NAMES:
            all_probes.append((node.lineno, f"os.environ['{environ_key}']"))


def _usefixtures_decorator_requests_isolation_fixture(decorator_node: ast.expr) -> bool:
    """Report whether a decorator is ``usefixtures`` requesting an isolation fixture.

    Recognizes ``@pytest.mark.usefixtures("monkeypatch")`` and the
    ``@mark.usefixtures("monkeypatch")`` short form: an ``ast.Call`` whose callee
    attribute chain ends in ``usefixtures`` and whose string-constant arguments
    include any name in ``ALL_PYTEST_FILESYSTEM_ISOLATION_FIXTURE_NAMES``.

    Args:
        decorator_node: A single decorator expression from a test's decorator list.

    Returns:
        True when the decorator injects an isolation fixture by name.
    """
    if not isinstance(decorator_node, ast.Call):
        return False
    if not isinstance(decorator_node.func, ast.Attribute):
        return False
    callee_chain = _dotted_attribute_chain(decorator_node.func)
    if callee_chain is None:
        return False
    if not callee_chain.endswith(PYTEST_USEFIXTURES_MARKER_NAME):
        return False
    for each_argument in decorator_node.args:
        if (
            isinstance(each_argument, ast.Constant)
            and isinstance(each_argument.value, str)
            and each_argument.value in ALL_PYTEST_FILESYSTEM_ISOLATION_FIXTURE_NAMES
        ):
            return True
    return False


def _function_uses_pytest_isolation_fixture(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    for each_argument in function_node.args.posonlyargs:
        if each_argument.arg in ALL_PYTEST_FILESYSTEM_ISOLATION_FIXTURE_NAMES:
            return True
    for each_argument in function_node.args.args:
        if each_argument.arg in ALL_PYTEST_FILESYSTEM_ISOLATION_FIXTURE_NAMES:
            return True
    for each_argument in function_node.args.kwonlyargs:
        if each_argument.arg in ALL_PYTEST_FILESYSTEM_ISOLATION_FIXTURE_NAMES:
            return True
    for each_decorator in function_node.decorator_list:
        if _usefixtures_decorator_requests_isolation_fixture(each_decorator):
            return True
    return False
