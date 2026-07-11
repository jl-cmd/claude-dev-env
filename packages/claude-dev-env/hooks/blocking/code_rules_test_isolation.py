"""Test-isolation check ensuring tests do not probe real home or shared-temp directories."""

import ast
import sys
from pathlib import Path

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_probe_chains import (  # noqa: E402
    _attribute_chain_resolves_to_os_environ,
    _canonical_probe_prefix_for_value,
    _descend_within_test_scope,
    _node_is_lexically_inside_function_or_class,
    _record_probe_import_aliases,
)
from code_rules_probe_detection import (  # noqa: E402
    _pathlib_path_construction_uses_home_tilde,
)
from code_rules_probe_recording import (  # noqa: E402
    _collect_pytest_collectable_test_functions,
    _detect_home_or_temp_probes_in_body,
    _function_uses_pytest_isolation_fixture,
)
from code_rules_shared import (  # noqa: E402
    _build_parent_map,
    _function_definition_line_span,
    _scope_violations_to_changed_lines,
    is_test_file,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_CANONICAL_DOTTED_NAMES_BY_BARE_IMPORT,
    OS_ENVIRON_DOTTED_NAME,
    TEST_ISOLATION_MESSAGE_SUFFIX,
)


def _build_alias_canonicalization_map(syntax_tree: ast.Module) -> dict[str, str]:
    """Map each module-level probe import local name to its canonical prefix.

    Resolves both module aliases and bare-imported names so a dotted-call
    chain rooted at any module-level binding rewrites to the canonical form the
    probe set already matches:

    - ``import os as o`` -> ``o`` resolves to ``os`` (so ``o.getenv`` ->
      ``os.getenv`` and ``o.path.expanduser`` -> ``os.path.expanduser``).
    - ``import os.path as op`` -> ``op`` resolves to ``os.path`` (so
      ``op.expanduser`` -> ``os.path.expanduser``).
    - ``import pathlib as pl`` -> ``pl`` resolves to ``pathlib``.
    - ``from pathlib import Path as P`` -> ``P`` resolves to ``Path``.
    - ``from os import path`` -> ``path`` resolves to ``os.path`` (so
      ``path.expanduser`` -> ``os.path.expanduser``).
    - ``from os.path import expanduser as e`` -> ``e`` resolves to
      ``os.path.expanduser``; ``from os import getenv`` -> ``getenv``
      resolves to ``os.getenv``; ``from os import environ`` -> ``environ``
      resolves to ``os.environ``.

    An import is module-scoped — and enters this shared map — when it is not
    lexically inside any ``FunctionDef``/``AsyncFunctionDef``/``ClassDef`` body.
    That admits top-level imports nested in module-level ``try``/``except``,
    ``if``, or ``with`` blocks (the ``try: import os as o except ImportError:``
    optional-import idiom binds ``o`` module-wide) while excluding both
    function-local and class-body imports. A function-local import binds its
    name only inside the function it appears in, and a class-body import binds
    its alias only within the class namespace; neither may enter this shared,
    module-wide map — otherwise a probe import inside one test would
    canonicalize a same-named reference in a sibling test that never imported
    it. Function-local imports are scoped to their own function by
    ``_collect_local_probe_alias_bindings``.

    Args:
        syntax_tree: The parsed module to scan for module-scoped import
            statements.

    Returns:
        Mapping from module-level local binding name to its canonical dotted
        prefix.
    """
    parent_by_child_id = _build_parent_map(syntax_tree)
    all_canonical_names_by_alias: dict[str, str] = {}
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, (ast.Import, ast.ImportFrom)):
            continue
        if _node_is_lexically_inside_function_or_class(each_node, parent_by_child_id):
            continue
        _record_probe_import_aliases(each_node, all_canonical_names_by_alias)
    return all_canonical_names_by_alias


def _collect_os_environ_local_binding_names(
    scope_node: ast.FunctionDef | ast.AsyncFunctionDef,
    all_canonical_names_by_alias: dict[str, str],
) -> set[str]:
    """Return local names bound to ``os.environ`` within *scope_node*.

    Scoped to the single test function passed as *scope_node* so a binding in
    one test never attributes a same-named access in a sibling test. Tracks
    ``e = os.environ`` style assignments (resolving the right-hand side through
    *all_canonical_names_by_alias* so ``e = o.environ`` with ``import os as o``
    is recognized) and ``from os import environ`` bindings (rare inside a
    function but supported for completeness). Subscript and ``.get(...)`` reads
    on these local names are treated as ``os.environ`` accesses.

    Args:
        scope_node: The single test function node to scan for bindings.
        all_canonical_names_by_alias: Import-alias map from
            ``_build_alias_canonicalization_map``.

    Returns:
        Set of local variable names that reference ``os.environ``.
    """
    environ_bindings: set[str] = set()
    for each_node in _descend_within_test_scope(scope_node):
        if isinstance(each_node, ast.ImportFrom):
            for each_alias in each_node.names:
                canonical_dotted = ALL_CANONICAL_DOTTED_NAMES_BY_BARE_IMPORT.get(
                    (each_node.module or "", each_alias.name)
                )
                if canonical_dotted == OS_ENVIRON_DOTTED_NAME:
                    environ_bindings.add(each_alias.asname or each_alias.name)
            continue
        if not isinstance(each_node, ast.Assign):
            continue
        if not _attribute_chain_resolves_to_os_environ(each_node.value, all_canonical_names_by_alias):
            continue
        for each_target in each_node.targets:
            if isinstance(each_target, ast.Name):
                environ_bindings.add(each_target.id)
    return environ_bindings


def _collect_pathlib_path_local_binding_names(
    scope_node: ast.FunctionDef | ast.AsyncFunctionDef,
    all_canonical_names_by_alias: dict[str, str],
) -> set[str]:
    """Return local names bound to a home-tilde ``pathlib.Path(...)`` construction.

    Scoped to the single test function passed as *scope_node* so a binding in
    one test never attributes a same-named ``.expanduser()`` call in a sibling
    test. Tracks ``candidate = Path('~/x')`` style assignments whose first
    constructor argument is a literal string beginning with ``~`` (resolving
    the constructor through *all_canonical_names_by_alias* so an aliased
    ``candidate = P('~/x')`` with ``from pathlib import Path as P`` and a
    fully qualified ``candidate = pathlib.Path('~/x')`` are both recognized).
    A later ``candidate.expanduser()`` call on such a name is attributed to a
    home-directory probe. A tilde-free or dynamic constructor argument
    (``Path('/tmp/x')`` / ``Path(some_path)``) expands no home directory and
    is not collected, keeping the instance ``.expanduser()`` form symmetric
    with ``os.path.expanduser`` argument inspection.

    Args:
        scope_node: The single test function node to scan for bindings.
        all_canonical_names_by_alias: Import-alias map from
            ``_build_alias_canonicalization_map``.

    Returns:
        Set of local variable names bound to a home-tilde ``pathlib.Path``
        construction.
    """
    path_bindings: set[str] = set()
    for each_node in _descend_within_test_scope(scope_node):
        if not isinstance(each_node, ast.Assign):
            continue
        if not _pathlib_path_construction_uses_home_tilde(
            each_node.value, all_canonical_names_by_alias
        ):
            continue
        for each_target in each_node.targets:
            if isinstance(each_target, ast.Name):
                path_bindings.add(each_target.id)
    return path_bindings


def _collect_local_probe_alias_bindings(
    scope_node: ast.FunctionDef | ast.AsyncFunctionDef,
    all_canonical_names_by_alias: dict[str, str],
) -> dict[str, str]:
    """Return a per-test overlay mapping local names to canonical probe prefixes.

    Scoped to the single test function passed as *scope_node* so an alias bound
    in one test never resolves a same-named access in a sibling test. Two
    binding forms are tracked, both scoped to this function only:

    - Function-local imports — ``import os as o``, ``from os import environ``,
      ``from pathlib import Path`` — resolved through the same probe-relevant
      filtering ``_build_alias_canonicalization_map`` applies to module-level
      imports. Because the shared module map omits function-local imports, this
      overlay is the only place a probe import inside one test takes effect, and
      it stays confined to that test's body.
    - Rebindings of a probe module, class, or callable to a local name —
      ``path_class = Path``, ``read_env = os.getenv``, ``temp_module = tempfile``,
      ``path_module = os.path``, ``e = os.environ`` — by resolving each
      right-hand side through *all_canonical_names_by_alias* and keeping only
      those whose canonical prefix is probe-aliasable
      (``ALL_PROBE_ALIASABLE_CANONICAL_PREFIXES``).

    Merged over the module-level alias map, the overlay lets a later
    ``path_class.home()`` / ``read_env('HOME')`` / ``temp_module.mkdtemp()``
    resolve to its canonical probe chain.

    Args:
        scope_node: The single test function node to scan for alias bindings.
        all_canonical_names_by_alias: Module-level import-alias map from
            ``_build_alias_canonicalization_map``.

    Returns:
        Mapping from local binding name to its canonical probe prefix.
    """
    local_alias_canonical_names: dict[str, str] = {}
    for each_node in _descend_within_test_scope(scope_node):
        if isinstance(each_node, (ast.Import, ast.ImportFrom)):
            _record_probe_import_aliases(each_node, local_alias_canonical_names)
            continue
        if not isinstance(each_node, ast.Assign):
            continue
        canonical_prefix = _canonical_probe_prefix_for_value(
            each_node.value, all_canonical_names_by_alias
        )
        if canonical_prefix is None:
            continue
        for each_target in each_node.targets:
            if isinstance(each_target, ast.Name):
                local_alias_canonical_names[each_target.id] = canonical_prefix
    return local_alias_canonical_names


def check_tests_use_isolated_filesystem_paths(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag test functions that probe HOME or TMP without pytest isolation.

    Pattern class: tests that call ``Path.home()``, ``os.path.expanduser('~')``,
    ``os.getenv('HOME'|'USERPROFILE'|'TMPDIR'|…)``, ``os.environ['HOME'|…]``, or
    ``tempfile.gettempdir()`` against the real environment leak state across
    the suite and surface as environment-coupled bugs (audit Theme M).

    Test functions whose signatures take ``monkeypatch`` are treated as
    intentionally isolated and pass — ``monkeypatch.setenv('HOME', ...)``
    can intercept every env-derived probe, and this suppression applies
    uniformly to every probe type below. ``tmp_path`` / ``tmp_path_factory``
    / ``tmpdir`` / ``tmpdir_factory`` allocate alternative sandbox paths but
    do not intercept env reads, so their presence alone does not suppress
    the check. Module-level helpers and fixtures (any function whose name
    does not start with ``test_`` or ``should_``) are out of scope — only
    pytest-collectable ``def test_*`` / ``async def test_*`` / ``def
    should_*`` module-level or class-method functions are scanned.

    Covered forms (API surface × access form):
        Probe API surfaces — ``pathlib.Path.home()``,
        ``pathlib.Path('~...').expanduser()``, ``os.path.expanduser(arg)``,
        ``os.path.expandvars(arg)``, ``os.getenv(name)``,
        ``os.environ[name]``, ``os.environ.get(name)``, and the ``tempfile``
        allocators (``gettempdir``, ``gettempdirb``, ``gettempprefix``,
        ``mkstemp``, ``mkdtemp``, ``mktemp``, ``NamedTemporaryFile``,
        ``TemporaryFile``, ``TemporaryDirectory``, ``SpooledTemporaryFile``).
        Each surface is recognized through four access forms: (1) canonical
        dotted (``os.path.expanduser``), (2) module-level ``from X import
        name`` bare use (``from os import environ; environ['HOME']``),
        (3) module-level aliased import (``import tempfile as tf;
        tf.mkdtemp()``), and (4) a function-local binding tracked per test —
        either a function-local import (``def t(): from os import environ;
        environ['HOME']``) or a local rebinding (``path_class = Path;
        path_class.home()``; ``read_env = os.getenv; read_env('HOME')``). A
        function-local binding never leaks into a sibling test, so a same-named
        bare reference in another test that lacks its own binding does not fire.
        Gating is symmetric across the two ``expanduser`` forms (flag only on a
        leading-``~`` literal) and across the env getters / subscript (flag only
        on a home/temp env-var name). Probes are reported in source-line order
        for every probe type.

    Out of scope by design (dynamically constructed call targets that no
    AST-level pattern can resolve statically): attribute access through
    ``getattr(os, 'environ')``, callable names assembled at runtime by
    string concatenation, and calls built through ``exec``/``eval``. These
    bound the detector to a fixed, documented surface rather than an
    open-ended chase.

    Args:
        content: The Python source to analyze.
        file_path: The path of the file being checked. The check only fires
            on test files.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a probe
            blocks when any line of its enclosing test function's declared span
            (signature line through last body line) is among the changed lines,
            so editing the signature to remove an isolation fixture brings an
            unchanged-body probe into scope.
        defer_scope_to_caller: When True, return every probe so the commit/push
            gate's ``split_violations_by_scope`` can scope by added line and
            report the in-scope set.

    Returns:
        A list of issue strings naming each offending probe call. When
        *defer_scope_to_caller* is True every probe is returned for the gate to
        scope; otherwise every probe in scope is returned.
    """
    if not is_test_file(file_path):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    all_module_canonical_names_by_alias = _build_alias_canonicalization_map(syntax_tree)
    all_violations_in_source_line_order: list[tuple[range, str]] = []
    for each_node in _collect_pytest_collectable_test_functions(syntax_tree):
        if _function_uses_pytest_isolation_fixture(each_node):
            continue
        all_canonical_names_by_alias = {
            **all_module_canonical_names_by_alias,
            **_collect_local_probe_alias_bindings(each_node, all_module_canonical_names_by_alias),
        }
        all_environ_local_bindings = _collect_os_environ_local_binding_names(each_node, all_canonical_names_by_alias)
        all_path_local_bindings = _collect_pathlib_path_local_binding_names(each_node, all_canonical_names_by_alias)
        line_span = _function_definition_line_span(each_node)
        enclosing_function_span = range(each_node.lineno, each_node.lineno + line_span)
        for each_line, each_probe_label in _detect_home_or_temp_probes_in_body(
            each_node, all_canonical_names_by_alias, all_environ_local_bindings, all_path_local_bindings
        ):
            message = (
                f"Line {each_line}: Test {each_node.name!r} "
                f"(defined at line {each_node.lineno}, spanning {line_span} lines) "
                f"probes {each_probe_label} - {TEST_ISOLATION_MESSAGE_SUFFIX}"
            )
            all_violations_in_source_line_order.append(
                (enclosing_function_span, message)
            )
    return _scope_violations_to_changed_lines(
        all_violations_in_source_line_order,
        all_changed_lines,
        defer_scope_to_caller,
    )
