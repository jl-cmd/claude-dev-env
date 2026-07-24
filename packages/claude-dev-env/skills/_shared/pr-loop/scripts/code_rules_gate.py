"""Run the code-rules validators over a resolved git file set.

::

    default mode: git diff since merge-base, joined with untracked files
    --staged:     validate the staged index; --paths: validate explicit files
    every mode ends by naming how many files it inspected

This entry module wires the ``code_rules_gate_parts`` submodules into one CLI
and re-exports their surface for the test suite.
"""

import argparse
import sys
from pathlib import Path


def _ensure_scripts_directory_on_path() -> None:
    """Add this file's directory to sys.path so the parts package resolves."""
    scripts_directory = str(Path(__file__).resolve().parent)
    if scripts_directory not in sys.path:
        sys.path.insert(0, scripts_directory)


_ensure_scripts_directory_on_path()

try:
    from code_rules_gate_parts import (
        added_line_maps,
        enforcer_loading,
        gate_arguments,
        gate_running,
        git_blob_readers,
        git_file_sets,
        staged_test_running,
        violation_scoping,
        wrapper_plumb_check,
    )
    from pr_loop_shared_constants.code_rules_gate_constants import (
        ALL_POSIX_VENV_PYTHON_RELATIVE_PATH_SEGMENTS,
        ALL_PYTEST_MODULE_INVOCATION,
        ALL_STAGED_PYTEST_LIVE_SUITE_EXCLUSION_ARGUMENTS,
        ALL_WINDOWS_VENV_PYTHON_RELATIVE_PATH_SEGMENTS,
        EMPTY_FILE_SET_EXIT_CODE,
        EMPTY_FILE_SET_MESSAGE,
        INSPECTED_COUNT_MESSAGE,
        MAXIMUM_STAGED_PYTEST_COMMAND_LINE_CHARACTERS,
        MINIMUM_STAGED_PYTEST_PYTHON_MAJOR,
        MINIMUM_STAGED_PYTEST_PYTHON_MINOR,
    )
    from pr_loop_shared_constants.preflight_constants import (
        PYTEST_NO_TESTS_COLLECTED_EXIT_CODE,
    )
    from terminology_sweep import repository_environment, staged_terminology_findings
except ImportError as import_error:
    raise ImportError(
        "code_rules_gate: could not import its code_rules_gate_parts submodules; "
        "ensure the pr-loop scripts directory is importable."
    ) from import_error

subprocess = git_file_sets.subprocess

resolve_claude_dev_env_root = enforcer_loading.resolve_claude_dev_env_root
load_validate_content = enforcer_loading.load_validate_content
ValidateContentCallable = enforcer_loading.ValidateContentCallable

resolve_merge_base = git_file_sets.resolve_merge_base
paths_from_git_staged = git_file_sets.paths_from_git_staged
paths_from_git_diff = git_file_sets.paths_from_git_diff
paths_from_git_untracked = git_file_sets.paths_from_git_untracked
filter_paths_under_prefixes = git_file_sets.filter_paths_under_prefixes
is_staged_file_newly_added = git_file_sets.is_staged_file_newly_added
staged_file_line_count = git_file_sets.staged_file_line_count
staged_unified_diff_text = git_file_sets.staged_unified_diff_text

read_prior_committed_content = git_blob_readers.read_prior_committed_content
read_staged_content = git_blob_readers.read_staged_content
staged_blob_exists = git_blob_readers.staged_blob_exists

parse_added_line_numbers = violation_scoping.parse_added_line_numbers
hunk_header_pattern = violation_scoping.hunk_header_pattern
violation_line_pattern = violation_scoping.violation_line_pattern
extract_violation_line_number = violation_scoping.extract_violation_line_number
function_length_span_range = violation_scoping.function_length_span_range
isolation_span_range = violation_scoping.isolation_span_range
banned_noun_span_range = violation_scoping.banned_noun_span_range
duplicate_body_span_range = violation_scoping.duplicate_body_span_range
inline_duplicate_body_span_lines = violation_scoping.inline_duplicate_body_span_lines
enclosing_span_range = violation_scoping.enclosing_span_range
split_violations_by_scope = violation_scoping.split_violations_by_scope

added_lines_for_file = added_line_maps.added_lines_for_file
added_lines_for_renamed_file = added_line_maps.added_lines_for_renamed_file
renamed_file_source_map_since = added_line_maps.renamed_file_source_map_since
added_lines_by_file = added_line_maps.added_lines_by_file
is_file_new_at_base = added_line_maps.is_file_new_at_base
whole_file_line_set = added_line_maps.whole_file_line_set

check_wrapper_plumb_through = wrapper_plumb_check.check_wrapper_plumb_through
is_code_path = wrapper_plumb_check.is_code_path
is_test_path = wrapper_plumb_check.is_test_path

run_gate = gate_running.run_gate
print_violation_section = gate_running.print_violation_section
_collect_partitioned_violations = gate_running._collect_partitioned_violations
_scoped_violations_for_file = gate_running._scoped_violations_for_file
_report_terminology_findings = gate_running._report_terminology_findings


def _report_partitioned_violations(
    blocking_by_file: dict[Path, list[str]],
    advisory_by_file: dict[Path, list[str]],
    repository_root: Path,
    is_whole_file_scope: bool,
    skipped_unreadable_count: int,
) -> int:
    """Print the violation sections and return the gate exit code.

    Importers outside this directory (the code-verifier spawn-preflight hook)
    call this surface with the partition spread across positional arguments,
    so this wrapper keeps that calling shape and folds the pieces into the
    ``PartitionedViolations`` tuple the gate-running module consumes.

    Args:
        blocking_by_file: Blocking violations grouped by resolved file path.
        advisory_by_file: Advisory violations grouped by resolved file path.
        repository_root: Repository root for computing relative paths.
        is_whole_file_scope: True when findings cover whole files, not a diff.
        skipped_unreadable_count: Count of files skipped due to read errors.

    Returns:
        The gate exit code: 1 when anything blocks, 0 otherwise.
    """
    return gate_running._report_partitioned_violations(
        (blocking_by_file, advisory_by_file, skipped_unreadable_count),
        repository_root,
        is_whole_file_scope,
    )

run_staged_test_files = staged_test_running.run_staged_test_files
_staged_test_file_paths = staged_test_running._staged_test_file_paths
_resolve_owning_test_root = staged_test_running._resolve_owning_test_root
_group_staged_tests_by_root = staged_test_running._group_staged_tests_by_root
_batched_pytest_arguments = staged_test_running._batched_pytest_arguments
_resolve_gate_python_executable = staged_test_running._resolve_gate_python_executable
_staged_pytest_environment = staged_test_running._staged_pytest_environment
_relative_pytest_argument = staged_test_running._relative_pytest_argument
_run_pytest_for_group = staged_test_running._run_pytest_for_group

parse_arguments = gate_arguments.parse_arguments

__all__ = [
    "ALL_POSIX_VENV_PYTHON_RELATIVE_PATH_SEGMENTS",
    "ALL_PYTEST_MODULE_INVOCATION",
    "ALL_STAGED_PYTEST_LIVE_SUITE_EXCLUSION_ARGUMENTS",
    "ALL_WINDOWS_VENV_PYTHON_RELATIVE_PATH_SEGMENTS",
    "MAXIMUM_STAGED_PYTEST_COMMAND_LINE_CHARACTERS",
    "MINIMUM_STAGED_PYTEST_PYTHON_MAJOR",
    "MINIMUM_STAGED_PYTEST_PYTHON_MINOR",
    "PYTEST_NO_TESTS_COLLECTED_EXIT_CODE",
    "repository_environment",
    "subprocess",
]


def added_lines_for_staged_file(
    repository_root: Path,
    relative_path_posix: str,
    all_rename_sources: dict[str, str] | None = None,
) -> set[int]:
    """Return added line numbers within the staged diff for one file.

    When *relative_path_posix* is a staged rename destination, compare the HEAD
    source blob to the staged destination blob so a pure move adds no lines.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        relative_path_posix: Repository-relative POSIX path to inspect.
        all_rename_sources: Optional staged rename destination-to-source map.

    Returns:
        Line numbers added in the staged diff, or the whole staged blob when
        the file is newly added and not a rename destination.
    """
    rename_sources = all_rename_sources if all_rename_sources is not None else {}
    if relative_path_posix in rename_sources:
        return added_line_maps.added_lines_for_staged_renamed_file(
            repository_root,
            rename_sources[relative_path_posix],
            relative_path_posix,
        )
    diff_text = staged_unified_diff_text(repository_root, relative_path_posix)
    if diff_text.strip():
        return parse_added_line_numbers(diff_text)
    if is_staged_file_newly_added(repository_root, relative_path_posix):
        total_lines = staged_file_line_count(repository_root, relative_path_posix)
        if total_lines > 0:
            return set(range(1, total_lines + 1))
    return set()


def _resolved_staged_rename_sources(
    resolved_root: Path, all_rename_sources: dict[str, str] | None
) -> dict[str, str]:
    """Return the given staged rename map, or compute it tree-wide when absent."""
    if all_rename_sources is not None:
        return all_rename_sources
    return added_line_maps.renamed_file_source_map_staged(resolved_root)


def added_lines_by_file_staged(
    repository_root: Path,
    all_file_paths: list[Path],
    all_rename_sources: dict[str, str] | None = None,
) -> dict[Path, set[int]]:
    """Build a per-file map of staged-added line numbers.

    Honors staged renames detected tree-wide (``git diff --cached -M``) so a
    pure move does not treat every destination line as newly introduced.

    Args:
        repository_root: Repository root for diff invocations.
        all_file_paths: File paths whose staged-added lines are collected.
        all_rename_sources: Optional staged rename destination-to-source map.

    Returns:
        Mapping from resolved file path to its staged-added line numbers.
    """
    resolved_root = repository_root.resolve()
    rename_sources = _resolved_staged_rename_sources(resolved_root, all_rename_sources)
    added_by_path: dict[Path, set[int]] = {}
    for each_path in all_file_paths:
        resolved = added_line_maps._resolved_under_root(each_path, resolved_root)
        if resolved is None:
            continue
        relative_posix = str(resolved.relative_to(resolved_root)).replace("\\", "/")
        added_by_path[resolved] = added_lines_for_staged_file(
            resolved_root, relative_posix, rename_sources
        )
    return added_by_path


def _staged_pytest_exit_code_for_current_python(repository_root: Path) -> int:
    """Run the staged test files, or skip them on a Python below the minimum.

    Args:
        repository_root: The repository root whose staged test files run.

    Returns:
        0 when the running Python is below the staged-test minimum, otherwise the
        exit code from running the staged test files.
    """
    running_version = (sys.version_info.major, sys.version_info.minor)
    minimum_version = (
        MINIMUM_STAGED_PYTEST_PYTHON_MAJOR,
        MINIMUM_STAGED_PYTEST_PYTHON_MINOR,
    )
    if running_version < minimum_version:
        sys.stderr.write(
            f"code_rules_gate: Python {running_version} is below the staged-test "
            f"minimum {minimum_version}; skipping the staged pytest step.\n"
        )
        return 0
    return run_staged_test_files(repository_root)


def _deduplicate_paths(all_paths: list[Path]) -> list[Path]:
    """Return *all_paths* with duplicates removed, preserving first-seen order."""
    return list(dict.fromkeys(all_paths))


def _report_empty_file_set() -> int:
    """Report an empty resolved file set loudly and exit non-zero.

    Zero candidate files means the gate inspected nothing, and a bad merge
    base or a wrong directory produces exactly this state. A quiet pass here
    would be trusted like a real pass (issue #62), so the run refuses with
    its own exit code, distinct from the violation and error codes. A set
    emptied only by the ``--only-under`` scope never reaches this reporter.
    """
    sys.stderr.write(EMPTY_FILE_SET_MESSAGE + "\n")
    sys.stderr.write(INSPECTED_COUNT_MESSAGE.format(inspected_count=0) + "\n")
    return EMPTY_FILE_SET_EXIT_CODE


def _run_explicit_paths_mode(
    validate_content: enforcer_loading.ValidateContentCallable,
    arguments: argparse.Namespace,
    repository_root: Path,
) -> int:
    """Validate the explicit paths named on the command line."""
    all_explicit_paths = [repository_root / each_path for each_path in arguments.paths]
    return run_gate(
        validate_content,
        all_explicit_paths,
        repository_root,
        all_added_lines_by_path=None,
    )


def _run_staged_mode(
    validate_content: enforcer_loading.ValidateContentCallable,
    arguments: argparse.Namespace,
    repository_root: Path,
) -> int:
    """Validate the staged changes, run staged tests, and sweep terminology."""
    _report_terminology_findings(staged_terminology_findings(repository_root))
    staged_test_exit_code = _staged_pytest_exit_code_for_current_python(repository_root)
    staged_file_paths = filter_paths_under_prefixes(
        paths_from_git_staged(repository_root), repository_root, arguments.only_under
    )
    if not staged_file_paths:
        sys.stderr.write(INSPECTED_COUNT_MESSAGE.format(inspected_count=0) + "\n")
        return staged_test_exit_code
    all_staged_rename_sources = added_line_maps.renamed_file_source_map_staged(
        repository_root.resolve()
    )
    staged_added_lines = added_lines_by_file_staged(
        repository_root, staged_file_paths, all_staged_rename_sources
    )
    gate_exit_code = run_gate(
        validate_content,
        staged_file_paths,
        repository_root,
        all_added_lines_by_path=staged_added_lines,
        should_read_staged_content=True,
    )
    return gate_exit_code or staged_test_exit_code


def _run_diff_mode(
    validate_content: enforcer_loading.ValidateContentCallable,
    arguments: argparse.Namespace,
    repository_root: Path,
) -> int:
    """Validate the merge-base diff joined with the untracked files.

    Zero candidates means nothing was inspected (bad wiring looks the same),
    so that run refuses loudly. A set emptied only by the ``--only-under``
    scope flows through ``run_gate`` over zero files and exits clean.
    """
    all_candidate_paths = _deduplicate_paths(
        paths_from_git_diff(repository_root, arguments.base)
        + paths_from_git_untracked(repository_root)
    )
    if not all_candidate_paths:
        return _report_empty_file_set()
    file_paths = filter_paths_under_prefixes(
        all_candidate_paths, repository_root, arguments.only_under
    )
    scoped_added_lines = (
        added_lines_by_file(repository_root, arguments.base, file_paths) if file_paths else {}
    )
    return run_gate(
        validate_content,
        file_paths,
        repository_root,
        all_added_lines_by_path=scoped_added_lines,
    )


def main(all_arguments: list[str]) -> int:
    """Run the gate using the parsed CLI arguments.

    Args:
        all_arguments: Command-line argument list forwarded to argparse.

    Returns:
        The gate exit code for the selected mode.
    """
    arguments = parse_arguments(all_arguments)
    repository_root = (
        arguments.repo_root.resolve() if arguments.repo_root is not None else Path.cwd().resolve()
    )
    validate_content = load_validate_content()
    if arguments.paths:
        return _run_explicit_paths_mode(validate_content, arguments, repository_root)
    if arguments.staged:
        return _run_staged_mode(validate_content, arguments, repository_root)
    return _run_diff_mode(validate_content, arguments, repository_root)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
