"""Cross-file duplicate top-level function body detection.

The check flags a top-level function in the file being written whose body is
structurally identical to a top-level function already defined in a sibling
``.py`` module in the same directory. This catches the Reuse-before-create / DRY
violation where a helper is copy-pasted across several modules instead of being
imported from one shared home.

The scan is deliberately conservative to keep false positives near zero:

- Only module-scope ``def`` / ``async def`` bodies are compared (the copied-helper
  case), never methods nested in a class.
- Bodies are compared by their normalized AST structure with the leading
  docstring dropped, so reformatting and comment differences do not hide a copy.
  The comparison keeps identifier names, so a match requires the body statements,
  including local variable names, to be structurally identical; it does not
  consider the parameter list, decorators, or whether the function is ``async``.
- A body must contain at least ``MINIMUM_DUPLICATE_BODY_STATEMENTS`` statements;
  trivial one- or two-line helpers (``return None``, a single delegation) are too
  common to flag.
- Test files and ``__init__.py`` re-export surfaces never participate, on either
  the writing side or the sibling side.

Unlike most code-rules checks, this one runs on hook-infrastructure files: the
copied-helper violation it targets appears most often in the ``blocking/`` hook
directory itself, so gating it behind the hook-infrastructure exemption would
leave the exact violation class unguarded. The enforcer entry points route a
hook ``.py`` target to this single check even though the full code-rules verdict
stays off hook infrastructure, so a Write or pre-check against a file under the
``blocking/`` directory still blocks a copied sibling helper.

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
import sys
from pathlib import Path

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
    PYTHON_SOURCE_SUFFIX,
    SKILL_SCRIPTS_DIRECTORY_NAME,
    SKILLS_DIRECTORY_NAME,
)


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
    body_statements = list(function_node.body)
    if body_statements and isinstance(body_statements[0], ast.Expr):
        first_value = body_statements[0].value
        if isinstance(first_value, ast.Constant) and isinstance(first_value.value, str):
            body_statements = body_statements[1:]
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
