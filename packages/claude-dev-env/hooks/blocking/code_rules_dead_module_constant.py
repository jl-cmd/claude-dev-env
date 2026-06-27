"""Dead module-level constant check for dedicated constants modules.

A constants module (`*_constants.py`, or any module under a ``config/``
directory) exists to export named values to importer modules elsewhere in the
project, so a constant defined there is never proven dead by a single-file scan
alone. This check resolves the enclosing package tree — the scan root — and
flags an UPPER_SNAKE constant defined in the written module whose name appears
in no ``.py`` module anywhere under that root: not as an imported name, not as a
read, not as a re-export. When a constant looks dead in the package tree, the
scan widens to the whole repository so a consumer in a sibling tree counts
before the constant is flagged. That is the ``MEDIUM_TEXT``-style dead constant
the CODE_RULES §9.8 dead-code rule targets, caught at Write/Edit time before the
unused constant lands.

The scan is deliberately conservative to keep false positives near zero:

- Only dedicated constants modules participate; ordinary production modules,
  whose file-global constants are governed by the use-count rule, are skipped.
- A module declaring ``__all__`` narrows the check to the constants its
  ``__all__`` list names — the explicit export surface. Each exported constant
  must be imported or read by some other module, since a name an author exports
  yet no module consumes is dead by §9.8; the module's own ``__all__`` entry
  never counts as that consumer. A constant the module defines but ``__all__``
  omits is the author's stated private value and is left alone.
- A constant is live when its name appears in another ``.py`` module the scan
  reaches — imported, read, listed in that module's ``__all__``, or referenced
  in a string annotation — or when the constants module itself reads it in code;
  a name listed only in the constants module's own ``__all__`` does not keep an
  exported constant live.
- When the package-tree scan leaves a constant unreferenced, the scan widens to
  the repository root (the nearest ``.git`` ancestor) so a consumer in a sibling
  tree of the same repository counts; a module outside any repository is judged
  on the package-tree scan alone. The widened pass skips the package subtree the
  first pass already covered, so no file is read twice.
- The combined file count of the package-tree and widened passes is bounded by a
  cap, so a write under an unexpectedly large tree cannot stall the hook; a write
  whose scan hits the cap is treated as "cannot prove dead" and flags nothing.
- Test modules under the scanned tree still count as references, so a constant
  used only by a test stays live.
"""

import ast
import os
import sys
from pathlib import Path

_blocking_directory = str(Path(__file__).resolve().parent)
_hooks_directory = str(Path(__file__).resolve().parent.parent)
if _blocking_directory not in sys.path:
    sys.path.insert(0, _blocking_directory)
if _hooks_directory not in sys.path:
    sys.path.insert(0, _hooks_directory)

from code_rules_shared import (  # noqa: E402
    is_migration_file,
    is_test_file,
)

from hooks_constants.dead_module_constant_constants import (  # noqa: E402
    CONFIG_DIRECTORY_SEGMENT,
    CONSTANTS_MODULE_SUFFIX,
    DEAD_MODULE_CONSTANT_GUIDANCE,
    DUNDER_ALL_NAME,
    DUNDER_INIT_FILENAME,
    GIT_DIRECTORY_NAME,
    MAX_DEAD_MODULE_CONSTANT_ISSUES,
    MAX_SCAN_ROOT_FILE_COUNT,
    MINIMUM_UPPER_SNAKE_LENGTH,
    PYTHON_SOURCE_SUFFIX,
)


def _is_dedicated_constants_module(file_path: str) -> bool:
    """Return whether a path is a dedicated constants module.

    A dedicated constants module is one whose filename ends in
    ``_constants.py`` or whose path includes a ``config`` directory segment.
    These modules export named values to importers, so their constants need a
    cross-module scan to judge liveness.

    Args:
        file_path: The destination path of the write.

    Returns:
        True for a constants-suffixed module or a module under ``config/``.
    """
    normalized_path = file_path.replace("\\", "/").lower()
    if normalized_path.endswith(CONSTANTS_MODULE_SUFFIX):
        return True
    path_segments = normalized_path.split("/")
    return CONFIG_DIRECTORY_SEGMENT in path_segments[:-1]


def _is_upper_snake_name(name: str) -> bool:
    """Return whether a name is an UPPER_SNAKE_CASE constant identifier."""
    if len(name) < MINIMUM_UPPER_SNAKE_LENGTH:
        return False
    if not name.replace("_", "").isalnum():
        return False
    return name == name.upper() and any(each_char.isalpha() for each_char in name)


def _module_constant_definitions(tree: ast.Module) -> list[tuple[str, int]]:
    """Return (name, line) for each module-scope UPPER_SNAKE constant assignment.

    Both plain assignments (``NAME = value``) and annotated assignments
    (``NAME: type = value``) at module scope are collected. A name bound more
    than once keeps the line of its first binding.

    Args:
        tree: The parsed constants module.

    Returns:
        One (name, line) pair per distinct module-scope constant, in source
        order.
    """
    line_by_name: dict[str, int] = {}
    for each_statement in tree.body:
        targets: list[ast.expr] = []
        if isinstance(each_statement, ast.Assign):
            targets = list(each_statement.targets)
        elif isinstance(each_statement, ast.AnnAssign) and each_statement.value is not None:
            targets = [each_statement.target]
        for each_target in targets:
            if not isinstance(each_target, ast.Name):
                continue
            if not _is_upper_snake_name(each_target.id):
                continue
            if each_target.id not in line_by_name:
                line_by_name[each_target.id] = each_statement.lineno
    return list(line_by_name.items())


def _statement_binds_dunder_all(statement: ast.stmt) -> bool:
    """Return whether a single statement assigns or annotates ``__all__``."""
    if isinstance(statement, ast.Assign):
        return any(
            isinstance(each_target, ast.Name) and each_target.id == DUNDER_ALL_NAME
            for each_target in statement.targets
        )
    return (
        isinstance(statement, ast.AnnAssign)
        and isinstance(statement.target, ast.Name)
        and statement.target.id == DUNDER_ALL_NAME
    )


def _module_declares_dunder_all(tree: ast.Module) -> bool:
    """Return whether the module body assigns or annotates ``__all__``."""
    return any(_statement_binds_dunder_all(each_node) for each_node in tree.body)


def _dunder_all_member_names(tree: ast.Module) -> set[str]:
    """Return the string member names a module's ``__all__`` sequence lists.

    Reads the value of each ``__all__`` assignment whose value is a list, tuple,
    or set literal and collects every string element. A non-literal ``__all__``
    value (built by concatenation or a comprehension) contributes no names, so a
    constant the check cannot prove is exported stays out of the exported set.

    Args:
        tree: The parsed constants module.

    Returns:
        The set of names the module names in its ``__all__`` literal.
    """
    member_names: set[str] = set()
    for each_statement in tree.body:
        if not _statement_binds_dunder_all(each_statement):
            continue
        value_node: ast.expr | None = None
        if isinstance(each_statement, ast.Assign):
            value_node = each_statement.value
        elif isinstance(each_statement, ast.AnnAssign):
            value_node = each_statement.value
        if not isinstance(value_node, ast.List | ast.Tuple | ast.Set):
            continue
        for each_element in value_node.elts:
            if isinstance(each_element, ast.Constant) and isinstance(each_element.value, str):
                member_names.add(each_element.value)
    return member_names


def _referenced_names_in_source(
    source: str,
    load_only: bool = False,
    collect_string_literals: bool = True,
) -> set[str]:
    """Return every name a module references — imported, read, or re-exported.

    Collects imported binding names, ``from`` import member names, name
    references, attribute roots, and (when ``collect_string_literals`` is set)
    string literals, so a name listed in an ``__all__`` literal or named in a
    string annotation counts as a reference. A module that fails to parse
    contributes no names. With ``load_only`` set, only ``Load``-context names
    count, so a constant's own assignment target in the module being judged does
    not count as a reference to itself.

    Args:
        source: The full text of a ``.py`` module under the scan root.
        load_only: When True, count only ``Load``-context name references,
            excluding ``Store``/``Del`` targets. Used for the written constants
            module so a definition is not mistaken for its own consumer.
        collect_string_literals: When True, count every string literal as a
            referenced name. Set False for the written module under an ``__all__``
            export check so the module's own ``__all__`` entry never shields an
            exported constant that no other module consumes.

    Returns:
        The set of names the module references.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    referenced_names: set[str] = set()
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.Name):
            if load_only and not isinstance(each_node.ctx, ast.Load):
                continue
            referenced_names.add(each_node.id)
        elif isinstance(each_node, ast.Import | ast.ImportFrom):
            for each_alias in each_node.names:
                referenced_names.add(each_alias.asname or each_alias.name)
                referenced_names.add(each_alias.name)
        elif (
            collect_string_literals
            and isinstance(each_node, ast.Constant)
            and isinstance(each_node.value, str)
        ):
            referenced_names.add(each_node.value)
    return referenced_names


def _scan_root_for_constants_module(file_path: str) -> Path:
    """Return the directory tree to scan for references to the module's constants.

    For a constants module inside a package subdirectory
    (``pkg/foo_constants.py``), the scan root is the package's parent, so an
    importer one directory up (``pkg/../consumer.py``) is in scope. For a
    constants module at the top of a directory, the scan root is that directory.
    A ``config/`` module's scan root is the parent of the ``config`` directory.

    Args:
        file_path: The destination path of the write.

    Returns:
        The absolute directory to scan recursively for references.
    """
    written_path = Path(file_path).resolve()
    enclosing_directory = written_path.parent
    if enclosing_directory.name.lower() == CONFIG_DIRECTORY_SEGMENT:
        return enclosing_directory.parent
    if (enclosing_directory / DUNDER_INIT_FILENAME).is_file():
        return enclosing_directory.parent
    return enclosing_directory


def _is_under_directory(candidate_path: Path, ancestor_directory: Path) -> bool:
    """Return whether a resolved path lies inside a resolved ancestor directory.

    Args:
        candidate_path: The resolved file path to test.
        ancestor_directory: The resolved directory that may contain the path.

    Returns:
        True when ``candidate_path`` is the ancestor directory itself or a
        descendant of it, False otherwise.
    """
    try:
        candidate_path.relative_to(ancestor_directory)
    except ValueError:
        return False
    return True


def _all_referenced_names_under_root(
    scan_root: Path,
    written_path: Path,
    written_content: str,
    already_scanned_count: int = 0,
    excluded_subtree: Path | None = None,
    seed_collect_string_literals: bool = True,
) -> tuple[set[str], int, bool]:
    """Return referenced names under the scan root, the running count, and a cap flag.

    The written module's on-disk text is replaced by ``written_content`` so the
    post-edit view is judged, never the stale disk copy. Sibling modules are read
    from disk. Reading stops once the running file count exceeds the configured
    cap so a write under an unexpectedly large tree cannot stall the hook; the
    boolean signals the caller to treat that case as "cannot prove dead". When
    ``excluded_subtree`` is supplied, every ``.py`` module under that directory is
    skipped, so the widened repository scan never re-reads a file the
    package-tree scan already covered.

    Args:
        scan_root: The directory tree to scan.
        written_path: The resolved path of the module being written.
        written_content: The post-edit text of the written module.
        already_scanned_count: The file count accumulated by a prior pass, so the
            cap bounds the combined work of the package-tree and widened passes.
        excluded_subtree: A resolved directory whose ``.py`` modules are skipped,
            or None to scan every file under the root.
        seed_collect_string_literals: Whether the written module's own string
            literals seed the referenced-name set. Set False under an ``__all__``
            export check so the module's own ``__all__`` entry never counts as the
            consumer of an exported constant; sibling modules always contribute
            their string literals so a consumer's re-export still counts.

    Returns:
        A (referenced_names, running_count, cap_was_hit) triple. The name set is
        the union across every scanned module, unioned with the names the written
        module itself references; running_count is the cumulative file count
        including ``already_scanned_count``; cap_was_hit is True when the scan
        stopped at the configured file cap before scanning the whole tree.
    """
    all_referenced_names = _referenced_names_in_source(
        written_content,
        load_only=True,
        collect_string_literals=seed_collect_string_literals,
    )
    written_path_key = os.path.normcase(str(written_path))
    scanned_file_count = already_scanned_count
    for each_path in scan_root.rglob("*" + PYTHON_SOURCE_SUFFIX):
        if not each_path.is_file():
            continue
        resolved_path = each_path.resolve()
        if os.path.normcase(str(resolved_path)) == written_path_key:
            continue
        if excluded_subtree is not None and _is_under_directory(resolved_path, excluded_subtree):
            continue
        scanned_file_count += 1
        if scanned_file_count > MAX_SCAN_ROOT_FILE_COUNT:
            return all_referenced_names, scanned_file_count, True
        try:
            sibling_source = each_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        all_referenced_names |= _referenced_names_in_source(sibling_source)
    return all_referenced_names, scanned_file_count, False


def _repository_root_for(written_path: Path) -> Path | None:
    """Return the nearest ancestor directory that holds a ``.git`` entry.

    Walks upward from the written module toward the filesystem root. A normal
    checkout carries a ``.git`` directory and a git worktree carries a ``.git``
    file; both satisfy ``exists()``. The repository root bounds the widened
    cross-tree reference scan.

    Args:
        written_path: The resolved path of the constants module being written.

    Returns:
        The repository root directory, or ``None`` when no ancestor carries a
        ``.git`` entry, so a module outside any repository triggers no widened
        scan.
    """
    for each_ancestor in written_path.parents:
        if (each_ancestor / GIT_DIRECTORY_NAME).exists():
            return each_ancestor
    return None


def _module_is_exempt_from_constant_check(file_path: str) -> bool:
    """Return whether a path is exempt from the dead module-constant check.

    Test modules and migration modules are exempt, and any module that is not a
    dedicated constants module is out of scope because its file-global constants
    are governed by the use-count rule instead.

    Args:
        file_path: The destination path of the write.

    Returns:
        True when the dead module-constant check must not run on this path.
    """
    if is_test_file(file_path):
        return True
    if is_migration_file(file_path):
        return True
    return not _is_dedicated_constants_module(file_path)


def _constants_under_check(tree: ast.Module) -> tuple[list[tuple[str, int]], bool]:
    """Return the constants to judge and whether the seed counts string literals.

    A module without ``__all__`` judges every module-scope constant and lets its
    own string literals seed the reference scan. A module declaring ``__all__``
    judges only the constants its ``__all__`` list names — the explicit export
    surface — and withholds its own string literals from the seed, so an
    ``__all__`` entry never counts as the consumer that keeps an exported constant
    live. A constant the module defines but ``__all__`` omits is the author's
    stated private value and is left out of the judged set.

    Args:
        tree: The parsed constants module.

    Returns:
        A (definitions, seed_collect_string_literals) pair: the (name, line)
        constants to judge, and whether the written module's string literals seed
        the referenced-name set.
    """
    constant_definitions = _module_constant_definitions(tree)
    if not _module_declares_dunder_all(tree):
        return constant_definitions, True
    exported_names = _dunder_all_member_names(tree)
    exported_definitions = [
        (each_name, each_line)
        for each_name, each_line in constant_definitions
        if each_name in exported_names
    ]
    return exported_definitions, False


def check_dead_module_constants(
    content: str,
    file_path: str,
    full_file_content: str | None = None,
) -> list[str]:
    """Flag an UPPER_SNAKE constant in a constants module read by no module.

    Runs only on a dedicated constants module (``*_constants.py`` or a module
    under ``config/``); every other production module's file-global constants
    are governed by the use-count rule instead. A constant is dead when its name
    appears in no ``.py`` module under the enclosing package tree, nor anywhere
    in the repository the scan widens to when the package-tree scan leaves the
    constant unreferenced — not imported, not read, not listed in another
    module's ``__all__`` literal, not named in a string annotation. A module
    declaring ``__all__`` narrows the check to the constants its ``__all__`` list
    names: each must be imported or read by another module, and the module's own
    ``__all__`` entry never counts as that consumer, so an exported constant no
    module consumes is flagged; a constant the module defines but ``__all__``
    omits is the author's private value and is left alone. A scan whose combined
    package-tree and widened file count exceeds the configured cap returns ``[]``
    (cannot prove dead), bounding the work so the blocking hook cannot stall under
    a large tree. Whole-file analysis runs against ``full_file_content`` when
    supplied so an Edit fragment is judged against the reconstructed post-edit
    file.

    Args:
        content: The new content under validation (Edit fragment or whole file).
        file_path: The destination path, used for the constants-module gate and
            the test/registry exemptions.
        full_file_content: The reconstructed post-edit whole-file content for an
            Edit, or None for a Write where ``content`` is already the whole file.

    Returns:
        One violation message per dead module-level constant, capped at the
        configured maximum. Returns an empty list when the file is exempt, no
        constant is in scope (none defined, or none exported when ``__all__`` is
        declared), the scan exceeds the file cap, or a SyntaxError prevents
        parsing.
    """
    if _module_is_exempt_from_constant_check(file_path):
        return []
    effective_content = content if full_file_content is None else full_file_content
    try:
        tree = ast.parse(effective_content)
    except SyntaxError:
        return []
    constant_definitions, seed_collect_string_literals = _constants_under_check(tree)
    if not constant_definitions:
        return []
    scan_root = _scan_root_for_constants_module(file_path)
    written_path = Path(file_path).resolve()
    all_referenced_names, scanned_file_count, cap_was_hit = _all_referenced_names_under_root(
        scan_root,
        written_path,
        effective_content,
        seed_collect_string_literals=seed_collect_string_literals,
    )
    if cap_was_hit:
        return []
    has_unreferenced_constant = any(
        each_name not in all_referenced_names for each_name, _ in constant_definitions
    )
    if has_unreferenced_constant:
        repository_root = _repository_root_for(written_path)
        if repository_root is not None and repository_root != scan_root:
            widened_names, _widened_count, widened_cap_was_hit = _all_referenced_names_under_root(
                repository_root,
                written_path,
                effective_content,
                already_scanned_count=scanned_file_count,
                excluded_subtree=scan_root,
                seed_collect_string_literals=seed_collect_string_literals,
            )
            if widened_cap_was_hit:
                return []
            all_referenced_names |= widened_names
    issues: list[str] = []
    for each_name, each_line in constant_definitions:
        if each_name in all_referenced_names:
            continue
        issues.append(
            f"Line {each_line}: module-level constant {each_name!r}"
            f" - {DEAD_MODULE_CONSTANT_GUIDANCE}"
        )
        if len(issues) >= MAX_DEAD_MODULE_CONSTANT_ISSUES:
            break
    return issues
