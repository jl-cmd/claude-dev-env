"""Validate the resolved file set and emit a diff-scoped violation report.

``run_gate`` reads each eligible code file, runs the enforcer's
``validate_content`` plus the wrapper plumb-through check, partitions the result
into blocking versus advisory by touched line, prints the report, and always
names how many files it inspected.
"""

import sys
from pathlib import Path

from pr_loop_shared_constants.code_rules_gate_constants import INSPECTED_COUNT_MESSAGE
from pr_loop_shared_constants.terminology_sweep_constants import (
    TERMINOLOGY_SWEEP_GATE_HEADER,
)

from code_rules_gate_parts.added_line_maps import _resolved_under_root
from code_rules_gate_parts.enforcer_loading import ValidateContentCallable
from code_rules_gate_parts.git_blob_readers import (
    read_prior_committed_content,
    read_staged_content,
    staged_blob_exists,
)
from code_rules_gate_parts.violation_scoping import split_violations_by_scope
from code_rules_gate_parts.wrapper_plumb_check import (
    check_wrapper_plumb_through,
    is_code_path,
)

PartitionedViolations = tuple[dict[Path, list[str]], dict[Path, list[str]], int]


def _path_is_eligible_for_validation(
    resolved_path: Path,
    repository_root: Path,
    should_read_staged_content: bool,
) -> bool:
    """Decide whether *resolved_path* should be validated by the gate.

    Args:
        resolved_path: A resolved candidate path under *repository_root*.
        repository_root: Repository root used to compute the relative path.
        should_read_staged_content: When True, require staged-index presence;
            when False, require working-tree presence.

    Returns:
        True when the path carries a code extension and exists in the source
        the gate will read; False otherwise.
    """
    if not is_code_path(resolved_path):
        return False
    if should_read_staged_content:
        resolved_root = repository_root.resolve()
        relative_posix = str(resolved_path.relative_to(resolved_root)).replace("\\", "/")
        return staged_blob_exists(resolved_root, relative_posix)
    return resolved_path.is_file()


def _eligible_resolved_paths(
    all_file_paths: list[Path],
    repository_root: Path,
    should_read_staged_content: bool,
) -> list[Path]:
    """Return the resolved code files under the repo the gate will validate."""
    resolved_root = repository_root.resolve()
    all_eligible: list[Path] = []
    for each_path in sorted(set(all_file_paths)):
        each_resolved = _resolved_under_root(each_path, resolved_root)
        if each_resolved is None:
            continue
        if _path_is_eligible_for_validation(
            each_resolved, repository_root, should_read_staged_content
        ):
            all_eligible.append(each_resolved)
    return all_eligible


def _file_content_for_validation(
    resolved_path: Path,
    resolved_root: Path,
    relative_posix: str,
    should_read_staged_content: bool,
) -> str | None:
    """Return the content the gate validates for one file, or None if unreadable."""
    if should_read_staged_content:
        return read_staged_content(resolved_root, relative_posix)
    try:
        return resolved_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _scoped_violations_for_file(
    validate_content: ValidateContentCallable,
    resolved_path: Path,
    repository_root: Path,
    all_added_lines_for_file: set[int] | None,
    should_read_staged_content: bool = False,
) -> tuple[list[str], list[str]] | None:
    """Validate one resolved file and partition its violations by diff scope."""
    resolved_root = repository_root.resolve()
    relative_posix = str(resolved_path.relative_to(resolved_root)).replace("\\", "/")
    content = _file_content_for_validation(
        resolved_path, resolved_root, relative_posix, should_read_staged_content
    )
    if content is None:
        sys.stderr.write(f"code_rules_gate: skip unreadable {resolved_path}\n")
        return None
    prior_content = read_prior_committed_content(resolved_root, relative_posix)
    issues = validate_content(
        content,
        relative_posix,
        prior_content,
        defer_scope_to_caller=True,
        sibling_directory=resolved_path.parent,
    )
    issues.extend(check_wrapper_plumb_through(content, relative_posix))
    if not issues:
        return [], []
    return split_violations_by_scope(issues, all_added_lines_for_file)


def _added_lines_for(
    all_added_lines_by_path: dict[Path, set[int]] | None, each_resolved: Path
) -> set[int] | None:
    """Return the added-line set for one path, or None for whole-file scope."""
    if all_added_lines_by_path is None:
        return None
    return all_added_lines_by_path.get(each_resolved)


def _partition_over_eligible_paths(
    validate_content: ValidateContentCallable,
    all_eligible_paths: list[Path],
    repository_root: Path,
    all_added_lines_by_path: dict[Path, set[int]] | None,
    should_read_staged_content: bool,
) -> PartitionedViolations:
    """Validate each already-resolved eligible file and partition the results."""
    blocking_by_file: dict[Path, list[str]] = {}
    advisory_by_file: dict[Path, list[str]] = {}
    skipped_unreadable_count = 0
    for each_resolved in all_eligible_paths:
        scoped_violations = _scoped_violations_for_file(
            validate_content,
            each_resolved,
            repository_root,
            _added_lines_for(all_added_lines_by_path, each_resolved),
            should_read_staged_content,
        )
        if scoped_violations is None:
            skipped_unreadable_count += 1
            continue
        blocking, advisory = scoped_violations
        if blocking:
            blocking_by_file[each_resolved] = blocking
        if advisory:
            advisory_by_file[each_resolved] = advisory
    return blocking_by_file, advisory_by_file, skipped_unreadable_count


def _collect_partitioned_violations(
    validate_content: ValidateContentCallable,
    all_file_paths: list[Path],
    repository_root: Path,
    all_added_lines_by_path: dict[Path, set[int]] | None,
    should_read_staged_content: bool = False,
) -> PartitionedViolations:
    """Validate every eligible file and partition results, counting read skips."""
    all_eligible_paths = _eligible_resolved_paths(
        all_file_paths, repository_root, should_read_staged_content
    )
    return _partition_over_eligible_paths(
        validate_content,
        all_eligible_paths,
        repository_root,
        all_added_lines_by_path,
        should_read_staged_content,
    )


def _blocking_header(blocking_count: int, is_whole_file_scope: bool) -> str:
    """Return the blocking-section header for the current scope."""
    if is_whole_file_scope:
        return f"code_rules_gate: {blocking_count} violation(s) reported."
    return f"code_rules_gate: {blocking_count} violation(s) introduced on changed lines:"


def print_violation_section(
    header_message: str,
    all_violations_by_file: dict[Path, list[str]],
    repository_root: Path,
) -> None:
    """Print a labeled block of violations grouped by relative path.

    Args:
        header_message: Section header to write to stderr.
        all_violations_by_file: Mapping from absolute file path to its violation
            strings.
        repository_root: Repository root used to compute relative paths.
    """
    sys.stderr.write(header_message + "\n")
    resolved_root = repository_root.resolve()
    for each_path in sorted(all_violations_by_file.keys()):
        relative = each_path.relative_to(resolved_root)
        sys.stderr.write(f"{relative}:\n")
        for each_issue in all_violations_by_file[each_path]:
            sys.stderr.write(f"  {each_issue}\n")


def _report_advisory_section(
    advisory_count: int,
    blocking_count: int,
    all_advisory_by_file: dict[Path, list[str]],
    repository_root: Path,
) -> None:
    """Print the advisory violation section when any advisory violation exists."""
    if not advisory_count:
        return
    if blocking_count:
        sys.stderr.write("\n")
    print_violation_section(
        (
            f"code_rules_gate: {advisory_count} pre-existing violation(s) "
            "in touched files (advisory, not blocking):"
        ),
        all_advisory_by_file,
        repository_root,
    )


def _report_partitioned_violations(
    partitions: PartitionedViolations,
    repository_root: Path,
    is_whole_file_scope: bool,
) -> int:
    """Print the blocking and advisory sections and return the gate exit code."""
    all_blocking_by_file, all_advisory_by_file, skipped_unreadable_count = partitions
    blocking_count = sum(len(each) for each in all_blocking_by_file.values())
    advisory_count = sum(len(each) for each in all_advisory_by_file.values())
    if blocking_count:
        print_violation_section(
            _blocking_header(blocking_count, is_whole_file_scope),
            all_blocking_by_file,
            repository_root,
        )
    _report_advisory_section(advisory_count, blocking_count, all_advisory_by_file, repository_root)
    if skipped_unreadable_count:
        sys.stderr.write(
            f"code_rules_gate: {skipped_unreadable_count} file(s) skipped due to "
            "read errors; gate cannot vouch for those files.\n"
        )
    if blocking_count or skipped_unreadable_count:
        return 1
    return 0


def _report_inspected_count(inspected_count: int) -> None:
    """Write the inspected-file count to standard error."""
    sys.stderr.write(INSPECTED_COUNT_MESSAGE.format(inspected_count=inspected_count) + "\n")


def _validate_and_count(
    validate_content: ValidateContentCallable,
    all_file_paths: list[Path],
    repository_root: Path,
    all_added_lines_by_path: dict[Path, set[int]] | None,
    should_read_staged_content: bool,
) -> PartitionedViolations:
    """Validate the eligible files, report the inspected count, return partitions."""
    all_eligible_paths = _eligible_resolved_paths(
        all_file_paths, repository_root, should_read_staged_content
    )
    blocking_by_file, advisory_by_file, skipped_count = _partition_over_eligible_paths(
        validate_content,
        all_eligible_paths,
        repository_root,
        all_added_lines_by_path,
        should_read_staged_content,
    )
    _report_inspected_count(len(all_eligible_paths) - skipped_count)
    return blocking_by_file, advisory_by_file, skipped_count


def run_gate(
    validate_content: ValidateContentCallable,
    all_file_paths: list[Path],
    repository_root: Path,
    all_added_lines_by_path: dict[Path, set[int]] | None = None,
    should_read_staged_content: bool = False,
) -> int:
    """Run the gate over *all_file_paths* and emit a partitioned report.

    Args:
        validate_content: The enforcer ``validate_content`` callable.
        all_file_paths: File paths to inspect.
        repository_root: Repository root for resolving relative paths.
        all_added_lines_by_path: Per-file added-line maps, or None.
        should_read_staged_content: When True, validate staged blobs.

    Returns:
        Zero when clean; non-zero on a blocking violation or a skipped file.
    """
    partitions = _validate_and_count(
        validate_content,
        all_file_paths,
        repository_root,
        all_added_lines_by_path,
        should_read_staged_content,
    )
    return _report_partitioned_violations(
        partitions, repository_root, all_added_lines_by_path is None
    )


def _report_terminology_findings(all_findings: list[str]) -> None:
    """Print the terminology-sweep findings, when any, to standard error.

    Args:
        all_findings: The near-miss findings from the staged terminology sweep.
    """
    if not all_findings:
        return
    sys.stderr.write(TERMINOLOGY_SWEEP_GATE_HEADER.format(finding_count=len(all_findings)) + "\n")
    for each_finding in all_findings:
        sys.stderr.write(f"  {each_finding}\n")
