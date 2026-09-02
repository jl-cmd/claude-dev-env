"""Duplicate top-level function body detection.

``check_duplicate_function_body_across_files`` flags a top-level function in the
file being written whose body is structurally identical to a top-level function
already defined in a sibling ``.py`` module in the same directory.
``check_same_file_inline_duplicate_body`` flags a top-level function whose body
appears verbatim as a contiguous statement block inside another function in the
same file — the inlined-block copy the cross-file whole-function comparison
misses. Both catch the Reuse-before-create / DRY violation where a block of logic
is copied instead of called from one shared home, so a fix that lands in one copy
leaves the other carrying the bug.

The scans are deliberately conservative to keep false positives near zero:

- Only module-scope ``def`` / ``async def`` bodies are compared (the copied-helper
  case), never methods nested in a class.
- The cross-file scan compares whole bodies by their normalized AST structure
  with the leading docstring dropped, keeping identifier names, so a match
  requires the body statements — local variable names included — to be
  structurally identical; it ignores the parameter list, decorators, and whether
  the function is ``async``, and a body must hold at least
  ``MINIMUM_DUPLICATE_BODY_STATEMENTS`` statements.
- The same-file inline scan trims a helper's leading ``assert`` preconditions and
  drops its docstring, then seeks the remaining window verbatim inside another
  function's reachable statement blocks. String-literal constants are canonicalized
  before comparison, so two blocks that differ only in a logging or error message
  still collide, while the window must hold a substantial compound statement
  (``try``, ``for``, ``while``, ``with``) and sit inside a strictly larger,
  non-twin enclosing body. A bare ``if`` guard, a flat run, and a structural-twin
  peer helper never flag.
- Test files and ``__init__.py`` re-export surfaces never participate, on either
  the writing side or the sibling side.

Unlike most code-rules checks, these run on hook-infrastructure files: the
copied-block violation they target appears often in the ``blocking/`` hook
directory itself, so gating them behind the hook-infrastructure exemption would
leave the exact violation class unguarded. The enforcer entry points route a
hook ``.py`` target to both checks even though the full code-rules verdict stays
off hook infrastructure, so a Write or pre-check against a file under the
``blocking/`` directory still blocks a copied sibling helper and an inlined
helper body.

``advise_cross_skill_duplicate_helper`` is the non-blocking companion for a
different layout: a helper copied between two skills' ``scripts`` directories.
Two skill folders install on their own, so a shared module would break
independent install and a same-directory block would be a false positive on a
sanctioned skill-isolation copy. The advisory prints a ``[CODE_RULES advisory]``
line to stderr naming the source skill and function so a reviewer confirms the
copy is intentional, and never enters the deny path. It fires only across skill
folders; within one skill the blocking check above already covers the copy.
"""

import ast
import copy
import sys
from pathlib import Path
from typing import NamedTuple

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_shared import (  # noqa: E402
    _scope_violations_to_changed_lines,
    is_test_file,
)

from hooks_constants.duplicate_function_body_constants import (  # noqa: E402
    CROSS_SKILL_ADVISORY_PREFIX,
    CROSS_SKILL_DUPLICATE_GUIDANCE,
    DUNDER_INIT_FILENAME,
    DUPLICATE_BODY_GUIDANCE,
    MAX_CROSS_SKILL_ADVISORY_ISSUES,
    MAX_DUPLICATE_BODY_ISSUES,
    MINIMUM_DUPLICATE_BODY_STATEMENTS,
    MINIMUM_INLINE_DUPLICATE_BODY_STATEMENTS,
    PYTHON_SOURCE_SUFFIX,
    SAME_FILE_INLINE_DUPLICATE_GUIDANCE,
    SAME_FILE_INLINE_DUPLICATE_SPAN_SUFFIX_TEMPLATE,
    SKILL_SCRIPTS_DIRECTORY_NAME,
    SKILLS_DIRECTORY_NAME,
)


_ModuleScopeFunction = ast.FunctionDef | ast.AsyncFunctionDef


class _FunctionScanProfile(NamedTuple):
    """The three readings of one module-scope function the inline scan compares.

    Every reading is a property of that function alone, so each is taken once per
    file and read by each pairing the scan weighs.
    """

    reachable_statement_count: int
    all_sorted_body_dumps: list[str]
    all_block_dumps: list[list[str]]


def _body_statements_without_docstring(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.stmt]:
    """Return the function's top-level body statements with a leading docstring dropped.

    A function whose first statement is a bare string-literal expression carries a
    docstring; that statement is omitted so two copies that differ only in their
    docstring compare equal. A function with no leading docstring returns its body
    unchanged.

    Args:
        function_node: The module-scope function whose body to read.

    Returns:
        The top-level body statements, excluding a leading docstring expression.
    """
    body_statements = list(function_node.body)
    if body_statements and isinstance(body_statements[0], ast.Expr):
        first_value = body_statements[0].value
        if isinstance(first_value, ast.Constant) and isinstance(first_value.value, str):
            return body_statements[1:]
    return body_statements


def _normalized_body_signature(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Return a position-independent structural fingerprint of the function body.

    The docstring statement, when present, is dropped so two copies that differ
    only in their docstring still collide. Returns None when the remaining body
    is shorter than the minimum statement count, which signals the caller to skip
    this function as too trivial to be a meaningful duplicate.

    Args:
        function_node: The module-scope function definition to fingerprint.

    Returns:
        A normalized AST dump of the body statements, or None when the body is
        too small to compare.
    """
    body_statements = _body_statements_without_docstring(function_node)
    if len(body_statements) < MINIMUM_DUPLICATE_BODY_STATEMENTS:
        return None
    return "\n".join(
        ast.dump(each_statement, annotate_fields=False) for each_statement in body_statements
    )


def _top_level_function_signatures(tree: ast.Module) -> dict[str, str]:
    """Map each module-scope function name to its normalized body signature.

    Functions whose body is too trivial to compare are omitted.

    Args:
        tree: The parsed module.

    Returns:
        A name-to-signature mapping for the comparable top-level functions.
    """
    signature_by_name: dict[str, str] = {}
    for each_node in tree.body:
        if isinstance(each_node, ast.FunctionDef | ast.AsyncFunctionDef):
            body_signature = _normalized_body_signature(each_node)
            if body_signature is not None:
                signature_by_name[each_node.name] = body_signature
    return signature_by_name


def _function_definition_span(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> range:
    """Return the inclusive 1-indexed source-line span of a function definition.

    Args:
        function_node: The module-scope function definition.

    Returns:
        A range covering the signature line through the last body line, so a
        changed-line set intersects the span when an edit touches any line of the
        function — mirroring the span scoping the sibling whole-file checks use.
    """
    last_line = function_node.end_lineno or function_node.lineno
    return range(function_node.lineno, last_line + 1)


def _top_level_function_signature_spans(
    tree: ast.Module,
) -> dict[str, tuple[str, range]]:
    """Map each comparable module-scope function to its signature and source span.

    Functions whose body is too trivial to compare are omitted.

    Args:
        tree: The parsed module being written.

    Returns:
        A name-to-``(signature, span)`` mapping for the comparable top-level
        functions, where the span covers the function's source lines.
    """
    signature_span_by_name: dict[str, tuple[str, range]] = {}
    for each_node in tree.body:
        if isinstance(each_node, ast.FunctionDef | ast.AsyncFunctionDef):
            body_signature = _normalized_body_signature(each_node)
            if body_signature is not None:
                signature_span_by_name[each_node.name] = (
                    body_signature,
                    _function_definition_span(each_node),
                )
    return signature_span_by_name


def _is_comparable_sibling(sibling_path: Path, written_file_name: str) -> bool:
    """Return whether a directory entry is a sibling module worth comparing against.

    Args:
        sibling_path: A candidate path from the written file's directory.
        written_file_name: The base name of the file being written.

    Returns:
        True for a Python source file other than the written file itself,
        excluding ``__init__.py`` and test modules.
    """
    if not sibling_path.is_file():
        return False
    if sibling_path.suffix != PYTHON_SOURCE_SUFFIX:
        return False
    if sibling_path.name == written_file_name:
        return False
    if sibling_path.name == DUNDER_INIT_FILENAME:
        return False
    return not is_test_file(sibling_path.name)


def _sibling_signatures(
    file_path: str,
    sibling_directory: Path | None = None,
) -> dict[str, list[str]]:
    """Collect normalized body signatures from every comparable sibling module.

    Args:
        file_path: The path of the file being written.
        sibling_directory: An absolute directory to scan for sibling modules.
            When None, the directory is derived from ``file_path``'s parent,
            which resolves against the process CWD for a relative ``file_path``.
            The commit/push gate passes the resolved file's parent so sibling
            resolution stays anchored to the repository regardless of the gate
            process's working directory.

    Returns:
        A signature-to-source-names mapping, where the value lists the
        ``module.py::function`` locations carrying that body.
    """
    written_path = Path(file_path)
    directory = written_path.parent if sibling_directory is None else sibling_directory
    source_names_by_signature: dict[str, list[str]] = {}
    try:
        all_entries = sorted(directory.iterdir())
    except OSError:
        return {}
    for each_entry in all_entries:
        if not _is_comparable_sibling(each_entry, written_path.name):
            continue
        try:
            sibling_source = each_entry.read_text(encoding="utf-8")
            sibling_tree = ast.parse(sibling_source)
        except (OSError, UnicodeDecodeError, SyntaxError):
            continue
        for each_name, each_signature in _top_level_function_signatures(sibling_tree).items():
            location = f"{each_entry.name}::{each_name}"
            source_names_by_signature.setdefault(each_signature, []).append(location)
    return source_names_by_signature


def check_duplicate_function_body_across_files(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
    sibling_directory: Path | None = None,
) -> list[str]:
    """Flag top-level functions copied byte-for-structure from a sibling module.

    Compares each module-scope function in the post-edit content against the
    top-level functions of every comparable ``.py`` sibling in the same
    directory, and reports any whose normalized body matches. Test files and
    ``__init__.py`` are skipped on both sides.

    Violations are scoped to the lines an edit touched the same way the sibling
    whole-file checks scope theirs: an Edit blocks only on a duplicated function
    whose source span intersects the changed lines, so an unrelated edit to a
    file that already carries a byte-identical entrypoint shim in a sibling
    module does not block, while a Write that newly copies a sibling helper still
    flags because every line is in scope.

    Unlike the sibling whole-file checks, this check carries no
    ``is_hook_infrastructure`` exemption: the copied-helper violation it targets
    appears most often in the ``blocking/`` hook directory itself.

    Args:
        content: The full post-edit file content being written.
        file_path: The destination path of the write.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a violation
            blocks only when the duplicated function's source span intersects the
            changed lines.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate's ``split_violations_by_scope`` can scope by added
            line.
        sibling_directory: An absolute directory to scan for sibling modules.
            When None, the directory is derived from ``file_path``'s parent. The
            PreToolUse path leaves this None because its ``file_path`` is already
            absolute; the commit/push gate passes the resolved file's parent so
            the sibling scan stays anchored to the repository regardless of the
            gate process's working directory.

    Returns:
        Human-readable violation strings, one per duplicated function, scoped to
        the changed lines unless *defer_scope_to_caller* is True or
        *all_changed_lines* is None.
    """
    written_name = Path(file_path).name
    if written_name == DUNDER_INIT_FILENAME:
        return []
    if is_test_file(file_path):
        return []
    try:
        written_tree = ast.parse(content)
    except SyntaxError:
        return []
    written_signature_spans = _top_level_function_signature_spans(written_tree)
    if not written_signature_spans:
        return []
    source_names_by_signature = _sibling_signatures(file_path, sibling_directory)
    all_violations_in_walk_order: list[tuple[range, str]] = []
    for each_name, (each_signature, each_span) in written_signature_spans.items():
        matching_locations = source_names_by_signature.get(each_signature)
        if not matching_locations:
            continue
        first_location = matching_locations[0]
        message = (
            f"Function {each_name!r} duplicates {first_location} — {DUPLICATE_BODY_GUIDANCE} "
            f"(duplicate body span at line {each_span.start}, spanning {len(each_span)} lines)"
        )
        all_violations_in_walk_order.append((each_span, message))
        if len(all_violations_in_walk_order) >= MAX_DUPLICATE_BODY_ISSUES:
            break
    return _scope_violations_to_changed_lines(
        all_violations_in_walk_order,
        all_changed_lines,
        defer_scope_to_caller,
    )


class _StringConstantCanonicalizer(ast.NodeTransformer):
    """Rewrite every string-literal constant to one placeholder.

    Two copied blocks most often differ only in a message string — a logging or
    error suffix the author tweaked while leaving the call, selector, and control
    structure identical. Canonicalizing string constants before dumping lets such
    blocks collide while a different call target, selector, or numeric constant
    still keeps two blocks distinct. Non-string constants (numbers, ``None``,
    booleans) are left untouched so a genuine value difference stays visible.
    """

    def visit_Constant(self, node: ast.Constant) -> ast.Constant:
        """Replace a string-valued constant with a fixed placeholder string.

        Args:
            node: The constant node under transformation.

        Returns:
            A placeholder constant for a string value, or the node unchanged for
            any non-string constant.
        """
        if isinstance(node.value, str):
            return ast.copy_location(ast.Constant(value=""), node)
        return node


def _normalized_statement_dump(statement: ast.stmt) -> str:
    """Return the normalized AST dump of one statement.

    Canonicalizes every string-literal constant to one placeholder before
    dumping, so two statements that differ only in a message string still produce
    the same dump. The call structure, selectors, exception handlers, and numeric
    constants are preserved, so a genuine logic difference still keeps two
    statements distinct.

    Args:
        statement: The statement node to fingerprint.

    Returns:
        The annotate-fields-suppressed AST dump of the statement after string
        constants are canonicalized.
    """
    canonical_statement = _StringConstantCanonicalizer().visit(
        copy.deepcopy(statement)
    )
    return ast.dump(canonical_statement, annotate_fields=False)


def _memoized_statement_dump(
    statement: ast.stmt,
    dump_by_statement: dict[ast.stmt, str],
) -> str:
    """Return the normalized dump of one statement, computing it at most once.

    The inline scan reads the same statement's dump many times over: once for its
    enclosing function's block window, once for that function's twin-test
    multiset, and again for every helper the function is weighed against. Dumping
    deep-copies the statement subtree before canonicalizing string constants, so
    this memo serves the repeat reads.

    An ``ast`` node defines no ``__eq__``, so the key is the node's identity and
    the dict holds a strong reference to it: a key cannot be freed and a later
    node cannot reuse its slot. The caller owns one memo per scanned file and
    drops it when the scan returns, so no entry outlives its parse tree.

    Args:
        statement: The statement node to fingerprint.
        dump_by_statement: The file's statement-to-dump memo, mutated in place.

    Returns:
        The value ``_normalized_statement_dump`` returns for this statement.
    """
    memoized_dump = dump_by_statement.get(statement)
    if memoized_dump is None:
        memoized_dump = _normalized_statement_dump(statement)
        dump_by_statement[statement] = memoized_dump
    return memoized_dump


def _statement_blocks_in_function(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[list[ast.stmt]]:
    """Return every statement list reachable inside a function body.

    A copied helper body can sit at the function's top level or nested inside a
    branch, loop, or context block, so the inline-duplicate scan walks each nested
    statement list as its own window source. The function's own immediate body is
    the first block; every nested block (``If`` arms, ``For``/``While`` bodies,
    ``With``/``Try`` bodies and handlers) follows.

    Args:
        function_node: The module-scope function whose blocks to collect.

    Returns:
        A list of statement lists, one per reachable block in the function.
    """
    all_blocks: list[list[ast.stmt]] = []
    for each_node in ast.walk(function_node):
        for each_field_name in ("body", "orelse", "finalbody"):
            block = getattr(each_node, each_field_name, None)
            if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
                all_blocks.append(block)
        for each_handler in getattr(each_node, "handlers", []) or []:
            if isinstance(each_handler, ast.ExceptHandler):
                all_blocks.append(each_handler.body)
    return all_blocks


def _total_reachable_statement_count(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int:
    """Return the count of every statement reachable inside the function body.

    Walks the function's immediate body and every nested block — ``If`` arms,
    loop and context bodies, ``Try`` bodies and handlers and ``finalbody`` — so a
    duplicated window wrapped inside a single top-level compound (a ``try``/
    ``finally`` cleanup or one ``if`` guard) still counts the statements the window
    occupies plus the statements around it. The leading docstring is excluded from
    the immediate body so a docstring does not inflate the count.

    Args:
        function_node: The function whose reachable statements to count.

    Returns:
        The number of statements reachable in the function, excluding a leading
        docstring expression.
    """
    has_leading_docstring = len(_body_statements_without_docstring(function_node)) < len(
        function_node.body
    )
    total_statement_count = sum(
        1 for each_node in ast.walk(function_node) if isinstance(each_node, ast.stmt)
    )
    if has_leading_docstring:
        return total_statement_count - 1
    return total_statement_count


def _helper_match_window_dumps(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
    dump_by_statement: dict[ast.stmt, str],
) -> list[str] | None:
    """Return the helper's substantive block as per-statement dumps, or None.

    Drops a leading docstring the same way ``_normalized_body_signature`` does,
    then trims leading ``assert`` precondition guards so the match window begins at
    the helper's first non-assert statement. A helper commonly wraps a copied block
    in its own ``assert`` precondition, so trimming those lets the helper's
    substantive block match the same block inlined elsewhere without the guard.
    Only ``assert`` is trimmed — a leading assignment or call carries data the
    duplicate must share, so trimming it would expose a generic tail and match
    unrelated peer helpers.

    The window must hold at least ``MINIMUM_INLINE_DUPLICATE_BODY_STATEMENTS``
    statements and must contain a substantial compound statement — a ``try``,
    ``for``, ``while``, or ``with`` block. A run of flat statements, and a bare
    ``if`` guard (an idiomatic strict-vs-optional validator pair where one wraps a
    ``None`` check around the other's ``if ...: raise`` narrow), are too common to
    be a meaningful inline duplicate and never flag, while a duplicated
    ``try``/``except`` or loop block — the substantial control structure worth a
    shared helper — does.

    Args:
        function_node: The module-scope function to treat as a candidate helper.

    Returns:
        The per-statement normalized dumps of the helper's substantive block, or
        None when it has no compound statement or is shorter than the minimum.
    """
    body_statements = _body_statements_without_docstring(function_node)
    first_non_assert_index = next(
        (
            each_index
            for each_index, each_statement in enumerate(body_statements)
            if not isinstance(each_statement, ast.Assert)
        ),
        None,
    )
    if first_non_assert_index is None:
        return None
    match_window = body_statements[first_non_assert_index:]
    if len(match_window) < MINIMUM_INLINE_DUPLICATE_BODY_STATEMENTS:
        return None
    substantial_compound_statement_types = (ast.Try, ast.For, ast.While, ast.With)
    has_substantial_compound = any(
        isinstance(each, substantial_compound_statement_types)
        for each in match_window
    )
    if not has_substantial_compound:
        return None
    return [
        _memoized_statement_dump(each_statement, dump_by_statement)
        for each_statement in match_window
    ]


def check_same_file_inline_duplicate_body(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag a module-scope helper whose body is inlined inside another function.

    Compares each module-scope function's body against every other module-scope
    function in the same file, reporting any helper whose body appears verbatim as
    a contiguous statement block inside another function. This is the same-file
    counterpart to ``check_duplicate_function_body_across_files``, which only
    compares whole functions across sibling modules and so misses a helper that
    duplicates a block already inlined in a same-file function.

    Violations are span-scoped to the lines an edit touched the same way the
    cross-file check scopes its own: a violation blocks when either the helper's
    span or the enclosing function's span intersects the changed lines, so an
    unrelated edit to a file that already carries the duplication does not block,
    while a Write or an edit touching either function still flags.

    Args:
        content: The full post-edit file content being written.
        file_path: The destination path of the write.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat the whole file as in scope. When provided, a violation
            blocks only when the helper's span or the enclosing function's span
            intersects the changed lines.
        defer_scope_to_caller: When True, return every violation so the commit/push
            gate's ``split_violations_by_scope`` can scope by added line.

    Returns:
        Human-readable violation strings, one per inlined-duplicate helper, scoped
        to the changed lines unless *defer_scope_to_caller* is True or
        *all_changed_lines* is None.
    """
    if Path(file_path).name == DUNDER_INIT_FILENAME:
        return []
    if is_test_file(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    all_top_level_functions = [
        each_node
        for each_node in tree.body
        if isinstance(each_node, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    return _scope_violations_to_changed_lines(
        _inline_duplicate_violations(all_top_level_functions, MAX_DUPLICATE_BODY_ISSUES),
        all_changed_lines,
        defer_scope_to_caller,
    )


def _block_dumps_in_function(
    function_node: _ModuleScopeFunction,
    dump_by_statement: dict[ast.stmt, str],
) -> list[list[str]]:
    """Return the per-statement dumps of each reachable block in a function.

    Args:
        function_node: The module-scope function to read.
        dump_by_statement: The file's statement-to-dump memo, mutated in place.

    Returns:
        One dump list per reachable block, in block-collection order.
    """
    return [
        [
            _memoized_statement_dump(each_statement, dump_by_statement)
            for each_statement in each_block
        ]
        for each_block in _statement_blocks_in_function(function_node)
    ]


def _function_scan_profile(
    function_node: _ModuleScopeFunction,
    dump_by_statement: dict[ast.stmt, str],
) -> _FunctionScanProfile:
    """Take the three readings the inline scan needs from one function.

    The sorted body dumps carry the docstring-stripped statement multiset that
    tests whether two functions are structural twins. Sorting makes that
    comparison order-independent, so two peer helpers that read different inputs
    but share the same statement shapes compare equal and are left to the
    cross-file check.

    Args:
        function_node: The module-scope function to read.
        dump_by_statement: The file's statement-to-dump memo, mutated in place.

    Returns:
        The function's reachable statement count, sorted body dumps, and
        per-block statement dumps.
    """
    return _FunctionScanProfile(
        reachable_statement_count=_total_reachable_statement_count(function_node),
        all_sorted_body_dumps=sorted(
            _memoized_statement_dump(each_statement, dump_by_statement)
            for each_statement in _body_statements_without_docstring(function_node)
        ),
        all_block_dumps=_block_dumps_in_function(function_node, dump_by_statement),
    )


def _block_dumps_contain_window(
    all_block_dumps: list[str],
    all_window_dumps: list[str],
) -> bool:
    """Return whether one block carries the window as a contiguous run.

    A block shorter than the window holds no run and answers False.

    Args:
        all_block_dumps: One reachable block's per-statement dumps.
        all_window_dumps: The helper's window dumps to seek.

    Returns:
        True when the window appears in the block as a contiguous run.
    """
    window_length = len(all_window_dumps)
    last_start_index = len(all_block_dumps) - window_length
    for each_start_index in range(last_start_index + 1):
        window_end = each_start_index + window_length
        if all_block_dumps[each_start_index:window_end] == all_window_dumps:
            return True
    return False


def _profile_inlines_window(
    helper_profile: _FunctionScanProfile,
    enclosing_profile: _FunctionScanProfile,
    all_helper_window_dumps: list[str],
) -> bool:
    """Return whether a function inlines a helper window inside a larger body.

    A run inside one of the enclosing function's reachable blocks whose dumps
    match the helper's, in order, is the inlined copy. Two guards hold the report
    to a genuine inlining: the enclosing function carries more reachable
    statements than the window, and the two functions are not structural twins,
    so peer helpers sharing a statement shape are left to the cross-file check.

    Args:
        helper_profile: The candidate helper's readings, for the twin guard.
        enclosing_profile: The candidate enclosing function's readings.
        all_helper_window_dumps: The helper's substantive-block statement dumps.

    Returns:
        True when a block carries the window inside a larger, non-twin body.
    """
    if enclosing_profile.reachable_statement_count <= len(all_helper_window_dumps):
        return False
    if helper_profile.all_sorted_body_dumps == enclosing_profile.all_sorted_body_dumps:
        return False
    return any(
        _block_dumps_contain_window(each_block_dumps, all_helper_window_dumps)
        for each_block_dumps in enclosing_profile.all_block_dumps
    )


def _first_enclosing_inliner(
    helper_node: _ModuleScopeFunction,
    all_helper_window_dumps: list[str],
    profile_by_function: dict[_ModuleScopeFunction, _FunctionScanProfile],
) -> _ModuleScopeFunction | None:
    """Return the first other module-scope function that inlines this window.

    Args:
        helper_node: The candidate helper whose window is sought.
        all_helper_window_dumps: The helper's substantive-block statement dumps.
        profile_by_function: Each function's readings, keyed in source order.

    Returns:
        The first function in source order that carries the window, or None.
    """
    helper_profile = profile_by_function[helper_node]
    for each_enclosing, each_profile in profile_by_function.items():
        if each_enclosing is helper_node:
            continue
        if _profile_inlines_window(
            helper_profile, each_profile, all_helper_window_dumps
        ):
            return each_enclosing
    return None


def _inline_duplicate_violation(
    helper_node: _ModuleScopeFunction,
    enclosing_node: _ModuleScopeFunction,
) -> tuple[frozenset[int], str]:
    """Return the scoped lines and report text for one inlined-helper finding.

    Args:
        helper_node: The helper whose body appears inline elsewhere.
        enclosing_node: The function carrying the inlined copy.

    Returns:
        The union of both function spans, and the message naming both.
    """
    helper_span = _function_definition_span(helper_node)
    enclosing_span = _function_definition_span(enclosing_node)
    span_suffix = SAME_FILE_INLINE_DUPLICATE_SPAN_SUFFIX_TEMPLATE.format(
        helper_start=helper_span.start,
        helper_length=len(helper_span),
        enclosing_start=enclosing_span.start,
        enclosing_length=len(enclosing_span),
    )
    message = (
        f"Function {helper_node.name!r} duplicates an inline block in "
        f"{enclosing_node.name!r} — {SAME_FILE_INLINE_DUPLICATE_GUIDANCE} "
        f"{span_suffix}"
    )
    return (frozenset(helper_span) | frozenset(enclosing_span), message)


def _violations_for_qualifying_helpers(
    window_by_function: dict[_ModuleScopeFunction, list[str]],
    profile_by_function: dict[_ModuleScopeFunction, _FunctionScanProfile],
    maximum_issue_count: int,
) -> list[tuple[frozenset[int], str]]:
    """Walk the helpers in source order and report the first inliner of each.

    Args:
        window_by_function: Each qualifying function's helper match window.
        profile_by_function: Each function's readings, keyed in source order.
        maximum_issue_count: The report ceiling the walk stops at.

    Returns:
        The in-scope lines and message of each report, in walk order.
    """
    all_violations_in_walk_order: list[tuple[frozenset[int], str]] = []
    for each_helper, each_window_dumps in window_by_function.items():
        each_enclosing = _first_enclosing_inliner(
            each_helper, each_window_dumps, profile_by_function
        )
        if each_enclosing is not None:
            all_violations_in_walk_order.append(
                _inline_duplicate_violation(each_helper, each_enclosing)
            )
        if len(all_violations_in_walk_order) >= maximum_issue_count:
            break
    return all_violations_in_walk_order


def _inline_duplicate_violations(
    all_top_level_functions: list[_ModuleScopeFunction],
    maximum_issue_count: int,
) -> list[tuple[frozenset[int], str]]:
    """Report every module-scope helper whose body is inlined in another function.

    The dump memo and the per-function readings live for this one call and are
    dropped when it returns, so no reading outlives the parse tree it describes.

    Args:
        all_top_level_functions: The module-scope functions in source order.
        maximum_issue_count: The report ceiling the walk stops at.

    Returns:
        The in-scope lines and message of each report, in walk order.
    """
    dump_by_statement: dict[ast.stmt, str] = {}
    window_by_function = {
        each_function: each_window
        for each_function in all_top_level_functions
        if (
            each_window := _helper_match_window_dumps(each_function, dump_by_statement)
        )
        is not None
    }
    if not window_by_function:
        return []
    profile_by_function = {
        each_function: _function_scan_profile(each_function, dump_by_statement)
        for each_function in all_top_level_functions
    }
    return _violations_for_qualifying_helpers(
        window_by_function, profile_by_function, maximum_issue_count
    )


def _skill_scripts_root(file_path: str) -> Path | None:
    """Return the ``skills/<name>/scripts`` root the written file sits under.

    A skill's helper scripts live at ``<...>/skills/<skill-name>/scripts/<file>``.
    This walks the written file's parents for a ``scripts`` directory whose own
    parent's parent is named ``skills``, and returns that ``scripts`` directory.

    Args:
        file_path: The destination path of the write.

    Returns:
        The ``skills/<name>/scripts`` directory containing the file, or None when
        the file is not under a skill's ``scripts`` directory.
    """
    written_path = Path(file_path).resolve()
    for each_ancestor in written_path.parents:
        if each_ancestor.name != SKILL_SCRIPTS_DIRECTORY_NAME:
            continue
        skill_directory = each_ancestor.parent
        if skill_directory.parent.name == SKILLS_DIRECTORY_NAME:
            return each_ancestor
    return None


def _other_skill_scripts_directories(scripts_root: Path) -> list[Path]:
    """List the ``scripts`` directories of every sibling skill folder.

    Args:
        scripts_root: The ``skills/<name>/scripts`` directory of the written file.

    Returns:
        The ``scripts`` directory of each sibling skill that has one, excluding
        the written file's own skill.
    """
    own_skill_directory = scripts_root.parent
    skills_directory = own_skill_directory.parent
    all_other_scripts_directories: list[Path] = []
    try:
        all_skill_entries = sorted(skills_directory.iterdir())
    except OSError:
        return []
    for each_skill_directory in all_skill_entries:
        if not each_skill_directory.is_dir():
            continue
        if each_skill_directory == own_skill_directory:
            continue
        candidate_scripts = each_skill_directory / SKILL_SCRIPTS_DIRECTORY_NAME
        if candidate_scripts.is_dir():
            all_other_scripts_directories.append(candidate_scripts)
    return all_other_scripts_directories


def _cross_skill_source_signatures(
    all_other_scripts_directories: list[Path],
) -> dict[str, list[str]]:
    """Map each function body signature to the ``skill/module::function`` copies.

    Args:
        all_other_scripts_directories: The ``scripts`` directory of each sibling skill.

    Returns:
        A signature-to-source-names mapping naming the skill, module, and function
        that carry each comparable top-level body.
    """
    source_names_by_signature: dict[str, list[str]] = {}
    for each_scripts_directory in all_other_scripts_directories:
        skill_name = each_scripts_directory.parent.name
        try:
            all_entries = sorted(each_scripts_directory.iterdir())
        except OSError:
            continue
        for each_entry in all_entries:
            if not _is_comparable_sibling(each_entry, ""):
                continue
            try:
                sibling_source = each_entry.read_text(encoding="utf-8")
                sibling_tree = ast.parse(sibling_source)
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue
            for each_name, each_signature in _top_level_function_signatures(sibling_tree).items():
                location = f"{skill_name}/{each_entry.name}::{each_name}"
                source_names_by_signature.setdefault(each_signature, []).append(location)
    return source_names_by_signature


def advise_cross_skill_duplicate_helper(content: str, file_path: str) -> None:
    """Emit non-blocking stderr advisories for helpers copied across skill folders.

    A top-level function in the file being written whose normalized body matches a
    top-level function in another skill's ``scripts`` directory is surfaced as a
    ``[CODE_RULES advisory]`` line on stderr — never a block. Two skill folders
    install on their own, so a shared module would break independent install; the
    copy is a defensible skill-isolation tradeoff the writer confirms rather than
    a violation the gate denies. Within one skill the blocking duplicate-body gate
    already covers the copy, so this advisory fires only across skill folders.

    Test files and ``__init__.py`` are skipped on both the writing side and the
    sibling side, mirroring the blocking gate.

    Args:
        content: The full post-edit file content being written.
        file_path: The destination path of the write.
    """
    written_name = Path(file_path).name
    if written_name == DUNDER_INIT_FILENAME:
        return
    if is_test_file(file_path):
        return
    scripts_root = _skill_scripts_root(file_path)
    if scripts_root is None:
        return
    try:
        written_tree = ast.parse(content)
    except SyntaxError:
        return
    written_signatures = _top_level_function_signatures(written_tree)
    if not written_signatures:
        return
    all_other_scripts_directories = _other_skill_scripts_directories(scripts_root)
    if not all_other_scripts_directories:
        return
    source_names_by_signature = _cross_skill_source_signatures(all_other_scripts_directories)
    advisory_count = 0
    for each_name, each_signature in written_signatures.items():
        matching_locations = source_names_by_signature.get(each_signature)
        if not matching_locations:
            continue
        print(
            f"{CROSS_SKILL_ADVISORY_PREFIX} {file_path}: function {each_name!r} "
            f"duplicates {matching_locations[0]} in another skill — "
            f"{CROSS_SKILL_DUPLICATE_GUIDANCE}",
            file=sys.stderr,
        )
        advisory_count += 1
        if advisory_count >= MAX_CROSS_SKILL_ADVISORY_ISSUES:
            break
