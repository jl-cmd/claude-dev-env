"""Gate a split plan on cross-file symbol dependencies before any git mutation.

A file-based split cuts the symbol graph along file lines. A slice can then read
a name whose only definition lands in a later slice. Collection never sees it.
The read sits inside a function body, so imports resolve and
``pytest --collect-only`` passes green. A per-slice test run misses it too,
because nothing calls the new code until a later slice wires it up. Merging any
prefix of such a stack puts importable-but-broken code on the base branch.

Two constraints pull in opposite directions, and both are checked here:

- **Runtime.** A definition must land no later than its first reader.
- **Dead-config gate.** A config dataclass field must land no earlier than a
  production module that reads it, or the pre-commit gate rejects that slice.

When both fire on one file, no ordering works. That file has to ship together
with enough readers to cover its new fields. The report names the smallest such
set, so the operator does not guess.

::

    verify_slice_dependencies(all_slices, all_sources_by_path)
    # ok:   is_valid True when every slice prefix is closed under references
    # flag: forward_references when a definition lands after its reader
    # flag: unread_config_fields when a config field lands before its reader
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

from split_pr_scripts_constants.config.dependency_constants import (
    ALL_CONFIG_CLASS_NAME_SUFFIXES,
    ALL_MIGRATION_PATH_MARKERS,
    ALL_TEST_PATH_MARKERS,
    ERROR_COALESCE_HINT,
    ERROR_CONTRADICTION,
    ERROR_FORWARD_REFERENCE,
    ERROR_UNREAD_CONFIG_FIELD,
    EXIT_CODE_FAILURE,
    EXIT_CODE_SUCCESS,
    JSON_INDENT_SPACES,
    LIST_JOIN_SEPARATOR,
    PYTHON_FILE_SUFFIX,
    REPORT_KEY_COALESCE_SUGGESTION,
    REPORT_KEY_CONTRADICTIONS,
    REPORT_KEY_ERRORS,
    REPORT_KEY_FORWARD_REFERENCES,
    REPORT_KEY_IS_VALID,
    REPORT_KEY_UNREAD_CONFIG_FIELDS,
    SLICE_KEY_FILES,
    SLICE_KEY_INDEX,
    SLICE_KEY_SLUG,
    STAR_IMPORT_NAME,
    VIOLATION_KEY_CURRENT_SLICE,
    VIOLATION_KEY_DEFINING_SLICE,
    VIOLATION_KEY_EARLIEST_READER_SLICE,
    VIOLATION_KEY_FIELD,
    VIOLATION_KEY_FILE,
    VIOLATION_KEY_REFERENCING_SLICE,
    VIOLATION_KEY_SLICE,
    VIOLATION_KEY_SYMBOL,
    VIOLATION_KEY_UNCOVERED_FIELDS,
)

JsonObject = dict[str, object]


def is_python_path(path: str) -> bool:
    """Return whether a repository path names a Python module.

    ::

        is_python_path("src/a.py")   # ok: True
        is_python_path("docs/a.md")  # ok: False

    Args:
        path: Repository-relative path.

    Returns:
        True when the path ends in the Python suffix.
    """
    return path.replace("\\", "/").lower().endswith(PYTHON_FILE_SUFFIX)


def is_production_path(path: str) -> bool:
    """Return whether a path counts as a production reader.

    Mirrors the dead-config-field hook, which excludes test and migration
    modules. A field read only by a test is still reported dead.

    ::

        is_production_path("src/a.py")        # ok: True
        is_production_path("tests/test_a.py") # ok: False

    Args:
        path: Repository-relative path.

    Returns:
        True when the path is neither a test nor a migration module.
    """
    normalized = path.replace("\\", "/")
    basename = normalized.rsplit("/", 1)[-1]
    for each_marker in ALL_TEST_PATH_MARKERS:
        if each_marker in normalized or basename.startswith(each_marker):
            return False
    return not any(each_marker in normalized for each_marker in ALL_MIGRATION_PATH_MARKERS)


def parse_source(source_text: str) -> ast.Module | None:
    """Parse Python source, returning None when it cannot be parsed.

    A plan may name a file this analysis cannot read. Returning None keeps one
    unparsable file from failing the whole plan.

    Args:
        source_text: File contents.

    Returns:
        The parsed module, or None on a syntax error.
    """
    try:
        return ast.parse(source_text)
    except (SyntaxError, ValueError):
        return None


def collect_config_field_definitions(source_text: str) -> set[str]:
    """Return field names of config-like dataclasses in one module.

    Args:
        source_text: File contents.

    Returns:
        Annotated field names on classes whose name ends in a config suffix.
    """
    tree = parse_source(source_text)
    if tree is None:
        return set()
    all_collected: set[str] = set()
    for each_node in ast.walk(tree):
        if not isinstance(each_node, ast.ClassDef):
            continue
        if not each_node.name.endswith(ALL_CONFIG_CLASS_NAME_SUFFIXES):
            continue
        for each_statement in each_node.body:
            if isinstance(each_statement, ast.AnnAssign) and isinstance(
                each_statement.target, ast.Name
            ):
                all_collected.add(each_statement.target.id)
    return all_collected


def collect_top_level_definitions(source_text: str) -> set[str]:
    """Return module-level bindings, functions, and classes.

    Args:
        source_text: File contents.

    Returns:
        Every name the module binds at top level, plus its config field names.
    """
    tree = parse_source(source_text)
    if tree is None:
        return set()
    all_collected: set[str] = set()
    for each_statement in tree.body:
        if isinstance(
            each_statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            all_collected.add(each_statement.name)
        elif isinstance(each_statement, ast.Assign):
            for each_target in each_statement.targets:
                if isinstance(each_target, ast.Name):
                    all_collected.add(each_target.id)
        elif isinstance(each_statement, ast.AnnAssign) and isinstance(
            each_statement.target, ast.Name
        ):
            all_collected.add(each_statement.target.id)
    return all_collected | collect_config_field_definitions(source_text)


def collect_attribute_reads(source_text: str) -> set[str]:
    """Return attribute names read anywhere in a module.

    These are the references collection cannot reach. An attribute read inside a
    function body never executes during import.

    Args:
        source_text: File contents.

    Returns:
        Every attribute name loaded in the module.
    """
    tree = parse_source(source_text)
    if tree is None:
        return set()
    return {
        each_node.attr
        for each_node in ast.walk(tree)
        if isinstance(each_node, ast.Attribute) and isinstance(each_node.ctx, ast.Load)
    }


def collect_imported_names(source_text: str) -> set[str]:
    """Return names pulled in by ``from ... import`` statements.

    ::

        collect_imported_names("from x import Y")  # ok: {"Y"}

    Args:
        source_text: File contents.

    Returns:
        Every imported name, ignoring star imports.
    """
    tree = parse_source(source_text)
    if tree is None:
        return set()
    all_collected: set[str] = set()
    for each_node in ast.walk(tree):
        if isinstance(each_node, ast.ImportFrom):
            all_collected |= {
                each_alias.name
                for each_alias in each_node.names
                if each_alias.name != STAR_IMPORT_NAME
            }
    return all_collected


def _definition_slice_by_symbol(
    all_slices: list[JsonObject],
    all_sources_by_path: dict[str, str],
) -> dict[str, int]:
    """Map each symbol a changed file defines to the slice that lands it."""
    all_definition_slices: dict[str, int] = {}
    for each_slice in all_slices:
        slice_index = int(each_slice[SLICE_KEY_INDEX])
        for each_path in each_slice.get(SLICE_KEY_FILES) or []:
            if not is_python_path(str(each_path)):
                continue
            source_text = all_sources_by_path.get(str(each_path))
            if source_text is None:
                continue
            for each_name in collect_top_level_definitions(source_text):
                all_definition_slices.setdefault(each_name, slice_index)
    return all_definition_slices


def _collect_forward_references(
    all_slices: list[JsonObject],
    all_sources_by_path: dict[str, str],
    all_definition_slices: dict[str, int],
) -> list[JsonObject]:
    """Report references whose only definition lands in a later slice."""
    all_violations: list[JsonObject] = []
    for each_slice in all_slices:
        slice_index = int(each_slice[SLICE_KEY_INDEX])
        for each_path in each_slice.get(SLICE_KEY_FILES) or []:
            source_text = all_sources_by_path.get(str(each_path))
            if source_text is None or not is_python_path(str(each_path)):
                continue
            all_references = collect_attribute_reads(
                source_text
            ) | collect_imported_names(source_text)
            for each_symbol in sorted(all_references):
                defining_index = all_definition_slices.get(each_symbol)
                if defining_index is None or defining_index <= slice_index:
                    continue
                all_violations.append({
                    VIOLATION_KEY_SYMBOL: each_symbol,
                    VIOLATION_KEY_FILE: str(each_path),
                    VIOLATION_KEY_REFERENCING_SLICE: slice_index,
                    VIOLATION_KEY_DEFINING_SLICE: defining_index,
                })
    return all_violations


def _production_readers_by_field(
    all_slices: list[JsonObject],
    all_sources_by_path: dict[str, str],
) -> dict[str, list[tuple[int, str]]]:
    """Map each attribute name to the production files that read it."""
    all_readers_by_field: dict[str, list[tuple[int, str]]] = {}
    for each_slice in all_slices:
        slice_index = int(each_slice[SLICE_KEY_INDEX])
        for each_path in each_slice.get(SLICE_KEY_FILES) or []:
            path_text = str(each_path)
            source_text = all_sources_by_path.get(path_text)
            if source_text is None or not is_python_path(path_text):
                continue
            if not is_production_path(path_text):
                continue
            for each_name in collect_attribute_reads(source_text):
                all_readers_by_field.setdefault(each_name, []).append(
                    (slice_index, path_text)
                )
    return all_readers_by_field


def _earlier_readers(
    field_name: str,
    slice_index: int,
    defining_path: str,
    all_readers_by_field: dict[str, list[tuple[int, str]]],
) -> list[str]:
    """Return production files reading a field at or before a slice."""
    return [
        each_reader_path
        for each_reader_index, each_reader_path in all_readers_by_field.get(
            field_name, []
        )
        if each_reader_index <= slice_index and each_reader_path != defining_path
    ]


def _collect_unread_config_fields(
    all_slices: list[JsonObject],
    all_sources_by_path: dict[str, str],
    all_readers_by_field: dict[str, list[tuple[int, str]]],
) -> list[JsonObject]:
    """Report config fields with no production reader at or before their slice."""
    all_violations: list[JsonObject] = []
    for each_slice in all_slices:
        slice_index = int(each_slice[SLICE_KEY_INDEX])
        for each_path in each_slice.get(SLICE_KEY_FILES) or []:
            path_text = str(each_path)
            source_text = all_sources_by_path.get(path_text)
            if source_text is None or not is_python_path(path_text):
                continue
            for each_field in sorted(collect_config_field_definitions(source_text)):
                if _earlier_readers(
                    each_field, slice_index, path_text, all_readers_by_field
                ):
                    continue
                all_violations.append({
                    VIOLATION_KEY_FIELD: each_field,
                    VIOLATION_KEY_FILE: path_text,
                    VIOLATION_KEY_SLICE: slice_index,
                })
    return all_violations


def _coalesce_suggestion(
    all_unread: list[JsonObject],
    all_readers_by_field: dict[str, list[tuple[int, str]]],
) -> list[str]:
    """Return the smallest file set covering every unread config field.

    Greedy set cover over the production readers. This is what keeps the
    suggestion smaller than "ship every consumer together": the gate needs one
    reader per field, not every reader of every field.

    Args:
        all_unread: Unread-config-field violations.
        all_readers_by_field: Production readers keyed by attribute name.

    Returns:
        Sorted file paths to ship in one slice, empty when nothing is unread.
    """
    if not all_unread:
        return []
    all_defining_files = {str(each[VIOLATION_KEY_FILE]) for each in all_unread}
    all_uncovered = {str(each[VIOLATION_KEY_FIELD]) for each in all_unread}
    all_chosen: set[str] = set(all_defining_files)
    all_candidate_fields: dict[str, set[str]] = {}
    for each_field in all_uncovered:
        for _, each_reader_path in all_readers_by_field.get(each_field, []):
            if each_reader_path in all_defining_files:
                continue
            all_candidate_fields.setdefault(each_reader_path, set()).add(each_field)
    while all_uncovered and all_candidate_fields:
        best_path = max(
            sorted(all_candidate_fields),
            key=lambda each_path: len(all_candidate_fields[each_path] & all_uncovered),
        )
        all_gained = all_candidate_fields[best_path] & all_uncovered
        if not all_gained:
            break
        all_chosen.add(best_path)
        all_uncovered -= all_gained
        del all_candidate_fields[best_path]
    return sorted(all_chosen)


def _earliest_reader_slice_by_file(
    all_forward_references: list[JsonObject],
    all_sources_by_path: dict[str, str],
    all_slices_by_file: dict[str, int],
) -> dict[str, int]:
    """Map each defining file to the earliest slice that reads from it."""
    all_earliest: dict[str, int] = {}
    for each_reference in all_forward_references:
        defining_index = int(each_reference[VIOLATION_KEY_DEFINING_SLICE])
        symbol = str(each_reference[VIOLATION_KEY_SYMBOL])
        referencing_index = int(each_reference[VIOLATION_KEY_REFERENCING_SLICE])
        for each_path, each_index in all_slices_by_file.items():
            if each_index != defining_index:
                continue
            source_text = all_sources_by_path.get(each_path, "")
            if symbol not in collect_top_level_definitions(source_text):
                continue
            all_earliest[each_path] = min(
                all_earliest.get(each_path, referencing_index), referencing_index
            )
    return all_earliest


def _detect_contradictions(
    all_forward_references: list[JsonObject],
    all_sources_by_path: dict[str, str],
    all_base_fields: set[str],
    all_readers_by_field: dict[str, list[tuple[int, str]]],
    all_slices_by_file: dict[str, int],
) -> list[JsonObject]:
    """Report defining files that no reordering can place correctly.

    Moving a defining file earlier satisfies its readers. A config module moved
    ahead of every reader of one of its new fields is then rejected by the
    dead-config-field gate. When both hold, no position works, and the file must
    ship with enough readers to cover its new fields.

    Args:
        all_forward_references: Violations from the runtime constraint.
        all_sources_by_path: Source text keyed by path.
        all_base_fields: Config fields the base branch already carries.
        all_readers_by_field: Production readers keyed by attribute name.
        all_slices_by_file: Slice index each file currently lands in.

    Returns:
        One record per file whose two constraints conflict, with a coalesce set.
    """
    all_earliest = _earliest_reader_slice_by_file(
        all_forward_references, all_sources_by_path, all_slices_by_file
    )
    all_contradictions: list[JsonObject] = []
    for each_path, each_target_index in sorted(all_earliest.items()):
        all_new_fields = (
            collect_config_field_definitions(all_sources_by_path.get(each_path, ""))
            - all_base_fields
        )
        all_uncovered = sorted(
            each_field
            for each_field in all_new_fields
            if not _earlier_readers(
                each_field, each_target_index, each_path, all_readers_by_field
            )
        )
        if not all_uncovered:
            continue
        all_simulated = [
            {VIOLATION_KEY_FIELD: each_field, VIOLATION_KEY_FILE: each_path}
            for each_field in all_uncovered
        ]
        all_contradictions.append({
            VIOLATION_KEY_FILE: each_path,
            VIOLATION_KEY_EARLIEST_READER_SLICE: each_target_index,
            VIOLATION_KEY_CURRENT_SLICE: all_slices_by_file.get(each_path),
            VIOLATION_KEY_UNCOVERED_FIELDS: all_uncovered,
            REPORT_KEY_COALESCE_SUGGESTION: _coalesce_suggestion(
                all_simulated, all_readers_by_field
            ),
        })
    return all_contradictions


def _base_symbols(
    all_base_sources_by_path: dict[str, str],
) -> tuple[set[str], set[str]]:
    """Return names and config fields the base branch already carries.

    A symbol already on the base branch is on disk from slice one, so it can
    never be a forward reference. A config field already there is not new, so
    the dead-field gate is not judging it in this stack. Without this
    subtraction, every modified file's unchanged definitions read as violations.

    Args:
        all_base_sources_by_path: Base-branch source text keyed by path, or None.

    Returns:
        The base's top-level names and its config field names.
    """
    if not all_base_sources_by_path:
        return set(), set()
    all_names: set[str] = set()
    all_fields: set[str] = set()
    for each_path, each_source in all_base_sources_by_path.items():
        if not is_python_path(each_path):
            continue
        all_names |= collect_top_level_definitions(each_source)
        all_fields |= collect_config_field_definitions(each_source)
    return all_names, all_fields


def _collect_all_violations(
    all_slices: list[JsonObject],
    all_sources_by_path: dict[str, str],
    all_base_sources_by_path: dict[str, str],
) -> tuple[list[JsonObject], list[JsonObject], list[JsonObject], list[str]]:
    """Run both constraint checks and derive the coalesce set.

    Args:
        all_slices: Plan slices in merge order.
        all_sources_by_path: Source-branch text keyed by path.
        all_base_sources_by_path: Base-branch text keyed by path.

    Returns:
        Forward references, unread config fields, contradictions, and the file
        set that must ship in one slice.
    """
    all_base_names, all_base_fields = _base_symbols(all_base_sources_by_path)
    all_definition_slices = {
        each_name: each_index
        for each_name, each_index in _definition_slice_by_symbol(
            all_slices, all_sources_by_path
        ).items()
        if each_name not in all_base_names
    }
    all_readers_by_field = _production_readers_by_field(all_slices, all_sources_by_path)
    all_forward_references = _collect_forward_references(
        all_slices, all_sources_by_path, all_definition_slices
    )
    all_unread_config_fields = [
        each
        for each in _collect_unread_config_fields(
            all_slices, all_sources_by_path, all_readers_by_field
        )
        if str(each[VIOLATION_KEY_FIELD]) not in all_base_fields
    ]
    all_slices_by_file = {
        str(each_path): int(each_slice[SLICE_KEY_INDEX])
        for each_slice in all_slices
        for each_path in (each_slice.get(SLICE_KEY_FILES) or [])
    }
    all_contradictions = _detect_contradictions(
        all_forward_references,
        all_sources_by_path,
        all_base_fields,
        all_readers_by_field,
        all_slices_by_file,
    )
    all_coalesce = _coalesce_suggestion(all_unread_config_fields, all_readers_by_field)
    if not all_coalesce and all_contradictions:
        all_coalesce = sorted({
            each_path
            for each in all_contradictions
            for each_path in each[REPORT_KEY_COALESCE_SUGGESTION]
        })
    return (
        all_forward_references,
        all_unread_config_fields,
        all_contradictions,
        all_coalesce,
    )


def _report_errors(
    all_forward_references: list[JsonObject],
    all_unread_config_fields: list[JsonObject],
    all_contradictions: list[JsonObject],
    all_coalesce: list[str],
    all_slugs_by_index: dict[int, str],
) -> list[str]:
    """Render every violation as one operator-readable line."""
    all_errors = [
        ERROR_FORWARD_REFERENCE % (
            each[VIOLATION_KEY_REFERENCING_SLICE],
            all_slugs_by_index.get(int(each[VIOLATION_KEY_REFERENCING_SLICE]), ""),
            each[VIOLATION_KEY_SYMBOL],
            each[VIOLATION_KEY_FILE],
            each[VIOLATION_KEY_DEFINING_SLICE],
            each[VIOLATION_KEY_REFERENCING_SLICE],
        )
        for each in all_forward_references
    ]
    all_errors.extend(
        ERROR_UNREAD_CONFIG_FIELD % (
            each[VIOLATION_KEY_SLICE],
            all_slugs_by_index.get(int(each[VIOLATION_KEY_SLICE]), ""),
            each[VIOLATION_KEY_FIELD],
        )
        for each in all_unread_config_fields
    )
    all_errors.extend(
        ERROR_CONTRADICTION % (
            each[VIOLATION_KEY_FILE],
            each[VIOLATION_KEY_EARLIEST_READER_SLICE],
            LIST_JOIN_SEPARATOR.join(each[VIOLATION_KEY_UNCOVERED_FIELDS]),
        )
        for each in all_contradictions
    )
    if all_coalesce:
        all_errors.append(ERROR_COALESCE_HINT % LIST_JOIN_SEPARATOR.join(all_coalesce))
    return all_errors


def verify_slice_dependencies(
    all_slices: list[JsonObject],
    all_sources_by_path: dict[str, str],
    all_base_sources_by_path: dict[str, str],
) -> JsonObject:
    """Check a plan's slice order against both dependency constraints.

    Args:
        all_slices: Plan slices in merge order, each with ``index`` and ``files``.
        all_sources_by_path: Source text of each changed file on the source branch.
        all_base_sources_by_path: Base-branch text for the same paths, empty when
            the base carries none of them. Symbols the base already defines are
            excluded, being present from slice one. Required rather than optional
            so a caller never silently skips the subtraction and drowns in
            false positives.

    Returns:
        Report with ``is_valid``, the violation lists, a coalesce suggestion,
        and human-readable ``errors``.
    """
    (
        all_forward_references,
        all_unread_config_fields,
        all_contradictions,
        all_coalesce,
    ) = _collect_all_violations(
        all_slices, all_sources_by_path, all_base_sources_by_path
    )
    all_slugs_by_index = {
        int(each[SLICE_KEY_INDEX]): str(each.get(SLICE_KEY_SLUG) or "")
        for each in all_slices
    }
    all_errors = _report_errors(
        all_forward_references,
        all_unread_config_fields,
        all_contradictions,
        all_coalesce,
        all_slugs_by_index,
    )
    return {
        REPORT_KEY_IS_VALID: not all_errors,
        REPORT_KEY_FORWARD_REFERENCES: all_forward_references,
        REPORT_KEY_UNREAD_CONFIG_FIELDS: all_unread_config_fields,
        REPORT_KEY_CONTRADICTIONS: all_contradictions,
        REPORT_KEY_COALESCE_SUGGESTION: all_coalesce,
        REPORT_KEY_ERRORS: all_errors,
    }


def read_source_files(
    repo_root: Path,
    source_branch: str,
    all_paths: list[str],
) -> dict[str, str]:
    """Read each path's contents from one branch.

    ::

        read_source_files(root, "main", ["a.py"])  # ok: {"a.py": "..."}

    Args:
        repo_root: Git repository root.
        source_branch: Branch to read from.
        all_paths: Repository-relative paths to read.

    Returns:
        Source text keyed by path, skipping paths the branch does not carry.
    """
    all_collected: dict[str, str] = {}
    for each_path in all_paths:
        outcome = subprocess.run(
            ["git", "show", f"{source_branch}:{each_path}"],
            cwd=str(repo_root),
            capture_output=True,
            check=False,
        )
        if outcome.returncode == 0:
            all_collected[each_path] = outcome.stdout.decode("utf-8", errors="replace")
    return all_collected


def main() -> int:
    """Verify a plan file's slice dependencies and print the JSON report.

    Returns:
        Process exit code (0 when every slice prefix is closed, else 1).
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", required=True, help="Path to the plan JSON")
    parser.add_argument("--repo-path", default=".", help="Path inside the repository")
    parser.add_argument("--source-branch", default=None, help="Override the plan branch")
    parser.add_argument("--base-branch", default=None, help="Override the plan base ref")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    arguments = parser.parse_args()

    plan = json.loads(Path(arguments.plan).read_text(encoding="utf-8"))
    all_slices = plan.get("proposed_slices") or []
    source_branch = arguments.source_branch or plan.get("source_branch")
    all_paths = [
        str(each_path)
        for each_slice in all_slices
        for each_path in (each_slice.get(SLICE_KEY_FILES) or [])
    ]
    repo_root = Path(arguments.repo_path).resolve()
    all_sources = read_source_files(repo_root, str(source_branch), all_paths)
    base_branch = arguments.base_branch or plan.get("base_ref")
    all_base_sources = (
        read_source_files(repo_root, str(base_branch), all_paths) if base_branch else {}
    )
    report = verify_slice_dependencies(all_slices, all_sources, all_base_sources)
    print(json.dumps(report, indent=JSON_INDENT_SPACES if arguments.pretty else None))
    return EXIT_CODE_SUCCESS if report[REPORT_KEY_IS_VALID] else EXIT_CODE_FAILURE


if __name__ == "__main__":
    sys.exit(main())
