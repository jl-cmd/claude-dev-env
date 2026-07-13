#!/usr/bin/env python3
"""PreToolUse hook: blocks a per-directory CLAUDE.md that names a file absent from its subtree.

A per-directory ``CLAUDE.md`` documents the files reachable from its own
directory in a markdown table whose first column names each file in backticks,
and shows run commands inside fenced code blocks that invoke those files. When a
first-column cell, or an interpreter invocation inside a fenced run command
(``python script.py``), names a bare filename that exists nowhere under the scan
root (the CLAUDE.md directory's parent, which covers the directory, its
subdirectories, and its siblings), the doc points a reader at a file that is not
there. This hook fires on Write, Edit, and MultiEdit targeting a file named
``CLAUDE.md`` and blocks the write when any such cell or run command names a file
absent from the scan root. A table block or a run-command fence whose own region
declares an explicit relative-path source (a ``../`` token, in the rows/fence or
the prose that introduces it) documents files outside the subtree, so that block's
rows or that fence's commands are left alone — the exemption is scoped to the
region, not the whole file.
"""

import sys
from pathlib import Path

try:
    _hooks_root_directory = str(Path(__file__).resolve().parent.parent)
    _blocking_directory = str(Path(__file__).resolve().parent)
    for each_bootstrap_directory in (_hooks_root_directory, _blocking_directory):
        if each_bootstrap_directory not in sys.path:
            sys.path.insert(0, each_bootstrap_directory)
    from claude_md_orphan_file_blocker_parts import (
        decision,
        references,
        scan_plan,
        subtree_scan,
    )
    from claude_md_orphan_file_blocker_parts.subtree_scan import (
        MAX_SUBTREE_FILES_SCANNED,  # noqa: F401
    )
    from inventory_intent_records import records

    from hooks_constants.pre_tool_use_stdin import (
        read_hook_input_dictionary_from_stdin,
    )
except ImportError as import_error:
    raise ImportError(
        "claude_md_orphan_file_blocker: cannot import its parts submodules; "
        "ensure the hooks directory is importable."
    ) from import_error


is_claude_md_file = references.is_claude_md_file
find_referenced_filenames = references.find_referenced_filenames
find_run_command_filenames = references.find_run_command_filenames
find_missing_filenames = subtree_scan.find_missing_filenames
build_orphan_scan_plan = scan_plan.build_orphan_scan_plan
collect_missing_filenames = scan_plan.collect_missing_filenames
deny_orphan_files = decision.deny_orphan_files


def _partition_by_file_intent(
    session_id: str, directory: str, all_missing_filenames: list[str]
) -> tuple[list[str], list[str]]:
    """Split missing filenames into those with a pending file intent and those without."""
    matched_filenames = [
        each_filename
        for each_filename in all_missing_filenames
        if records.has_fresh_file_intent(session_id, directory, each_filename)
    ]
    unmatched_filenames = [
        each_filename
        for each_filename in all_missing_filenames
        if each_filename not in matched_filenames
    ]
    return matched_filenames, unmatched_filenames


def _emit_orphan_decision(
    input_data: dict,
    tool_name: str,
    file_path: str,
    directory: str,
    all_missing_filenames: list[str],
) -> None:
    """Consume covered rows and deny any genuine orphan the change introduces."""
    session_id = str(input_data.get("session_id") or "")
    matched_filenames, unmatched_filenames = _partition_by_file_intent(
        session_id, directory, all_missing_filenames
    )
    if unmatched_filenames:
        for each_filename in unmatched_filenames:
            records.record_row_intent(session_id, directory, each_filename)
        deny_orphan_files(tool_name, file_path, directory, unmatched_filenames)
        return
    for each_filename in matched_filenames:
        records.consume_file_intent(session_id, directory, each_filename)


def main() -> None:
    """Read the PreToolUse payload from stdin and block an orphan-file CLAUDE.md."""
    input_data = read_hook_input_dictionary_from_stdin()
    if input_data is None:
        sys.exit(0)
    tool_name = input_data.get("tool_name", "")
    if not isinstance(tool_name, str):
        sys.exit(0)
    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        sys.exit(0)
    if tool_name not in ("Write", "Edit", "MultiEdit"):
        sys.exit(0)
    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not is_claude_md_file(file_path):
        sys.exit(0)
    claude_md_directory = Path(file_path).resolve().parent
    if not claude_md_directory.is_dir():
        sys.exit(0)
    scan_plan_result = build_orphan_scan_plan(tool_name, tool_input, file_path, claude_md_directory)
    if not scan_plan_result.candidate_contents:
        sys.exit(0)
    missing_filenames = collect_missing_filenames(scan_plan_result, claude_md_directory)
    if not missing_filenames:
        sys.exit(0)
    _emit_orphan_decision(
        input_data, tool_name, file_path, str(claude_md_directory), missing_filenames
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
