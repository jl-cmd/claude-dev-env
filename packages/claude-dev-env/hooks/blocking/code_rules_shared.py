"""Shared file classifiers, AST-walk helpers, and diff-scoping utilities for the code-rules checks."""

import ast
import difflib
import os
import sys
import tempfile
from collections.abc import Collection, Iterator
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from hooks_constants.code_rules_enforcer_constants import (  # noqa: E402
    ALL_DIFF_CHANGED_OPCODE_TAGS,
    ALL_EPHEMERAL_EXEMPT_DISABLE_TRUTHY_VALUES,
    ALL_HOOK_INFRASTRUCTURE_PATTERNS,
    ALL_MIGRATION_PATH_PATTERNS,
    ALL_ROOT_ANCHORED_EPHEMERAL_DIRECTORIES,
    ALL_STRICT_TEST_DIRECTORY_SEGMENTS,
    ALL_TEST_PATH_PATTERNS,
    ALL_WORKFLOW_REGISTRY_PATTERNS,
    CLAUDE_JOB_DIR_ENVIRONMENT_VARIABLE_NAME,
    CLAUDE_JOB_DIR_SCRATCH_SUBDIRECTORY,
    EPHEMERAL_EXEMPT_DISABLE_ENVIRONMENT_VARIABLE_NAME,
    LEADING_DRIVE_LETTER_PATTERN,
    STRICT_TEST_FILE_BASENAME_PATTERN,
)
from hooks_constants.harness_scratchpad_constants import (  # noqa: E402
    CLAUDE_SESSION_ID_ENVIRONMENT_VARIABLE_NAME,
    HARNESS_SCRATCHPAD_LEAF_DIRECTORY_NAME,
    HARNESS_SCRATCHPAD_USER_DIRECTORY_NAME,
    HARNESS_SCRATCHPAD_USER_DIRECTORY_PREFIX,
    HOOK_PAYLOAD_SESSION_ID_KEY,
)
from hooks_constants.unused_module_import_constants import (  # noqa: E402
    TYPE_CHECKING_IDENTIFIER,
)


def get_file_extension(file_path: str) -> str:
    """Extract lowercase file extension."""
    dot_index = file_path.rfind(".")
    if dot_index == -1:
        return ""
    return file_path[dot_index:].lower()


def is_hook_infrastructure(file_path: str) -> bool:
    """Check if file is a Claude Code hook (standalone infrastructure, not project code)."""
    path_lower = "/" + file_path.lower().replace("\\", "/").lstrip("/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in ALL_HOOK_INFRASTRUCTURE_PATTERNS)


def is_test_file(file_path: str) -> bool:
    """Check if file is a test file."""
    path_lower = file_path.lower()
    basename_lower = path_lower.replace("\\", "/").rsplit("/", 1)[-1]
    if basename_lower == "conftest.py":
        return True
    return any(pattern in path_lower for pattern in ALL_TEST_PATH_PATTERNS)


def is_strict_test_file(file_path: str) -> bool:
    """Check if a file is a genuine test module by its basename, not a mid-name match.

    A production module whose name carries the substring ``test`` mid-name —
    such as ``code_rules_test_assertions.py`` — is not a test module. This
    predicate anchors on the basename shape (``test_*`` / ``*_test.*`` /
    ``*.test.*`` / ``*.spec.*`` / ``conftest.py``) or a ``/tests/`` path
    segment, so it keeps such production modules out of the test exemption that
    the substring-based is_test_file applies.
    """
    normalized_path = file_path.lower().replace("\\", "/")
    if any(segment in normalized_path for segment in ALL_STRICT_TEST_DIRECTORY_SEGMENTS):
        return True
    basename_lower = normalized_path.rsplit("/", 1)[-1]
    return STRICT_TEST_FILE_BASENAME_PATTERN.match(basename_lower) is not None


def is_workflow_registry_file(file_path: str) -> bool:
    """Check if file is a workflow state/module registry file.

    Workflow tab files and state/module registry files use UPPER_SNAKE naming
    for StateDefinition and WorkflowModule instances by architectural convention.
    These are module-level singletons, not misplaced literal constants.
    """
    path_lower = file_path.lower().replace("\\", "/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in ALL_WORKFLOW_REGISTRY_PATTERNS)


def is_spec_file(file_path: str) -> bool:
    """Check if file is an E2E spec file."""
    return ".spec." in file_path.lower()


def _is_type_checking_guard(if_node: ast.If) -> bool:
    test_node = if_node.test
    if isinstance(test_node, ast.Name) and test_node.id == TYPE_CHECKING_IDENTIFIER:
        return True
    return isinstance(test_node, ast.Attribute) and test_node.attr == TYPE_CHECKING_IDENTIFIER


def _walk_skipping_type_checking_blocks(node: ast.AST) -> "Iterator[ast.AST]":
    for each_child in ast.iter_child_nodes(node):
        if isinstance(each_child, ast.If) and _is_type_checking_guard(each_child):
            continue
        yield each_child
        yield from _walk_skipping_type_checking_blocks(each_child)


def _walk_skipping_nested_functions(node: ast.AST) -> "Iterator[ast.AST]":
    for each_child in ast.iter_child_nodes(node):
        if isinstance(each_child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        yield each_child
        yield from _walk_skipping_nested_functions(each_child)


def _walk_skipping_nested_function_defs(start_node: ast.AST) -> Iterator[ast.AST]:
    if isinstance(start_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return
    nodes_to_visit: list[ast.AST] = [start_node]
    while nodes_to_visit:
        current_node = nodes_to_visit.pop()
        yield current_node
        all_child_nodes = list(ast.iter_child_nodes(current_node))
        for each_child_node in reversed(all_child_nodes):
            if isinstance(each_child_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            nodes_to_visit.append(each_child_node)


def _collect_annotated_arguments(function_node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.arg]:
    """Return every argument node on a function that may carry an annotation."""
    arguments = function_node.args
    all_annotated_arguments: list[ast.arg] = []
    all_annotated_arguments.extend(arguments.posonlyargs)
    all_annotated_arguments.extend(arguments.args)
    all_annotated_arguments.extend(arguments.kwonlyargs)
    if arguments.vararg is not None:
        all_annotated_arguments.append(arguments.vararg)
    if arguments.kwarg is not None:
        all_annotated_arguments.append(arguments.kwarg)
    return all_annotated_arguments


def _collect_fixture_injection_arguments(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> list[ast.arg]:
    """Return only the named parameters pytest fills by fixture injection.

    Pytest passes fixtures by keyword (``testfunction(**testargs)``), so a
    parameter can receive a fixture only when both conditions hold: it is
    reachable by keyword, and pytest is responsible for supplying its value.
    Positional-only parameters are NOT injection slots — a keyword-passed
    fixture can never bind to one, and ``def test_x(tmp_path, /)`` raises a
    missing-argument ``TypeError`` under pytest. A ``*args`` star-argument or
    ``**kwargs`` double-star-argument never names a single fixture either.
    A parameter carrying a default is NOT injected — pytest leaves its default
    in place rather than supplying the fixture. So this collector keeps only the
    positional-or-keyword and keyword-only parameters that have no default, and
    omits ``args.posonlyargs``, ``args.vararg``, and ``args.kwarg``.

    Args:
        function_node: The function definition AST node to inspect.

    Returns:
        The undefaulted positional-or-keyword and keyword-only argument nodes,
        in declaration order.
    """
    arguments = function_node.args
    defaulted_positional_count = len(arguments.defaults)
    undefaulted_positional_arguments = (
        arguments.args[:-defaulted_positional_count]
        if defaulted_positional_count
        else arguments.args
    )
    undefaulted_keyword_only_arguments = [
        each_keyword_argument
        for each_keyword_argument, each_default in zip(
            arguments.kwonlyargs, arguments.kw_defaults, strict=False
        )
        if each_default is None
    ]
    return [*undefaulted_positional_arguments, *undefaulted_keyword_only_arguments]


def _collect_target_names(target: ast.expr) -> list[ast.Name]:
    """Return every ast.Name reachable through tuple/list/starred unpacking targets."""
    if isinstance(target, ast.Name):
        return [target]
    if isinstance(target, (ast.Tuple, ast.List)):
        names: list[ast.Name] = []
        for each_element in target.elts:
            names.extend(_collect_target_names(each_element))
        return names
    if isinstance(target, ast.Starred):
        return _collect_target_names(target.value)
    return []


def _extract_fstring_literal_parts(
    joined_string_node: ast.JoinedStr,
    interpolation_placeholder: str = "INTERP",
) -> tuple[str, str]:
    """Return (display_body, shape_body) for an f-string node.

    ``display_body`` concatenates only the literal segments for use in the
    human-readable flag message. ``shape_body`` substitutes each interpolation
    slot with ``interpolation_placeholder`` so callers can choose a token that
    both preserves structural shape and does not collide with literal text in
    the source. The default ``"INTERP"`` keeps regex patterns for path shape
    (``\\w+/\\w+/\\w+``) matching across interpolation boundaries
    (e.g. ``/api/v1/{id}/home`` keeps its three path segments instead of
    collapsing to ``/api/v1//home``). Callers that will compare shape bodies
    verbatim — such as the skeleton builder — should pass their final token
    here directly rather than post-processing with ``.replace``, since that
    would corrupt literal text containing the default placeholder. Escaped
    braces (``{{`` / ``}}``) are already decoded by :mod:`ast` into their
    literal forms.
    """
    display_segments: list[str] = []
    shape_segments: list[str] = []
    for each_part in joined_string_node.values:
        if isinstance(each_part, ast.Constant) and isinstance(each_part.value, str):
            display_segments.append(each_part.value)
            shape_segments.append(each_part.value)
        else:
            shape_segments.append(interpolation_placeholder)
    return "".join(display_segments), "".join(shape_segments)


def is_ephemeral_script_path(file_path: str) -> bool:
    """Return True when the path is rooted at a throwaway scratch directory.

    Checks these sources in order:
    - ``$CLAUDE_JOB_DIR/tmp`` — only when ``CLAUDE_JOB_DIR`` is set.
    - Root-anchored ``/tmp`` and ``/temp`` (drive-letter tolerant).

    The shared OS temp directory is deliberately not a source: pytest writes
    its sandbox fixtures there, so matching it would exempt the suite's own
    targets. Returns False when ``CLAUDE_CODE_RULES_DISABLE_EPHEMERAL_EXEMPT``
    is truthy, when ``file_path`` is empty, and when no root matches. Path
    classification is string-only; the file need not exist.

    Args:
        file_path: The candidate path to classify.

    Returns:
        True when the path is rooted at a recognized ephemeral scratch directory.
    """
    if not file_path:
        return False
    disable_value = os.environ.get(EPHEMERAL_EXEMPT_DISABLE_ENVIRONMENT_VARIABLE_NAME, "").strip().lower()
    if disable_value in ALL_EPHEMERAL_EXEMPT_DISABLE_TRUTHY_VALUES:
        return False
    normalized = LEADING_DRIVE_LETTER_PATTERN.sub("", os.path.abspath(file_path).replace("\\", "/").lower())
    all_temp_roots: list[str] = []
    job_dir = os.environ.get(CLAUDE_JOB_DIR_ENVIRONMENT_VARIABLE_NAME)
    if job_dir:
        job_dir_scratch = LEADING_DRIVE_LETTER_PATTERN.sub(
            "", os.path.join(job_dir, CLAUDE_JOB_DIR_SCRATCH_SUBDIRECTORY).replace("\\", "/").lower()
        )
        all_temp_roots.append(job_dir_scratch)
    for each_root in ALL_ROOT_ANCHORED_EPHEMERAL_DIRECTORIES:
        all_temp_roots.append(each_root)
    for each_temp_root in all_temp_roots:
        if normalized == each_temp_root or normalized.startswith(each_temp_root + "/"):
            return True
    return False


def _session_id_for_scratchpad(hook_payload: dict) -> str:
    """Return the session id from the payload, or the harness environment value.

    Args:
        hook_payload: The PreToolUse payload that may carry ``session_id``.

    Returns:
        The payload session id when present, otherwise the
        ``CLAUDE_CODE_SESSION_ID`` environment value, or an empty string when
        neither source carries one.
    """
    payload_session_id = hook_payload.get(HOOK_PAYLOAD_SESSION_ID_KEY, "")
    if isinstance(payload_session_id, str) and payload_session_id:
        return payload_session_id
    return os.environ.get(CLAUDE_SESSION_ID_ENVIRONMENT_VARIABLE_NAME, "")


def _is_harness_user_directory(directory_name: str) -> bool:
    """Return whether a path component is the harness user directory.

    The harness names this directory ``claude`` on Windows and ``claude-<uid>``
    on POSIX, so both the exact name and the prefixed form count.

    Args:
        directory_name: A single path component below the temp-directory root.

    Returns:
        True when the component is the harness user directory.
    """
    return (
        directory_name == HARNESS_SCRATCHPAD_USER_DIRECTORY_NAME
        or directory_name.startswith(HARNESS_SCRATCHPAD_USER_DIRECTORY_PREFIX)
    )


def _relative_parts_under_temp_root(
    real_target: str, real_temp_root: str
) -> tuple[str, ...]:
    """Return real_target's path components below real_temp_root, or empty when outside.

    Args:
        real_target: The resolved candidate path.
        real_temp_root: The resolved temp-directory root.

    Returns:
        The path components between the temp root and the target, or an empty
        tuple when the target sits outside the temp directory or on another
        drive.
    """
    try:
        relative_path = os.path.relpath(real_target, real_temp_root)
    except ValueError:
        return ()
    all_relative_parts = Path(relative_path).parts
    if all_relative_parts and all_relative_parts[0] == os.path.pardir:
        return ()
    return all_relative_parts


def _existing_scratchpad_root(
    all_relative_parts: tuple[str, ...], real_temp_root: str, session_id: str
) -> str | None:
    """Return the on-disk scratchpad root matching the harness shape, or None.

    ::

        <temp-root>/<user-dir>/<mangled-cwd>/<session-id>/scratchpad/<file>
                        |                          |           |
                  claude user dir            session id     leaf name

    Args:
        all_relative_parts: The target's path components below the temp root.
        real_temp_root: The resolved temp-directory root.
        session_id: The session id the scratchpad's parent segment must equal.

    Returns:
        The scratchpad directory path when the shape matches and that directory
        exists on disk, otherwise None.
    """
    if not all_relative_parts or not _is_harness_user_directory(all_relative_parts[0]):
        return None
    for each_session_index in range(1, len(all_relative_parts) - 1):
        leaf_index = each_session_index + 1
        if all_relative_parts[each_session_index] != session_id:
            continue
        if all_relative_parts[leaf_index] != HARNESS_SCRATCHPAD_LEAF_DIRECTORY_NAME:
            continue
        scratchpad_root = os.path.join(
            real_temp_root, *all_relative_parts[: leaf_index + 1]
        )
        return scratchpad_root if os.path.isdir(scratchpad_root) else None
    return None


def is_under_session_scratchpad(file_path: str, hook_payload: dict) -> bool:
    """Return True when file_path resolves under the harness session scratchpad.

    One-off scripts written to the session scratchpad are throwaway tooling
    outside every repo, so the TDD and CODE_RULES gates skip them.

    The match keys on the session id — from the payload, or the
    ``CLAUDE_CODE_SESSION_ID`` environment variable — and on the temp-directory
    path shape ``<user-dir>/<mangled-cwd>/<session-id>/scratchpad``, so it holds
    on Windows and POSIX alike. file_path resolves through the real filesystem
    (symlinks followed) before the shape test, and the scratchpad directory must
    exist on disk, so a crafted path that never existed keeps full enforcement.

    Args:
        file_path: The path the write targets.
        hook_payload: The PreToolUse payload carrying the session id.

    Returns:
        True when file_path's real path sits at or under the session scratchpad.
    """
    if not file_path:
        return False
    session_id = _session_id_for_scratchpad(hook_payload)
    if not session_id:
        return False
    real_target = os.path.realpath(file_path)
    real_temp_root = os.path.realpath(tempfile.gettempdir())
    all_relative_parts = _relative_parts_under_temp_root(real_target, real_temp_root)
    return (
        _existing_scratchpad_root(all_relative_parts, real_temp_root, session_id)
        is not None
    )


def is_ephemeral_path(file_path: str, hook_payload: dict | None = None) -> bool:
    """Return True when file_path is a throwaway scratch path exempt from repo gates.

    Combines the two throwaway-path families a repo gate skips: the root-anchored
    ephemeral scratch directories (``/tmp`` and ``$CLAUDE_JOB_DIR/tmp``) and the
    harness session scratchpad. The session scratchpad match reads the session id
    from the payload when one is supplied, and from the harness environment
    variable otherwise, so a caller that holds no payload still gets the match.
    Repo gates that exempt throwaway paths call this shared predicate.

    Args:
        file_path: The candidate path to classify.
        hook_payload: The PreToolUse payload carrying the session id, or None to
            read the session id from the environment alone.

    Returns:
        True when the path is ephemeral scratch or under the session scratchpad.
    """
    if is_ephemeral_script_path(file_path):
        return True
    return is_under_session_scratchpad(file_path, hook_payload or {})


def is_migration_file(file_path: str) -> bool:
    """Check if file is a Django migration (must be self-contained)."""
    path_lower = file_path.lower().replace("\\", "/")
    return any(pattern.replace("\\", "/") in path_lower for pattern in ALL_MIGRATION_PATH_PATTERNS)


def docstring_line_numbers(content: str) -> set[int]:
    """Return every source line that sits inside a string-literal statement.

    A diagram-first docstring often draws its point across several lines, and
    those lines can hold a bare number (a row marker) or a contrast row
    (``flag: is_ok = do_thing(...)``). Those are prose, not code, so a
    line-based lint check that reads them as literals fires a false positive.
    This walks the parsed source and collects the line numbers spanned by every
    string-literal expression statement — module, class, and function
    docstrings, plus any bare string statement — so those checks can skip them.
    Unparseable source yields an empty set.

    Args:
        content: The Python source to scan.

    Returns:
        The 1-indexed line numbers that fall inside a string-literal statement.
    """
    try:
        parsed_tree = ast.parse(content)
    except SyntaxError:
        return set()
    all_docstring_line_numbers: set[int] = set()
    for each_node in ast.walk(parsed_tree):
        if not (isinstance(each_node, ast.Expr) and _statement_is_docstring(each_node)):
            continue
        end_line_number = each_node.end_lineno
        if end_line_number is None:
            continue
        for each_line_number in range(each_node.lineno, end_line_number + 1):
            all_docstring_line_numbers.add(each_line_number)
    return all_docstring_line_numbers


def _build_parent_map(module_tree: ast.Module) -> dict[int, ast.AST]:
    """Map child node id() to its parent node for ancestor walking."""
    parent_by_child_id: dict[int, ast.AST] = {}
    for each_parent in ast.walk(module_tree):
        for each_child in ast.iter_child_nodes(each_parent):
            parent_by_child_id[id(each_child)] = each_parent
    return parent_by_child_id


def _statement_is_docstring(statement_node: ast.stmt) -> bool:
    return (
        isinstance(statement_node, ast.Expr)
        and isinstance(statement_node.value, ast.Constant)
        and isinstance(statement_node.value.value, str)
    )


def _function_definition_line_span(
    function_node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> int:
    end_lineno = getattr(function_node, "end_lineno", None) or function_node.lineno
    return end_lineno - function_node.lineno + 1


def _definition_docstring_line_span(
    definition_node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> int:
    """Return the source-line count of the definition's leading docstring.

    The Google Python Style Guide pairs a small-function preference that
    targets executable complexity with a requirement for complete docstrings
    on public functions and classes. Counting those docstring lines toward the
    function-length gate would penalize the very documentation the Guide
    mandates, so the gate measures executable span and excludes leading
    docstring statements.

    Args:
        definition_node: The function, method, or class definition node to
            inspect.

    Returns:
        The number of source lines the leading docstring statement occupies,
        or zero when the definition body is empty or does not open with a
        string literal.
    """
    definition_body = definition_node.body
    if not definition_body:
        return 0
    first_statement = definition_body[0]
    if _statement_is_docstring(first_statement):
        docstring_end = getattr(first_statement, "end_lineno", None) or first_statement.lineno
        return docstring_end - first_statement.lineno + 1
    return 0


def changed_line_numbers(prior_content: str, post_edit_content: str) -> set[int]:
    """Return the post-edit line numbers an edit added or replaced.

    Runs a line-level diff of *prior_content* against *post_edit_content* and
    collects the 1-indexed line numbers in *post_edit_content* that fall inside
    a ``replace`` or ``insert`` opcode. This mirrors the "added lines" notion
    that ``code_rules_gate.parse_added_line_numbers`` derives from
    ``git diff --unified=0``, so the PreToolUse layer and the gate agree on
    which lines the change touched.

    Args:
        prior_content: The file content before the edit.
        post_edit_content: The reconstructed file content after the edit.

    Returns:
        The set of 1-indexed line numbers in *post_edit_content* that the edit
        added or replaced.
    """
    matcher = difflib.SequenceMatcher(
        a=prior_content.splitlines(),
        b=post_edit_content.splitlines(),
        autojunk=False,
    )
    all_changed_lines: set[int] = set()
    for each_tag, _, _, each_post_start, each_post_end in matcher.get_opcodes():
        if each_tag in ALL_DIFF_CHANGED_OPCODE_TAGS:
            for each_post_index in range(each_post_start, each_post_end):
                all_changed_lines.add(each_post_index + 1)
    return all_changed_lines


def _scope_violations_to_changed_lines(
    all_violations_in_walk_order: list[tuple[Collection[int], str]],
    all_changed_lines: set[int] | None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Scope span-tagged violations by diff intersection.

    In-scope violations are always reported; the untouched out-of-scope set is
    surfaced or dropped according to which caller path is active:

    - ``defer_scope_to_caller`` True (the commit/push gate): every violation is
      returned in walk order so the gate's ``split_violations_by_scope`` can
      classify blocking vs advisory by added line. The gate does this scoping,
      so no scoping happens here.
    - ``all_changed_lines`` None (a terminal new-file or full-file write): every
      line was just authored, so every violation is in scope and returned.
    - ``all_changed_lines`` provided (a terminal diff-scoped Edit): only the
      in-scope violations whose span intersects the changed lines are returned;
      the untouched out-of-scope set is dropped, because untouched code must not
      block a single-file edit.

    Args:
        all_violations_in_walk_order: ``(line_collection, issue_message)`` pairs
            in ``ast.walk`` traversal order, where ``line_collection`` holds the
            violation's source lines. A whole-function violation passes a
            contiguous ``range``; a two-function violation passes the union of
            both functions' lines, so the lines between the two functions stay
            out of scope and an edit to only that gap does not block.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat every violation as in-scope.
        defer_scope_to_caller: When True, return every violation message in walk
            order so the gate scopes by added line. When False, this enforcer is
            terminal and scopes directly.

    Returns:
        Every violation message when *defer_scope_to_caller* is True or
        *all_changed_lines* is None; otherwise only the in-scope messages whose
        span intersects the changed lines — so an edit that grows a function
        past the threshold always blocks even when many earlier untouched
        functions already exceed it.
    """
    if defer_scope_to_caller:
        return [each_message for _, each_message in all_violations_in_walk_order]
    if all_changed_lines is None:
        return [each_message for _, each_message in all_violations_in_walk_order]
    return [
        each_message
        for each_span, each_message in all_violations_in_walk_order
        if any(each_line in all_changed_lines for each_line in each_span)
    ]
