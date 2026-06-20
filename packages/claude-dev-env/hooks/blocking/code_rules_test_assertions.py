"""Skip-decorator, existence-only, constant-equality, stale-test-name, and flag-gated scenario test-quality checks."""

import ast
import sys
from pathlib import Path

_SCENARIO_NAME_CLAUSES = ("_when_", "_passes", "_succeeds", "_on_clean")
_MINIMUM_SIBLING_PATCH_COUNT = 2

_BLOCKING_DIRECTORY = str(Path(__file__).resolve().parent)
_HOOKS_DIRECTORY = str(Path(__file__).resolve().parent.parent)
if _BLOCKING_DIRECTORY not in sys.path:
    sys.path.insert(0, _BLOCKING_DIRECTORY)
if _HOOKS_DIRECTORY not in sys.path:
    sys.path.insert(0, _HOOKS_DIRECTORY)

from code_rules_shared import (  # noqa: E402
    is_test_file,
)

from hooks_constants.blocking_check_limits import (  # noqa: E402
    MAX_STALE_TEST_NAME_TARGET_ISSUES,
    STALE_TEST_NAME_MINIMUM_SHARED_TOKEN_COUNT,
)
from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    UPPER_SNAKE_CONSTANT_PATTERN,
)


def _decorator_name_contains_skip(decorator_node: ast.expr) -> bool:
    """Return True when a decorator AST node references an identifier containing 'skip'."""
    if isinstance(decorator_node, ast.Name):
        return "skip" in decorator_node.id.lower()
    if isinstance(decorator_node, ast.Attribute):
        return "skip" in decorator_node.attr.lower()
    if isinstance(decorator_node, ast.Call):
        return _decorator_name_contains_skip(decorator_node.func)
    return False


def check_skip_decorators_in_tests(content: str, file_path: str) -> list[str]:
    """Flag @skip decorators on test functions in test files.

    Tests must fail on missing dependencies rather than skip silently.
    Only applies to test files; production files are exempt.
    Only flags decorators applied to functions whose names start with 'test'.
    """
    if not is_test_file(file_path):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not each_node.name.startswith("test"):
            continue
        for each_decorator in each_node.decorator_list:
            if _decorator_name_contains_skip(each_decorator):
                issues.append(
                    f"Line {each_decorator.lineno}: @skip decorator on test"
                    f" — tests must fail on missing deps"
                )

    return issues


def _collect_assert_nodes_bounded(node: ast.AST) -> list[ast.Assert]:
    """Collect Assert nodes under node without crossing scope boundaries.

    Terminates descent at FunctionDef, AsyncFunctionDef, ClassDef, and Lambda
    nodes so that assertions belonging to nested scopes are not attributed to
    the enclosing function body.
    """
    scope_boundary_types = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
    assertions: list[ast.Assert] = []
    nodes_to_visit: list[ast.AST] = list(ast.iter_child_nodes(node))
    while nodes_to_visit:
        current = nodes_to_visit.pop()
        if isinstance(current, ast.Assert):
            assertions.append(current)
        if isinstance(current, scope_boundary_types):
            continue
        nodes_to_visit.extend(ast.iter_child_nodes(current))
    return assertions


def _collect_body_assertions(statement_nodes: list[ast.stmt]) -> list[ast.Assert]:
    """Collect Assert nodes from a function body without descending into nested scopes."""
    assertions: list[ast.Assert] = []
    for each_stmt in statement_nodes:
        if isinstance(each_stmt, ast.Assert):
            assertions.append(each_stmt)
            continue
        if isinstance(each_stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        assertions.extend(_collect_assert_nodes_bounded(each_stmt))
    return assertions


def _is_existence_only_assertion(call_node: ast.Call) -> bool:
    """Return True when a Call node is callable() or hasattr()."""
    function_reference = call_node.func
    if isinstance(function_reference, ast.Name):
        return function_reference.id in ("callable", "hasattr")
    if isinstance(function_reference, ast.Attribute):
        return function_reference.attr in ("callable", "hasattr")
    return False


def _test_body_has_only_existence_assertions(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Return True when a test function body contains only existence-check assertions."""
    assertion_nodes = _collect_body_assertions(function_node.body)
    if not assertion_nodes:
        return False

    non_existence_assertions = 0
    for each_assert in assertion_nodes:
        test_expr = each_assert.test
        if isinstance(test_expr, ast.Call) and _is_existence_only_assertion(test_expr):
            continue
        if isinstance(test_expr, ast.Compare):
            comparators = test_expr.comparators
            ops = test_expr.ops
            if (
                len(ops) == 1
                and isinstance(ops[0], ast.IsNot)
                and len(comparators) == 1
                and isinstance(comparators[0], ast.Constant)
                and comparators[0].value is None
            ):
                continue
        non_existence_assertions += 1

    return non_existence_assertions == 0


def check_existence_check_tests(content: str, file_path: str) -> list[str]:
    """Flag test functions containing only existence-check assertions.

    Tests asserting only callable(x), hasattr(m, 'name'), or x is not None
    verify nothing about behavior. They should be deleted or replaced with
    assertions that exercise actual functionality.
    Only applies to test files.
    """
    if not is_test_file(file_path):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not each_node.name.startswith("test"):
            continue
        if _test_body_has_only_existence_assertions(each_node):
            issues.append(
                f"Line {each_node.lineno}: existence-check test"
                f" — delete or replace with a behavior test"
            )

    return issues


def _is_upper_snake_name(name: str) -> bool:
    """Return True when an identifier is written in UPPER_SNAKE_CASE."""
    return bool(UPPER_SNAKE_CONSTANT_PATTERN.match(name))


def _assert_is_constant_equality_only(assert_node: ast.Assert) -> bool:
    """Return True when the assertion compares an UPPER_SNAKE name to a literal."""
    test_expr = assert_node.test
    if not isinstance(test_expr, ast.Compare):
        return False
    if len(test_expr.ops) != 1 or not isinstance(test_expr.ops[0], ast.Eq):
        return False
    left = test_expr.left
    right = test_expr.comparators[0]
    is_left_upper_snake = isinstance(left, ast.Name) and _is_upper_snake_name(left.id)
    is_right_upper_snake = isinstance(right, ast.Name) and _is_upper_snake_name(right.id)
    if is_left_upper_snake and is_right_upper_snake:
        return False
    is_left_a_literal = isinstance(left, ast.Constant)
    is_right_a_literal = isinstance(right, ast.Constant)
    return (
        (is_left_upper_snake and is_right_a_literal)
        or (is_right_upper_snake and is_left_a_literal)
    )


def check_constant_equality_tests(content: str, file_path: str) -> list[str]:
    """Flag test functions whose sole assertion compares a constant to a literal.

    Tests like 'assert CACHE_DIR == "cache"' cover no behavior — they just
    verify the constant has not changed. Such tests should be deleted.
    Only applies to test files; production files are exempt.
    """
    if not is_test_file(file_path):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    issues: list[str] = []
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not each_node.name.startswith("test"):
            continue
        all_assertions = _collect_body_assertions(each_node.body)
        if not all_assertions:
            continue
        if len(all_assertions) > 1:
            continue
        if _assert_is_constant_equality_only(all_assertions[0]):
            issues.append(
                f"Line {each_node.lineno}: constant-value test"
                f" — delete; tests must cover behavior"
            )

    return issues


def _flag_symbol_from_setattr_target(target_node: ast.expr) -> str | None:
    """Return the UPPER_SNAKE flag symbol a monkeypatch.setattr target names.

    Accepts both target shapes monkeypatch.setattr supports: a dotted string
    path (``"pkg.module.FLAG"``) and an attribute access (``module.FLAG``). The
    flag is the final dotted segment when that segment is UPPER_SNAKE_CASE; any
    other segment shape returns None so only module-level boolean flags qualify.

    Args:
        target_node: The first positional argument of a ``monkeypatch.setattr``
            call.

    Returns:
        The UPPER_SNAKE flag name, or None when the target names no such symbol.
    """
    if isinstance(target_node, ast.Constant) and isinstance(target_node.value, str):
        final_segment = target_node.value.rsplit(".", 1)[-1]
        return final_segment if _is_upper_snake_name(final_segment) else None
    if isinstance(target_node, ast.Attribute):
        return target_node.attr if _is_upper_snake_name(target_node.attr) else None
    return None


def _is_monkeypatch_setattr(call_node: ast.Call) -> bool:
    """Return True when a Call node is a ``monkeypatch.setattr(...)`` invocation."""
    function_reference = call_node.func
    return (
        isinstance(function_reference, ast.Attribute)
        and function_reference.attr == "setattr"
        and isinstance(function_reference.value, ast.Name)
        and function_reference.value.id == "monkeypatch"
    )


def _flags_patched_in_test(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Return the set of UPPER_SNAKE flag symbols a test patches via monkeypatch.setattr."""
    patched_flags: set[str] = set()
    for each_node in ast.walk(function_node):
        if not isinstance(each_node, ast.Call):
            continue
        if not _is_monkeypatch_setattr(each_node) or not each_node.args:
            continue
        flag_symbol = _flag_symbol_from_setattr_target(each_node.args[0])
        if flag_symbol is not None:
            patched_flags.add(flag_symbol)
    return patched_flags


def _name_encodes_scenario(test_name: str) -> bool:
    """Return True when a test name carries a scenario clause asserting a condition."""
    return any(each_clause in test_name for each_clause in _SCENARIO_NAME_CLAUSES)


def check_flag_gated_scenario_test_naming(content: str, file_path: str) -> list[str]:
    """Flag a scenario-named test that omits a flag its siblings establish.

    When two or more sibling tests in a file monkeypatch the same module-level
    UPPER_SNAKE flag, that flag governs which branch the code under test runs.
    A test whose name asserts a scenario (``_when_``, ``_passes``, ``_succeeds``,
    ``_on_clean``) but never patches that flag runs under the flag's default
    value, so its named condition may not be in effect — the audit category N
    test-name-scenario mismatch. Advisory only; emitted to stderr, never blocks.
    Only applies to test files; production files are exempt.

    Args:
        content: The file body under validation.
        file_path: Path to the file, used for the test-file gate.

    Returns:
        An empty list; advisories print to stderr so the write proceeds.
    """
    if not is_test_file(file_path):
        return []

    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    test_functions = [
        each_node
        for each_node in ast.walk(syntax_tree)
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and each_node.name.startswith("test")
    ]
    flags_patched_by_test = {
        each_test.name: _flags_patched_in_test(each_test) for each_test in test_functions
    }
    sibling_patch_count_by_flag: dict[str, int] = {}
    for patched_flags in flags_patched_by_test.values():
        for each_flag in patched_flags:
            sibling_patch_count_by_flag[each_flag] = (
                sibling_patch_count_by_flag.get(each_flag, 0) + 1
            )
    established_flags = {
        each_flag
        for each_flag, patch_count in sibling_patch_count_by_flag.items()
        if patch_count >= _MINIMUM_SIBLING_PATCH_COUNT
    }
    if not established_flags:
        return []

    for each_test in test_functions:
        if not _name_encodes_scenario(each_test.name):
            continue
        unpatched_flags = established_flags - flags_patched_by_test[each_test.name]
        if unpatched_flags:
            flag_list = ", ".join(sorted(unpatched_flags))
            print(
                f"ADVISORY [CODE_RULES] Line {each_test.lineno}: scenario test"
                f" {each_test.name!r} never patches {flag_list}, which sibling tests"
                f" establish — the named scenario may run under the flag default."
                f" Patch the flag (and assert the gated path runs) or rename the test.",
                file=sys.stderr,
            )

    return []


def _called_function_names(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Return the bare names of every function the test body calls."""
    called_names: set[str] = set()
    for each_node in ast.walk(function_node):
        if not isinstance(each_node, ast.Call):
            continue
        callee = each_node.func
        if isinstance(callee, ast.Name):
            called_names.add(callee.id)
        elif isinstance(callee, ast.Attribute):
            called_names.add(callee.attr)
    return called_names


def _module_known_callable_names(syntax_tree: ast.Module) -> set[str]:
    """Return every callable-like name the module imports, defines, or calls.

    A stale test name embeds a function that has been renamed away, so its name
    appears nowhere as a real symbol. This set is the universe of names that DO
    exist in the file, used to confirm the embedded name is absent.
    """
    known_names: set[str] = set()
    for each_node in ast.walk(syntax_tree):
        if isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            known_names.add(each_node.name)
        elif isinstance(each_node, ast.ImportFrom):
            for each_alias in each_node.names:
                known_names.add(each_alias.asname or each_alias.name)
        elif isinstance(each_node, ast.Import):
            for each_alias in each_node.names:
                known_names.add((each_alias.asname or each_alias.name).split(".")[0])
        elif isinstance(each_node, ast.Call):
            callee = each_node.func
            if isinstance(callee, ast.Name):
                known_names.add(callee.id)
            elif isinstance(callee, ast.Attribute):
                known_names.add(callee.attr)
    return known_names


def _leading_token_overlap(first_name: str, second_name: str) -> int:
    """Return how many leading underscore-separated tokens two names share."""
    first_tokens = first_name.split("_")
    second_tokens = second_name.split("_")
    shared = 0
    for first_token, second_token in zip(first_tokens, second_tokens):
        if first_token != second_token:
            break
        shared += 1
    return shared


def _renamed_sibling_for_candidate(candidate_name: str, called_names: set[str]) -> str | None:
    """Return a called function that looks like the renamed form of the candidate.

    A rename keeps the token count and the leading tokens but swaps one or more
    interior or trailing tokens (``collect_skip_theme_names`` to
    ``collect_skip_clean_names``). The match requires an equal token count and a
    shared leading run, which excludes an ordinary descriptive test suffix where
    the called function is a strict shorter prefix of the embedded name.
    """
    candidate_token_count = len(candidate_name.split("_"))
    for each_called in sorted(called_names):
        if each_called == candidate_name:
            continue
        if len(each_called.split("_")) != candidate_token_count:
            continue
        if (
            _leading_token_overlap(candidate_name, each_called)
            >= STALE_TEST_NAME_MINIMUM_SHARED_TOKEN_COUNT
        ):
            return each_called
    return None


def _embedded_target_candidates(test_name: str) -> list[str]:
    """Return the function-name candidates a test name embeds after its test_ prefix.

    For ``test_collect_skip_theme_names_keeps_only_sorted_at_risk`` the candidates
    are the successive leading runs ``collect_skip_theme_names``,
    ``collect_skip_theme``, ``collect_skip`` — longest first — so the embedded
    function name is matched before its shorter prefixes.
    """
    if not test_name.startswith("test_"):
        return []
    remainder_tokens = test_name[len("test_"):].split("_")
    candidates: list[str] = []
    for token_count in range(len(remainder_tokens), STALE_TEST_NAME_MINIMUM_SHARED_TOKEN_COUNT - 1, -1):
        candidates.append("_".join(remainder_tokens[:token_count]))
    return candidates


def check_stale_test_name_target(content: str, file_path: str) -> list[str]:
    """Flag a test whose name embeds a renamed-away function the body no longer calls.

    When a producer function is renamed (``collect_skip_theme_names`` to
    ``collect_skip_clean_names``) the test bodies are updated to call the new
    name but the test function identifiers keep the old one. The result is a test
    name advertising a function that exists nowhere in the file. This catches that
    Category N test-name-versus-scenario drift: a ``test_*`` name embeds a
    snake_case run of at least two tokens that names nothing the module imports,
    defines, or calls, while the same test body calls a function sharing the
    embedded run's leading tokens — the renamed sibling. Only applies to test
    files; production files are exempt.

    Args:
        content: The file body under validation.
        file_path: Path to the file, used for the test-file gate.

    Returns:
        One issue per test whose name embeds a renamed-away target, capped at the
        module limit.
    """
    if not is_test_file(file_path):
        return []
    try:
        syntax_tree = ast.parse(content)
    except SyntaxError:
        return []

    known_names = _module_known_callable_names(syntax_tree)
    issues: list[str] = []
    for each_node in ast.walk(syntax_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not each_node.name.startswith("test"):
            continue
        called_names = _called_function_names(each_node)
        for each_candidate in _embedded_target_candidates(each_node.name):
            if each_candidate in known_names:
                break
            renamed_sibling = _renamed_sibling_for_candidate(each_candidate, called_names)
            if renamed_sibling is None:
                continue
            issues.append(
                f"Line {each_node.lineno}: test {each_node.name!r} names "
                f"{each_candidate!r}, which the file never imports, defines, or calls; "
                f"the body calls {renamed_sibling!r} instead — rename the test to match "
                "the function it exercises (Category N test-name-vs-scenario drift)"
            )
            if len(issues) >= MAX_STALE_TEST_NAME_TARGET_ISSUES:
                return issues[:MAX_STALE_TEST_NAME_TARGET_ISSUES]
            break

    return issues[:MAX_STALE_TEST_NAME_TARGET_ISSUES]
