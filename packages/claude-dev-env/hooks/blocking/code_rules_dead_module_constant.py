"""Dead module-level constant check for dedicated constants modules.

A constants module (`*_constants.py`, or any module under a ``config/``
directory) exists to export named values to importer modules elsewhere in the
project, so a constant defined there is never proven dead by a single-file scan
alone. This check resolves the enclosing package tree — the scan root — and
flags an UPPER_SNAKE constant defined in the written module whose name appears
in no ``.py`` module anywhere under that root: not as an imported name, not as a
read, not as a re-export. That is the ``MEDIUM_TEXT``-style dead constant the
CODE_RULES §9.8 dead-code rule targets, caught at Write/Edit time before the
unused constant lands.

The scan is deliberately conservative to keep false positives near zero:

- Only dedicated constants modules participate; ordinary production modules,
  whose file-global constants are governed by the use-count rule, are skipped.
- A module declaring ``__all__`` is skipped: the author has named its export
  surface explicitly, so a name listed there is live by declaration and a name
  absent there is the author's stated intent, neither of which this check second
  guesses.
- A constant is live when its name appears anywhere under the scan root —
  imported, read, listed in ``__all__``, or referenced in a string annotation —
  in any ``.py`` module, including the constants module itself.
- Test modules under the scan root still count as references, so a constant used
  only by a test stays live.
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


def _referenced_names_in_source(source: str, load_only: bool = False) -> set[str]:
    """Return every name a module references — imported, read, or re-exported.

    Collects imported binding names, ``from`` import member names, name
    references, attribute roots, and string literals (so a name listed in an
    ``__all__`` literal or named in a string annotation counts as a reference).
    A module that fails to parse contributes no names. With ``load_only`` set,
    only ``Load``-context names count, so a constant's own assignment target in
    the module being judged does not count as a reference to itself.

    Args:
        source: The full text of a ``.py`` module under the scan root.
        load_only: When True, count only ``Load``-context name references,
            excluding ``Store``/``Del`` targets. Used for the written constants
            module so a definition is not mistaken for its own consumer.

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
        elif isinstance(each_node, ast.Constant) and isinstance(each_node.value, str):
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


def _all_referenced_names_under_root(
    scan_root: Path,
    written_path: Path,
    written_content: str,
) -> tuple[set[str], bool]:
    """Return referenced names under the scan root and whether the file cap was hit.

    The written module's on-disk text is replaced by ``written_content`` so the
    post-edit view is judged, never the stale disk copy. Sibling modules are
    read from disk. Reading stops after the configured file cap so a write under
    an unexpectedly large tree cannot stall the hook; the boolean signals the
    caller to treat that case as "cannot prove dead".

    Args:
        scan_root: The directory tree to scan.
        written_path: The resolved path of the module being written.
        written_content: The post-edit text of the written module.

    Returns:
        A (referenced_names, cap_was_hit) pair. The name set is the union across
        every scanned module; cap_was_hit is True when the scan stopped at the
        configured file cap before scanning the whole tree.
    """
    all_referenced_names = _referenced_names_in_source(written_content, load_only=True)
    written_path_key = os.path.normcase(str(written_path))
    scanned_file_count = 1
    for each_path in scan_root.rglob("*" + PYTHON_SOURCE_SUFFIX):
        if not each_path.is_file():
            continue
        if os.path.normcase(str(each_path.resolve())) == written_path_key:
            continue
        scanned_file_count += 1
        if scanned_file_count > MAX_SCAN_ROOT_FILE_COUNT:
            return all_referenced_names, True
        try:
            sibling_source = each_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        all_referenced_names |= _referenced_names_in_source(sibling_source)
    return all_referenced_names, False


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


def check_dead_module_constants(
    content: str,
    file_path: str,
    full_file_content: str | None = None,
) -> list[str]:
    """Flag an UPPER_SNAKE constant in a constants module read by no module.

    Runs only on a dedicated constants module (``*_constants.py`` or a module
    under ``config/``); every other production module's file-global constants
    are governed by the use-count rule instead. A constant is dead when its name
    appears in no ``.py`` module anywhere under the enclosing package tree — not
    imported, not read, not listed in an ``__all__`` literal, not named in a
    string annotation. A module declaring its own ``__all__`` is skipped so the
    author's explicit export surface is never second-guessed. Whole-file
    analysis runs against ``full_file_content`` when supplied so an Edit fragment
    is judged against the reconstructed post-edit file.

    Args:
        content: The new content under validation (Edit fragment or whole file).
        file_path: The destination path, used for the constants-module gate and
            the test/registry exemptions.
        full_file_content: The reconstructed post-edit whole-file content for an
            Edit, or None for a Write where ``content`` is already the whole file.

    Returns:
        One violation message per dead module-level constant, capped at the
        configured maximum.
    """
    if _module_is_exempt_from_constant_check(file_path):
        return []
    effective_content = content if full_file_content is None else full_file_content
    try:
        tree = ast.parse(effective_content)
    except SyntaxError:
        return []
    if _module_declares_dunder_all(tree):
        return []
    constant_definitions = _module_constant_definitions(tree)
    if not constant_definitions:
        return []
    scan_root = _scan_root_for_constants_module(file_path)
    written_path = Path(file_path).resolve()
    all_referenced_names, cap_was_hit = _all_referenced_names_under_root(
        scan_root,
        written_path,
        effective_content,
    )
    if cap_was_hit:
        return []
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
