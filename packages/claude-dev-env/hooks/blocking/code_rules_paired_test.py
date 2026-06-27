"""Public-function paired-test coverage check for ``code_rules_enforcer``.

The TDD gate ``tdd_enforcer.py`` requires a fresh test file to exist before a
production module is written, but it judges coverage at file granularity: a
module whose dedicated test file exercises some public functions while leaving
one untested still satisfies it. This check closes that gap from both write
orders, so a forgotten function gets a behavioral test before the
partially-covered module lands.

``check_public_function_missing_paired_test`` fires on the production-module
write: when a module has an established paired test suite — a stem-matched
``test_<stem>.py`` that already exercises at least one of the module's public
functions — a public function that suite references nowhere is flagged.

``check_test_file_omits_module_public_function`` fires on the stem-matched
test-file write, covering the reverse order in which the production module is
written before its test file exists. It resolves the production module the
written ``test_<stem>.py`` or ``<stem>_test.py`` file pairs with and flags every
public function the post-edit suite omits, so the gap that the production-side
check cannot see — because no suite existed when the module was written — is
caught when the test file lands.

Both checks stay conservative to keep false positives near zero:

- The production-side check runs only on a production module whose stem-matched
  test file already exists; a module with no dedicated test file is out of scope
  and left to the file-level TDD gate. The test-side check runs only on a
  stem-matched test file whose paired production module exists on disk.
- Either check fires only when the suite already covers at least one public
  function of the paired module — the signature of a maintained per-function
  suite rather than an unrelated or placeholder test file.
- A public function counts as covered when its name appears in any test file in
  the suite directory — imported, called, or named — so a function exercised by
  a differently-named sibling test still counts.
- ``main`` and underscore-prefixed functions are never required to carry a test.
- Test modules, hook infrastructure, config modules, migrations, workflow
  registries, and ``__init__`` modules are exempt as production targets.
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

from code_rules_path_utils import (  # noqa: E402
    is_config_file,
)
from code_rules_shared import (  # noqa: E402
    _scope_violations_to_changed_lines,
    is_hook_infrastructure,
    is_migration_file,
    is_test_file,
    is_workflow_registry_file,
)

from hooks_constants.paired_test_coverage_constants import (  # noqa: E402
    ALL_TEST_FILENAME_GLOBS,
    ANCESTOR_DIRECTORY_WALK_LIMIT,
    EXEMPT_PUBLIC_FUNCTION_NAMES,
    INIT_MODULE_FILENAME,
    MAX_PAIRED_TEST_COVERAGE_ISSUES,
    MAX_TEST_FILES_SCANNED,
    MINIMUM_COVERED_PUBLIC_FUNCTIONS,
    MISSING_PAIRED_TEST_GUIDANCE,
    PYTHON_SOURCE_SUFFIX,
    STEM_TEST_FILENAME_PREFIX,
    STEM_TEST_FILENAME_SUFFIX,
    TEST_SUITE_OMITS_FUNCTION_GUIDANCE,
    TESTS_DIRECTORY_NAME,
)


def _is_public_function_name(function_name: str) -> bool:
    """Return whether a function name is a public, test-worthy entry point.

    Args:
        function_name: The bare function name from a module-scope definition.

    Returns:
        True when the name does not start with an underscore and is not one of
        the conventionally untested entry points such as ``main``.
    """
    if function_name.startswith("_"):
        return False
    return function_name not in EXEMPT_PUBLIC_FUNCTION_NAMES


def _public_function_definitions(tree: ast.Module) -> list[tuple[str, int]]:
    """Return ``(name, line)`` for each module-scope public function definition.

    Args:
        tree: The parsed production module.

    Returns:
        One ``(name, definition_line)`` pair per module-scope public function,
        in source order.
    """
    all_definitions: list[tuple[str, int]] = []
    for each_statement in tree.body:
        if not isinstance(each_statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if _is_public_function_name(each_statement.name):
            all_definitions.append((each_statement.name, each_statement.lineno))
    return all_definitions


def _ancestor_tests_directories(start_directory: Path) -> list[Path]:
    """Return each ancestor's ``tests`` directory, nearest ancestor first.

    Args:
        start_directory: The directory holding the production module.

    Returns:
        Existing ``tests`` directories found by walking from start_directory
        toward the filesystem root, bounded by the ancestor walk limit.
    """
    all_candidate_directories = [start_directory, *start_directory.parents]
    all_tests_directories: list[Path] = []
    for each_directory in all_candidate_directories[:ANCESTOR_DIRECTORY_WALK_LIMIT]:
        candidate_tests_directory = each_directory / TESTS_DIRECTORY_NAME
        if candidate_tests_directory.is_dir():
            all_tests_directories.append(candidate_tests_directory)
    return all_tests_directories


def _stem_matched_test_path(module_path: Path) -> Path | None:
    """Return the first existing stem-matched test file for a module, or None.

    Args:
        module_path: The resolved path of the production module.

    Returns:
        The path of the first existing ``test_<stem>.py`` or ``<stem>_test.py``
        file — beside the module or under an ancestor ``tests`` directory — or
        None when the module has no dedicated test file.
    """
    module_directory = module_path.parent
    module_stem = module_path.stem
    flat_prefixed_name = STEM_TEST_FILENAME_PREFIX + module_stem + PYTHON_SOURCE_SUFFIX
    flat_suffixed_name = module_stem + STEM_TEST_FILENAME_SUFFIX
    all_candidate_paths = [
        module_directory / flat_prefixed_name,
        module_directory / flat_suffixed_name,
    ]
    for each_tests_directory in _ancestor_tests_directories(module_directory):
        all_candidate_paths.append(each_tests_directory / flat_prefixed_name)
    for each_candidate_path in all_candidate_paths:
        if each_candidate_path.is_file():
            return each_candidate_path
    return None


def _collect_referenced_identifiers(source: str) -> set[str]:
    """Return every identifier a test module references — imported, called, or named.

    Collects ``import`` binding names and ``from``-import member names, every
    ``Name`` node id, and every attribute access name, so a public function the
    test imports, calls bare, or reaches through an attribute all count as a
    reference. A module that fails to parse contributes no identifiers.

    Args:
        source: The full text of a test module.

    Returns:
        The set of identifiers the test module references.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    all_referenced_identifiers: set[str] = set()
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.Name):
            all_referenced_identifiers.add(each_node.id)
        elif isinstance(each_node, ast.Attribute):
            all_referenced_identifiers.add(each_node.attr)
        elif isinstance(each_node, (ast.Import, ast.ImportFrom)):
            for each_alias in each_node.names:
                all_referenced_identifiers.add(each_alias.asname or each_alias.name)
                all_referenced_identifiers.add(each_alias.name)
    return all_referenced_identifiers


def _suite_referenced_identifiers(stem_test_path: Path) -> set[str]:
    """Return identifiers referenced across every test file beside the stem test.

    Scans every ``test_*.py`` and ``*_test.py`` file in the directory holding the
    stem-matched test file, bounded by the scan cap, and unions the identifiers
    each one references.

    Args:
        stem_test_path: The stem-matched test file whose directory is scanned.

    Returns:
        The union of referenced identifiers across the scanned test files.
    """
    suite_directory = stem_test_path.parent
    all_test_file_paths: list[Path] = []
    for each_glob in ALL_TEST_FILENAME_GLOBS:
        all_test_file_paths.extend(sorted(suite_directory.glob(each_glob)))
    all_referenced_identifiers: set[str] = set()
    for each_test_file_path in all_test_file_paths[:MAX_TEST_FILES_SCANNED]:
        try:
            test_source = each_test_file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        all_referenced_identifiers |= _collect_referenced_identifiers(test_source)
    return all_referenced_identifiers


def _module_is_exempt(file_path: str) -> bool:
    """Return whether a path is exempt from the paired-test coverage check.

    Test modules, hook infrastructure, config modules, migrations, workflow
    registries, and package ``__init__`` re-export modules are all exempt.

    Args:
        file_path: The destination path of the write or edit.

    Returns:
        True when the paired-test coverage check must not run on this path.
    """
    if is_test_file(file_path):
        return True
    if is_hook_infrastructure(file_path):
        return True
    if is_config_file(file_path):
        return True
    if is_migration_file(file_path):
        return True
    if is_workflow_registry_file(file_path):
        return True
    return Path(file_path).name == INIT_MODULE_FILENAME


def check_public_function_missing_paired_test(
    content: str,
    file_path: str,
    all_changed_lines: set[int] | None = None,
    defer_scope_to_caller: bool = False,
) -> list[str]:
    """Flag a public function the module's established paired test suite omits.

    Runs only on a production module whose stem-matched ``test_<stem>.py`` already
    exists and already exercises at least one of the module's public functions.
    Under that established-suite precondition, a public function the suite
    references nowhere is flagged, so the forgotten function gets a behavioral
    test before the partially-covered module lands. ``main`` and
    underscore-prefixed functions are never required to carry a test, and test
    modules, hook infrastructure, config modules, migrations, workflow
    registries, and ``__init__`` modules are exempt.

    Args:
        content: The reconstructed post-edit whole-file content of the module.
        file_path: The destination path, used for the exemptions and to locate
            the module's paired test files on disk.
        all_changed_lines: Post-edit line numbers the current edit touched, or
            None to treat every public-function definition as in scope.
        defer_scope_to_caller: When True, return every violation so the
            commit/push gate scopes by added line.

    Returns:
        One violation per uncovered public function, capped at the configured
        maximum, scoped to the changed lines unless deferred or unscoped. Empty
        when the module is exempt, has no dedicated test file, the suite covers
        no public function, or the content fails to parse.
    """
    if _module_is_exempt(file_path):
        return []
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    all_public_definitions = _public_function_definitions(tree)
    if not all_public_definitions:
        return []
    stem_test_path = _stem_matched_test_path(Path(file_path).resolve())
    if stem_test_path is None:
        return []
    all_referenced_identifiers = _suite_referenced_identifiers(stem_test_path)
    covered_function_count = sum(
        1
        for each_name, _each_line in all_public_definitions
        if each_name in all_referenced_identifiers
    )
    if covered_function_count < MINIMUM_COVERED_PUBLIC_FUNCTIONS:
        return []
    all_violations_in_walk_order: list[tuple[range, str]] = []
    for each_name, each_definition_line in all_public_definitions:
        if each_name in all_referenced_identifiers:
            continue
        message = (
            f"Line {each_definition_line}: public function {each_name!r} "
            f"{MISSING_PAIRED_TEST_GUIDANCE}"
        )
        all_violations_in_walk_order.append(
            (range(each_definition_line, each_definition_line + 1), message)
        )
        if len(all_violations_in_walk_order) >= MAX_PAIRED_TEST_COVERAGE_ISSUES:
            break
    return _scope_violations_to_changed_lines(
        all_violations_in_walk_order,
        all_changed_lines,
        defer_scope_to_caller,
    )


def _production_stem_from_test_filename(test_filename: str) -> str | None:
    """Return the production-module stem a stem-matched test filename pairs with.

    Args:
        test_filename: The basename of the written file.

    Returns:
        The production stem for a ``test_<stem>.py`` or ``<stem>_test.py`` name,
        or None when the filename is not stem-matched or its stem is empty.
    """
    if test_filename.endswith(STEM_TEST_FILENAME_SUFFIX):
        production_stem = test_filename[: -len(STEM_TEST_FILENAME_SUFFIX)]
        return production_stem or None
    if test_filename.startswith(STEM_TEST_FILENAME_PREFIX) and test_filename.endswith(
        PYTHON_SOURCE_SUFFIX
    ):
        production_stem = test_filename[
            len(STEM_TEST_FILENAME_PREFIX) : -len(PYTHON_SOURCE_SUFFIX)
        ]
        return production_stem or None
    return None


def _paired_production_module_path(
    test_path: Path, production_stem: str
) -> Path | None:
    """Return the production module a stem-matched test file pairs with, or None.

    Mirrors ``_stem_matched_test_path`` in reverse for the two common layouts: a
    module beside the test file, and a module in the parent of the ``tests``
    directory that directly holds the test file.

    Args:
        test_path: The resolved path of the written stem-matched test file.
        production_stem: The production-module stem the test filename names.

    Returns:
        The first candidate production module path that exists on disk, or None
        when no candidate module file exists.
    """
    production_filename = production_stem + PYTHON_SOURCE_SUFFIX
    test_directory = test_path.parent
    all_candidate_paths = [test_directory / production_filename]
    if test_directory.name == TESTS_DIRECTORY_NAME:
        all_candidate_paths.append(test_directory.parent / production_filename)
    for each_candidate_path in all_candidate_paths:
        if each_candidate_path.is_file():
            return each_candidate_path
    return None


def _post_edit_suite_referenced_identifiers(
    suite_directory: Path,
    written_test_path: Path,
    written_test_content: str,
) -> set[str]:
    """Return suite identifiers, reading the written test's post-edit content.

    Scans every ``test_*.py`` and ``*_test.py`` file in the suite directory,
    bounded by the scan cap, and unions the identifiers each references. The
    written test file contributes ``written_test_content`` rather than its stale
    on-disk text, so the post-edit suite is judged.

    Args:
        suite_directory: The directory holding the suite's test files.
        written_test_path: The resolved path of the test file being written.
        written_test_content: The post-edit text of the written test file.

    Returns:
        The union of referenced identifiers across the post-edit suite.
    """
    all_test_file_paths: list[Path] = []
    for each_glob in ALL_TEST_FILENAME_GLOBS:
        all_test_file_paths.extend(sorted(suite_directory.glob(each_glob)))
    written_path_key = os.path.normcase(str(written_test_path))
    all_referenced_identifiers = _collect_referenced_identifiers(written_test_content)
    for each_test_file_path in all_test_file_paths[:MAX_TEST_FILES_SCANNED]:
        if os.path.normcase(str(each_test_file_path.resolve())) == written_path_key:
            continue
        try:
            test_source = each_test_file_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        all_referenced_identifiers |= _collect_referenced_identifiers(test_source)
    return all_referenced_identifiers


def check_test_file_omits_module_public_function(
    content: str,
    file_path: str,
) -> list[str]:
    """Flag a public function the written test file's paired suite omits.

    The companion of ``check_public_function_missing_paired_test`` for the
    reverse write order: when a production module is written before its test
    file, the production-side check sees no suite yet and the omission slips
    through, so this check fires on the stem-matched test-file write instead. It
    resolves the production module the written ``test_<stem>.py`` or
    ``<stem>_test.py`` file pairs with, and when the post-edit suite already
    covers at least one of that module's public functions, flags every public
    function the suite references nowhere. ``main`` and underscore-prefixed
    functions are never required to carry a test, and a production module that is
    itself exempt — a test module, hook infrastructure, config module, migration,
    workflow registry, or ``__init__`` module — is skipped.

    Args:
        content: The reconstructed post-edit whole-file content of the test file.
        file_path: The destination path of the written test file, used to resolve
            its paired production module on disk.

    Returns:
        One violation per public function the suite omits, capped at the
        configured maximum. Empty when the file is not a stem-matched test file,
        no paired production module exists on disk, the production module is
        exempt or defines no public function, or the suite covers none of the
        module's public functions.
    """
    production_stem = _production_stem_from_test_filename(Path(file_path).name)
    if production_stem is None:
        return []
    test_path = Path(file_path).resolve()
    production_module_path = _paired_production_module_path(test_path, production_stem)
    if production_module_path is None:
        return []
    if _module_is_exempt(str(production_module_path)):
        return []
    try:
        production_source = production_module_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    try:
        production_tree = ast.parse(production_source)
    except SyntaxError:
        return []
    all_public_definitions = _public_function_definitions(production_tree)
    if not all_public_definitions:
        return []
    all_referenced_identifiers = _post_edit_suite_referenced_identifiers(
        test_path.parent, test_path, content
    )
    covered_function_count = sum(
        1
        for each_name, _each_line in all_public_definitions
        if each_name in all_referenced_identifiers
    )
    if covered_function_count < MINIMUM_COVERED_PUBLIC_FUNCTIONS:
        return []
    production_module_name = production_module_path.name
    all_violations: list[str] = []
    for each_name, each_definition_line in all_public_definitions:
        if each_name in all_referenced_identifiers:
            continue
        all_violations.append(
            f"{production_module_name} line {each_definition_line}: public function "
            f"{each_name!r} {TEST_SUITE_OMITS_FUNCTION_GUIDANCE}"
        )
        if len(all_violations) >= MAX_PAIRED_TEST_COVERAGE_ISSUES:
            break
    return all_violations

