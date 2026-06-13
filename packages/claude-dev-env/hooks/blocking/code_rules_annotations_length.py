"""Parameter-annotation, return-annotation, and function-length checks."""

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
    _collect_annotated_arguments,
    _collect_fixture_injection_arguments,
    _definition_docstring_line_span,
    _function_definition_line_span,
    _scope_violations_to_changed_lines,
    is_hook_infrastructure,
    is_migration_file,
    is_test_file,
    is_workflow_registry_file,
)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_SELF_AND_CLS_PARAMETER_NAMES,
    ANNOTATION_BY_PYTEST_FIXTURE,
    FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX,
    FUNCTION_LENGTH_BLOCKING_THRESHOLD,
    KNOWN_PYTEST_FIXTURE_ANNOTATION_MESSAGE_SUFFIX,
)


def check_parameter_annotations(content: str, file_path: str) -> list[str]:
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
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for each_arg in _collect_annotated_arguments(each_node):
            if each_arg.arg in ALL_SELF_AND_CLS_PARAMETER_NAMES:
                continue
            if each_arg.annotation is None:
                issues.append(
                    f"Line {each_arg.lineno}: parameter {each_arg.arg!r} on {each_node.name!r} missing type annotation (CODE_RULES §6)"
                )
    return issues


def _is_pytest_fixture_injection_site(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> bool:
    """Return True when a function node is a valid pytest fixture injection site.

    A function qualifies as a fixture injection site when either its name begins
    with the ``test`` prefix (matching pytest's default ``python_functions = test*``
    collection rule) or it carries a ``@pytest.fixture`` / ``@fixture`` decorator,
    with or without call arguments.  Ordinary helper functions that happen to share
    a parameter name with a known pytest fixture are excluded by this predicate so
    that ``check_known_pytest_fixture_annotations`` only enforces annotation
    requirements on the functions where pytest actually performs fixture injection.

    Args:
        node: The function definition AST node to inspect.

    Returns:
        True when the node is a pytest test function or a fixture-decorated
        function; False otherwise.
    """
    if node.name.startswith("test"):
        return True
    for each_decorator in node.decorator_list:
        unwrapped = each_decorator.func if isinstance(each_decorator, ast.Call) else each_decorator
        if isinstance(unwrapped, ast.Name) and unwrapped.id == "fixture":
            return True
        if isinstance(unwrapped, ast.Attribute) and unwrapped.attr == "fixture":
            return True
    return False


def _normalize_fixture_annotation_text(annotation_text: str) -> str:
    """Strip forward-reference string quoting from an unparsed annotation.

    ``ast.unparse`` renders a forward-reference annotation such as
    ``tmp_path: "Path"`` as the quoted literal ``'Path'``. Removing the
    surrounding quotes recovers the bare type name so the quoted spelling
    compares equal to its unquoted form.

    Args:
        annotation_text: The annotation as rendered by ``ast.unparse``.

    Returns:
        The annotation text with any single surrounding quote pair removed.
    """
    if len(annotation_text) >= 2 and annotation_text[0] in {'"', "'"}:
        if annotation_text[-1] == annotation_text[0]:
            return annotation_text[1:-1]
    return annotation_text


def _fixture_annotation_matches_expected(
    actual_annotation: str, expected_annotation: str
) -> bool:
    """Return True when an annotation matches its fixture's documented type.

    The match accepts every equally-correct spelling of the documented type:
    the exact text, a forward-reference string form, and either the bare
    attribute tail or the fully-qualified dotted form. Both ``tmp_path: Path``
    and ``tmp_path: pathlib.Path`` satisfy an expected ``Path``, and both
    ``monkeypatch: pytest.MonkeyPatch`` and ``monkeypatch: MonkeyPatch``
    satisfy an expected ``pytest.MonkeyPatch``.

    Args:
        actual_annotation: The annotation as rendered by ``ast.unparse``.
        expected_annotation: The fixture's single documented type spelling.

    Returns:
        True when the actual annotation is an accepted spelling of the
        expected type; False otherwise.
    """
    normalized_actual = _normalize_fixture_annotation_text(actual_annotation)
    if normalized_actual == expected_annotation:
        return True
    return normalized_actual.rsplit(".", 1)[-1] == expected_annotation.rsplit(
        ".", 1
    )[-1]


def check_known_pytest_fixture_annotations(content: str, file_path: str) -> list[str]:
    """Flag well-known pytest fixture parameters lacking their type annotation.

    The broad parameter-annotation rule exempts test files, so an ordinary
    test parameter never needs a type hint. This narrower check restores
    enforcement for exactly the pytest builtin fixtures whose injected type is
    fixed and documented — ``tmp_path: Path``, ``monkeypatch:
    pytest.MonkeyPatch``, and the rest of
    ``ANNOTATION_BY_PYTEST_FIXTURE``. For these names the
    correct annotation is unambiguous, so requiring it costs the author one
    token and removes a recurring class of reviewer noise on test fixtures.
    A non-test file produces no findings here: the broad check already covers
    every parameter outside test files.

    A known fixture parameter is flagged both when it carries no annotation and
    when its annotation source differs from the fixture's single documented
    type, so ``tmp_path: str`` is flagged exactly like ``tmp_path``. Only the
    named injection slots pytest actually fills — undefaulted
    positional-or-keyword and keyword-only parameters — are inspected. A
    positional-only parameter is skipped because pytest passes fixtures by
    keyword and can never bind one positionally; a defaulted parameter is
    skipped because pytest leaves its default in place rather than injecting a
    fixture; and a ``*args`` or ``**kwargs`` parameter that happens to share a
    fixture name is never a fixture injection.

    Args:
        content: The Python source to analyze.
        file_path: The path of the file being checked.

    Returns:
        One blocking issue per known fixture injection parameter whose
        annotation is missing or differs from its single documented type,
        naming the parameter and its expected type.
    """
    if not is_test_file(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    issues: list[str] = []
    for each_node in ast.walk(tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not _is_pytest_fixture_injection_site(each_node):
            continue
        for each_arg in _collect_fixture_injection_arguments(each_node):
            expected_annotation = ANNOTATION_BY_PYTEST_FIXTURE.get(
                each_arg.arg
            )
            if expected_annotation is None:
                continue
            actual_annotation = (
                ast.unparse(each_arg.annotation)
                if each_arg.annotation is not None
                else None
            )
            if actual_annotation is not None and _fixture_annotation_matches_expected(
                actual_annotation, expected_annotation
            ):
                continue
            issues.append(
                f"Line {each_arg.lineno}: parameter {each_arg.arg!r} on "
                f"{each_node.name!r} - {KNOWN_PYTEST_FIXTURE_ANNOTATION_MESSAGE_SUFFIX} "
                f"(annotate as {expected_annotation!r})"
            )
    return issues


def check_return_annotations(content: str, file_path: str) -> list[str]:
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
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if each_node.returns is None:
            issues.append(
                f"Line {each_node.lineno}: function {each_node.name!r} missing return type annotation (CODE_RULES §6)"
            )
    return issues


def check_function_length(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag functions whose executable span exceeds cognitive-load thresholds.

    Function executable spans — the definition span (signature line through
    last body statement, inclusive) minus the leading docstring lines of the
    function and of every function or class nested within it, per
    ``_definition_docstring_line_span`` summed over the nested definitions —
    at or above ``FUNCTION_LENGTH_BLOCKING_THRESHOLD`` appear in
    the returned issues list and block the write at the
    gate. The threshold rests on the small-function guidance in Robert C.
    Martin, *Clean Code* Chapter Three ("Functions") and the Google Python Style
    Guide's ~forty-line function review hint
    (https://google.github.io/styleguide/pyguide.html) — a measure of
    executable complexity, paired with the Guide's complete-docstring mandate
    for public APIs, so documentation lines never count against the gate; this
    gate blocks on body growth that pushes a function past that span. It does
    not derive from CODE_RULES file-length guidance, which governs advisory
    file-length signals and argues against hard numeric blocks.

    The issue message carries ``Function NAME (defined at line X) is Y lines``
    precisely so the gate's ``function_length_span_range`` can recover the
    function's full declared span (lines ``X`` through ``X + Y - 1``). The
    gate classifies the violation blocking when that span intersects the
    diff's added lines — the body grew this diff — and advisory otherwise — a
    pre-existing, untouched long function in a file the diff happened to
    touch. Anchoring to the span rather than a single ``Line N:`` definition
    line lets body growth on any interior line block correctly even when the
    ``def`` line itself is untouched.

    Exempt: test files (test bodies are sometimes long by necessity), Django
    migrations (auto-generated), workflow registries (registry entries), and
    hook infrastructure.

    Args:
        content: The Python source to analyze.
        file_path: The path of the file being checked.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a violation
            blocks only when the function's declared span intersects the changed
            lines.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate's ``split_violations_by_scope`` can scope by added
            line and report the in-scope set.

    Returns:
        Blocking issues. When *defer_scope_to_caller* is True every violation is
        returned for the gate to scope; otherwise every violation in scope is
        returned.
    """
    if is_test_file(file_path):
        return []
    if is_hook_infrastructure(file_path):
        return []
    if is_workflow_registry_file(file_path) or is_migration_file(file_path):
        return []

    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return []

    all_violations_in_walk_order: list[tuple[range, str]] = []
    for each_node in ast.walk(parsed_tree):
        if not isinstance(each_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        line_span = _function_definition_line_span(each_node)
        if line_span < FUNCTION_LENGTH_BLOCKING_THRESHOLD:
            continue
        docstring_line_total = sum(
            _definition_docstring_line_span(each_definition)
            for each_definition in ast.walk(each_node)
            if isinstance(
                each_definition, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
            )
        )
        executable_line_span = line_span - docstring_line_total
        if executable_line_span >= FUNCTION_LENGTH_BLOCKING_THRESHOLD:
            span_range = range(each_node.lineno, each_node.lineno + line_span)
            message = (
                f"Function {each_node.name!r} (defined at line {each_node.lineno}) "
                f"is {line_span} lines - {FUNCTION_LENGTH_BLOCKING_MESSAGE_SUFFIX}"
            )
            all_violations_in_walk_order.append((span_range, message))
    return _scope_violations_to_changed_lines(
        all_violations_in_walk_order,
        all_changed_lines,
        defer_scope_to_caller,
    )
