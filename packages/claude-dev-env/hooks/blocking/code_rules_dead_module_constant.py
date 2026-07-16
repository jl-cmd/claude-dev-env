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
  the repository root (the nearest ``.git`` ancestor). The widened pass counts a
  sibling-tree reference only when a module imports the name through a
  ``from <module> import`` whose final dotted segment equals the written
  module's filename stem, so a genuine cross-tree consumer of this constants
  module keeps the constant live while a same-named constant exported by an
  unrelated module never masks a dead one. The widened pass reads a repository
  file only to test whether its text names the written module's filename stem;
  a file that never mentions the stem cannot carry such an import, so it is
  skipped without spending scan-cap budget, keeping the widened pass bounded to
  the handful of candidate importer files even in a large repository. A module
  outside any repository is
  judged on the package-tree scan alone, and the widened pass skips the package
  subtree the first pass already covered, so no file is read twice.
- Two caps bound the widened pass: a read-attempt cap bounds how many files
  the pass opens and reads at all while testing for the stem, and a separate
  parse cap bounds how many of those files (the ones that do name the stem)
  get parsed and have their names collected. Either cap bounds the pass even
  under an unexpectedly large tree; a write whose scan hits either cap is
  treated as "cannot prove dead" and flags nothing.
- Test modules under the scanned tree still count as references, so a constant
  used only by a test stays live.
"""

import ast
import os
import sys
from collections.abc import Callable
from functools import partial
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
    DEAD_MODULE_CONSTANT_RETRY_GUIDANCE,
    DUNDER_ALL_NAME,
    DUNDER_INIT_FILENAME,
    GIT_DIRECTORY_NAME,
    MAX_DEAD_MODULE_CONSTANT_ISSUES,
    MAX_SCAN_ROOT_FILE_COUNT,
    MAX_SCAN_ROOT_READ_COUNT,
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
    references, both the root and the member name of each attribute access (so
    ``module.CONSTANT`` counts ``CONSTANT`` as read), and (when
    ``collect_string_literals`` is set) string literals, so a name listed in an
    ``__all__`` literal or named in a string annotation counts as a reference. A
    module that fails to parse
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
        elif isinstance(each_node, ast.Attribute):
            referenced_names.add(each_node.attr)
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


def _module_final_segment(module_path: str | None) -> str:
    """Return the final dotted segment of an import module path.

    Args:
        module_path: The ``module`` attribute of a ``from ... import`` node, or
            None for a bare relative import (``from . import x``).

    Returns:
        The text after the last dot, the whole string when it carries no dot, or
        the empty string when ``module_path`` is None or empty.
    """
    if not module_path:
        return ""
    return module_path.rsplit(".", 1)[-1]


def _qualified_import_member_names(source: str, module_stem: str) -> set[str]:
    """Return names imported from a module whose filename stem is ``module_stem``.

    A cross-package consumer of an exported constant imports it through an
    explicit ``from <module> import NAME`` whose module path ends in the defining
    module's filename stem. Collecting only those member names binds a
    widened-scan reference to the module that actually defines the constant, so a
    same-named constant exported by an unrelated module never masks a dead one.

    Args:
        source: The full text of a ``.py`` module under the repository root.
        module_stem: The filename stem of the constants module being judged.

    Returns:
        The member names imported from a module whose final dotted segment equals
        ``module_stem``. A module that fails to parse contributes no names.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    member_names: set[str] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.ImportFrom):
            continue
        if _module_final_segment(each_node.module) != module_stem:
            continue
        for each_alias in each_node.names:
            member_names.add(each_alias.name)
    return member_names


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


def _read_candidate_source(file_path: Path, required_substring: str | None) -> str | None:
    """Return a module's text, or None when it is not a reference-scan candidate.

    ::

        required_substring = None                 -> read and keep every file
        required_substring = the module stem      -> keep only files naming it
            from pkg.foo_constants import BAR  ->  names the stem  ->  candidate
            def unrelated() -> int: ...        ->  no stem mention ->  skipped

    The widened repository pass looks only for a ``from <module> import`` whose
    final dotted segment equals the constants module's filename stem, and such an
    import always spells that stem in the file's text. A file whose text never
    mentions the stem cannot carry the import, so returning None for it lets the
    caller skip the file without spending scan-cap budget, which keeps the widened
    pass bounded to the candidate importer files even under a large repository.

    Args:
        file_path: The ``.py`` module to read.
        required_substring: A stem every candidate file's text must contain, or
            None to keep every readable file (the package-tree pass keeps all).

    Returns:
        The file's text when it is readable and, when ``required_substring`` is
        set, contains that stem; None when the file cannot be read or does not
        name the stem.
    """
    try:
        source_text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    if required_substring is not None and required_substring not in source_text:
        return None
    return source_text


def _collect_names_under_root(
    scan_root: Path,
    written_path: Path,
    all_seed_names: set[str],
    extract_names: Callable[[str], set[str]],
    already_scanned_count: int = 0,
    excluded_subtree: Path | None = None,
    required_substring: str | None = None,
) -> tuple[set[str], int, bool]:
    """Collect referenced names under the scan root via a per-module extractor.

    Walks every ``.py`` module under ``scan_root`` (excluding the written module
    itself, and any module under ``excluded_subtree``), applies ``extract_names``
    to each module's text, and unions the result onto ``all_seed_names``. Two
    caps bound the walk so a write under an unexpectedly large tree cannot
    stall the hook:

    ::

        read_attempt_count  -> every file this call opens and reads,
                                whether or not it turns out to be a
                                candidate -> capped by MAX_SCAN_ROOT_READ_COUNT
        scanned_file_count  -> only the files that pass the candidate
                                filter and get parsed for names       -> capped
                                by MAX_SCAN_ROOT_FILE_COUNT

    Either cap tripping returns ``cap_was_hit=True``, which signals the caller
    to treat the write as "cannot prove dead". The ``excluded_subtree`` skip
    keeps the widened repository scan from re-reading a file the package-tree
    scan already covered. When ``required_substring`` is set, a module whose
    text never contains that stem is skipped after being read but before it is
    counted toward ``scanned_file_count`` or parsed, so the parse-and-collect
    work stays bounded to the candidate importer files even though the read
    cap still bounds the raw disk reads across the whole tree.

    Args:
        scan_root: The directory tree to scan.
        written_path: The resolved path of the module being written, skipped so
            its own text is judged through ``all_seed_names`` rather than the
            stale disk copy.
        all_seed_names: The names the written module itself contributes, unioned
            in before the walk begins.
        extract_names: Maps one module's source text to the set of names it
            contributes — the generous reference collector for the package-tree
            pass, the stem-bound import collector for the widened pass.
        already_scanned_count: The parsed-file count accumulated by a prior
            pass, so the parse cap bounds the combined work of the
            package-tree and widened passes.
        excluded_subtree: A resolved directory whose ``.py`` modules are skipped,
            or None to scan every file under the root.
        required_substring: A stem a file's text must contain to count as a
            scan candidate, or None to scan every file. The widened pass passes
            the written module's filename stem so a file that never names the
            module is skipped before it is counted or parsed, spending parse
            budget only on the candidate importer files, while the read cap
            still bounds how many files get read looking for that stem.

    Returns:
        A (collected_names, running_count, cap_was_hit) triple. collected_names
        is ``all_seed_names`` unioned with every scanned module's contribution;
        running_count is the cumulative file count including
        ``already_scanned_count``; cap_was_hit is True when the scan stopped at
        the configured file cap before scanning the whole tree.
    """
    collected_names = set(all_seed_names)
    written_path_key = os.path.normcase(str(written_path))
    scanned_file_count = already_scanned_count
    read_attempt_count = 0
    for each_path in scan_root.rglob("*" + PYTHON_SOURCE_SUFFIX):
        if not each_path.is_file():
            continue
        resolved_path = each_path.resolve()
        if os.path.normcase(str(resolved_path)) == written_path_key:
            continue
        if excluded_subtree is not None and _is_under_directory(resolved_path, excluded_subtree):
            continue
        read_attempt_count += 1
        if read_attempt_count > MAX_SCAN_ROOT_READ_COUNT:
            return collected_names, scanned_file_count, True
        sibling_source = _read_candidate_source(each_path, required_substring)
        if sibling_source is None:
            continue
        scanned_file_count += 1
        if scanned_file_count > MAX_SCAN_ROOT_FILE_COUNT:
            return collected_names, scanned_file_count, True
        collected_names |= extract_names(sibling_source)
    return collected_names, scanned_file_count, False


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
    appears in no ``.py`` module under the enclosing package tree — not imported,
    not read, not listed in another module's ``__all__`` literal, not named in a
    string annotation — and, in the repository-wide scan the check widens to when
    the package-tree scan leaves the constant unreferenced, no module imports the
    name from a ``from <module> import`` whose final dotted segment equals this
    module's filename stem. Binding the widened scan to the stem keeps a genuine
    cross-tree consumer counting while a same-named constant exported by an
    unrelated module never masks a dead one. A module declaring ``__all__``
    narrows the check to the constants its ``__all__`` list names: each must be
    imported or read by another module, and the module's own ``__all__`` entry
    never counts as that consumer, so an exported constant no module consumes is
    flagged; a constant the module defines but ``__all__`` omits is the author's
    private value and is left alone. A scan whose combined package-tree and
    widened file count exceeds the configured cap returns ``[]`` (cannot prove
    dead), bounding the work so the blocking hook cannot stall under a large tree.
    Whole-file analysis runs against ``full_file_content`` when supplied so an
    Edit fragment is judged against the reconstructed post-edit file.

    Args:
        content: The new content under validation (Edit fragment or whole file).
        file_path: The destination path, used for the constants-module gate and
            the test/registry exemptions.
        full_file_content: The reconstructed post-edit whole-file content for an
            Edit, or None for a Write where ``content`` is already the whole file.

    Returns:
        One violation message per dead module-level constant, capped at the
        configured maximum. Returns an empty list when the file is exempt, the
        path is relative (the scan root cannot be resolved against a known
        base, so the check cannot prove a constant dead), no constant is in
        scope (none defined, or none exported when ``__all__`` is declared),
        the scan exceeds the file cap, or a SyntaxError prevents parsing.
    """
    if _module_is_exempt_from_constant_check(file_path):
        return []
    if not Path(file_path).is_absolute():
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
    written_seed_names = _referenced_names_in_source(
        effective_content,
        load_only=True,
        collect_string_literals=seed_collect_string_literals,
    )
    all_referenced_names, scanned_file_count, cap_was_hit = _collect_names_under_root(
        scan_root,
        written_path,
        written_seed_names,
        _referenced_names_in_source,
    )
    if cap_was_hit:
        return []
    has_unreferenced_constant = any(
        each_name not in all_referenced_names for each_name, _ in constant_definitions
    )
    if has_unreferenced_constant:
        repository_root = _repository_root_for(written_path)
        if repository_root is not None and repository_root != scan_root:
            collect_qualified_imports = partial(
                _qualified_import_member_names, module_stem=written_path.stem
            )
            widened_names, _widened_count, widened_cap_was_hit = _collect_names_under_root(
                repository_root,
                written_path,
                set(),
                collect_qualified_imports,
                already_scanned_count=scanned_file_count,
                excluded_subtree=scan_root,
                required_substring=written_path.stem,
            )
            if widened_cap_was_hit:
                return []
            all_referenced_names |= widened_names
    issues: list[str] = []
    for each_name, each_line in constant_definitions:
        if each_name in all_referenced_names:
            continue
        issues.append(
            f"Line {each_line}: module-level constant {each_name!r} in"
            f" {written_path.name} - {DEAD_MODULE_CONSTANT_GUIDANCE}"
            f" {DEAD_MODULE_CONSTANT_RETRY_GUIDANCE}"
        )
        if len(issues) >= MAX_DEAD_MODULE_CONSTANT_ISSUES:
            break
    return issues
