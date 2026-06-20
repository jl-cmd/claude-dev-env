#!/usr/bin/env python3
"""PreToolUse hook: pre-flight gate for the code-verifier subagent spawn.

The hook fires only on an ``Agent`` tool call whose ``subagent_type`` is
``code-verifier``. Before that verification spawn runs, the hook checks the
branch for two committability problems against the resolved base ref: a real
merge conflict (a non-mutating trial-merge of HEAD against the base ref) and a
CODE_RULES violation on a line added in the uncommitted working tree. When
either fires, the hook denies the spawn with a reason addressed to the spawning
agent that names the conflicting files and the violating file:line, so that
agent fixes them and re-spawns. Both checks fail OPEN on any infrastructure
problem — a non-repo cwd, an absent base ref, a git or engine failure, or a
timeout — because the authoritative fail-closed CODE_RULES enforcement already
runs at Write time and at commit time. The hook never network-fetches and never
mutates the index or working tree.
"""

from __future__ import annotations

import contextlib
import io
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import TextIO

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

_blocking_dir = str(Path(__file__).resolve().parent)
if _blocking_dir not in sys.path:
    sys.path.insert(0, _blocking_dir)

from verification_verdict_store import (  # noqa: E402
    candidate_base_references,
    resolve_merge_base,
    resolve_repo_root,
    run_git,
    untracked_file_paths,
)

from hooks_constants.code_verifier_spawn_preflight_gate_constants import (  # noqa: E402
    ALL_MERGE_TREE_COMMAND_FLAGS,
    ALL_NAME_ONLY_WORKTREE_DIFF_FLAGS,
    ALL_UNIFIED_ZERO_DIFF_FLAGS,
    CODE_RULES_CHECK_TIMEOUT_SECONDS,
    CODE_RULES_SECTION_HEADER,
    CODE_VERIFIER_SUBAGENT_TYPE,
    DENY_REASON_LEAD,
    GATE_SCRIPTS_RELATIVE_PATH,
    MERGE_CONFLICT_SECTION_HEADER,
    MERGE_TREE_CLEAN_EXIT_CODE,
    MERGE_TREE_CONFLICT_EXIT_CODE,
    MERGE_TREE_TIMEOUT_SECONDS,
)
from hooks_constants.pr_converge_bugteam_enforcer_constants import (  # noqa: E402
    AGENT_TOOL_NAME,
)

_scripts_dir = str(Path(__file__).resolve().parents[2] / GATE_SCRIPTS_RELATIVE_PATH)
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)

from code_rules_gate import (  # noqa: E402
    ValidateContentCallable,
    is_code_path,
    load_validate_content,
    parse_added_line_numbers,
    run_gate,
    whole_file_line_set,
)


def _should_run(payload_by_field: dict[str, object]) -> bool:
    """Return True only for a code-verifier Agent spawn.

    Args:
        payload_by_field: The full PreToolUse hook payload (already
            JSON-parsed), keyed by top-level field name.

    Returns:
        True when the tool is Agent and ``tool_input.subagent_type`` is
        ``code-verifier``; False for every other shape.
    """
    if payload_by_field.get("tool_name", "") != AGENT_TOOL_NAME:
        return False
    tool_input = payload_by_field.get("tool_input", {})
    if not isinstance(tool_input, dict):
        return False
    return tool_input.get("subagent_type", "") == CODE_VERIFIER_SUBAGENT_TYPE


def _resolve_repo_root_and_base(working_directory: str | None) -> tuple[str, str, str] | None:
    """Resolve the repo root, merge-base sha, and chosen base ref.

    Args:
        working_directory: The spawn's working directory from the payload, or
            None when the payload carries no ``cwd``.

    Returns:
        A ``(repo_root, merge_base_sha, base_ref)`` triple, or None when the
        directory is not a work tree or no base ref resolves on disk — the
        caller fails OPEN on None.
    """
    start_directory = working_directory if working_directory else str(Path.cwd())
    repo_root = resolve_repo_root(start_directory)
    if repo_root is None:
        return None
    merge_base_sha = resolve_merge_base(repo_root)
    if merge_base_sha is None:
        return None
    for each_reference in candidate_base_references(repo_root):
        if run_git(repo_root, "merge-base", "HEAD", each_reference) is not None:
            return repo_root, merge_base_sha, each_reference
    return None


def _run_trial_merge(repo_root: str, base_ref: str) -> tuple[int, str] | None:
    """Run the non-mutating trial-merge and return its exit code and stdout.

    Args:
        repo_root: The repository top-level directory.
        base_ref: The base ref to trial-merge HEAD against.

    Returns:
        A ``(returncode, stdout)`` pair, or None when the command is missing,
        times out, or raises an OS-level error — the caller fails OPEN on None.
    """
    try:
        completed_process = subprocess.run(
            ["git", "-C", repo_root, *ALL_MERGE_TREE_COMMAND_FLAGS, base_ref, "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=MERGE_TREE_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return completed_process.returncode, completed_process.stdout


def _conflicting_files(repo_root: str, base_ref: str) -> list[str] | None:
    """Return the files that conflict when HEAD trial-merges against the base.

    Args:
        repo_root: The repository top-level directory.
        base_ref: The base ref to trial-merge HEAD against.

    Returns:
        The conflicting file paths on a conflict exit, an empty list on a
        clean merge, or None on any infrastructure failure (command missing,
        timeout, or an exit code that is neither clean nor conflict) — the
        caller fails OPEN on None.
    """
    merge_outcome = _run_trial_merge(repo_root, base_ref)
    if merge_outcome is None:
        return None
    return_code, merge_stdout = merge_outcome
    if return_code == MERGE_TREE_CLEAN_EXIT_CODE:
        return []
    if return_code != MERGE_TREE_CONFLICT_EXIT_CODE:
        return None
    return _parse_conflicting_paths(merge_stdout)


def _parse_conflicting_paths(merge_stdout: str) -> list[str]:
    """Extract conflicting paths from trial-merge stdout.

    Args:
        merge_stdout: The stdout of a conflict-exit trial-merge: the written
            tree-OID line, then one conflicting path per line, then a blank
            line and informational text.

    Returns:
        The conflicting file paths — the lines after the tree-OID up to the
        first blank line.
    """
    all_lines = merge_stdout.splitlines()
    conflicting_paths: list[str] = []
    for each_line in all_lines[1:]:
        if not each_line.strip():
            break
        conflicting_paths.append(each_line)
    return conflicting_paths


def _working_tree_added_lines_by_path(
    repo_root: str, merge_base_sha: str
) -> tuple[list[Path], dict[Path, set[int]]] | None:
    """Build the code-file surface and its working-tree-vs-merge-base added lines.

    Args:
        repo_root: The repository top-level directory.
        merge_base_sha: The merge-base sha the surface diffs against.

    Returns:
        A ``(file_paths, added_lines_by_path)`` pair keyed by resolved
        absolute path, or None when a surface git query fails — the caller
        fails OPEN on None.
    """
    tracked_changed_text = run_git(repo_root, *ALL_NAME_ONLY_WORKTREE_DIFF_FLAGS, merge_base_sha)
    if tracked_changed_text is None:
        return None
    untracked_paths = untracked_file_paths(repo_root)
    if untracked_paths is None:
        return None
    repo_root_path = Path(repo_root)
    file_paths: list[Path] = []
    added_lines_by_path: dict[Path, set[int]] = {}
    for each_relative in tracked_changed_text.splitlines():
        if not each_relative or not is_code_path(Path(each_relative)):
            continue
        resolved_path = (repo_root_path / each_relative).resolve()
        file_paths.append(resolved_path)
        added_lines_by_path[resolved_path] = _tracked_file_added_lines(
            repo_root, merge_base_sha, each_relative
        )
    for each_relative in untracked_paths:
        if not is_code_path(Path(each_relative)):
            continue
        resolved_path = (repo_root_path / each_relative).resolve()
        file_paths.append(resolved_path)
        added_lines_by_path[resolved_path] = whole_file_line_set(resolved_path)
    return file_paths, added_lines_by_path


def _tracked_file_added_lines(repo_root: str, merge_base_sha: str, relative_path: str) -> set[int]:
    """Return the working-tree-added line numbers for one tracked file.

    Args:
        repo_root: The repository top-level directory.
        merge_base_sha: The merge-base sha the diff runs against.
        relative_path: The repo-relative path of the tracked changed file.

    Returns:
        The 1-indexed line numbers added vs the merge base in the working
        tree, or an empty set when the per-file diff fails.
    """
    unified_diff_text = run_git(
        repo_root, *ALL_UNIFIED_ZERO_DIFF_FLAGS, merge_base_sha, "--", relative_path
    )
    if unified_diff_text is None:
        return set()
    return parse_added_line_numbers(unified_diff_text)


def _code_rules_report(
    repo_root: str, all_file_paths: list[Path], all_added_lines_by_path: dict[Path, set[int]]
) -> str | None:
    """Run the CODE_RULES engine and return its blocking report, or None.

    Args:
        repo_root: The repository top-level directory.
        all_file_paths: The resolved code-file paths to inspect.
        all_added_lines_by_path: Per-file working-tree-added line numbers keyed
            by resolved absolute path.

    Returns:
        The engine's grouped file:line report when a blocking violation lands
        on an added line, or None when the surface is clean, the engine fails
        to load, the check times out, or any engine error arises — every
        non-block outcome fails OPEN.
    """
    if not all_file_paths:
        return None
    try:
        validate_content = load_validate_content()
    except SystemExit:
        return None
    captured_stderr = io.StringIO()
    try:
        with ThreadPoolExecutor(max_workers=1) as engine_executor:
            engine_future = engine_executor.submit(
                _run_gate_capturing_stderr,
                validate_content,
                all_file_paths,
                Path(repo_root),
                all_added_lines_by_path,
                captured_stderr,
            )
            exit_code = engine_future.result(timeout=CODE_RULES_CHECK_TIMEOUT_SECONDS)
    except FutureTimeoutError:
        return None
    except OSError:
        return None
    if exit_code == 0:
        return None
    return captured_stderr.getvalue()


def _run_gate_capturing_stderr(
    validate_content: ValidateContentCallable,
    all_file_paths: list[Path],
    repository_root: Path,
    all_added_lines_by_path: dict[Path, set[int]],
    captured_stderr: io.StringIO,
) -> int:
    """Run the gate with its stderr report captured into a buffer.

    Args:
        validate_content: The enforcer ``validate_content`` callable.
        all_file_paths: The resolved code-file paths to inspect.
        repository_root: The repository root path the gate resolves against.
        all_added_lines_by_path: Per-file working-tree-added line numbers keyed
            by resolved absolute path.
        captured_stderr: The buffer the gate's grouped report is written into.

    Returns:
        The gate exit code: 0 when clean, non-zero on a blocking violation or
        an unreadable file.
    """
    with contextlib.redirect_stderr(captured_stderr):
        return run_gate(
            validate_content,
            all_file_paths,
            repository_root,
            all_added_lines_by_path=all_added_lines_by_path,
            read_staged_content_flag=False,
        )


def _build_deny_reason(
    all_conflicting_files: list[str] | None, base_ref: str, code_rules_report: str | None
) -> str | None:
    """Assemble the spawner-addressed deny reason from the two check results.

    Args:
        all_conflicting_files: The conflicting file paths from the conflict
            check, an empty list when clean, or None when that check failed open.
        base_ref: The base ref named in the conflict section header.
        code_rules_report: The grouped report from the CODE_RULES check, or None
            when that check found nothing or failed open.

    Returns:
        The full deny reason when either check fired, or None when neither
        produced an issue.
    """
    reason_sections: list[str] = []
    if all_conflicting_files:
        conflict_lines = "\n".join(f"  {each_path}" for each_path in all_conflicting_files)
        conflict_header = MERGE_CONFLICT_SECTION_HEADER.format(base_ref=base_ref)
        reason_sections.append(f"{conflict_header}\n{conflict_lines}")
    if code_rules_report:
        reason_sections.append(f"{CODE_RULES_SECTION_HEADER}\n{code_rules_report.strip()}")
    if not reason_sections:
        return None
    return DENY_REASON_LEAD + "\n\n" + "\n\n".join(reason_sections)


def _emit_deny_payload(output_stream: TextIO, reason: str) -> None:
    """Write the PreToolUse deny payload to the provided stream.

    Args:
        output_stream: Writable text stream — production code passes
            ``sys.stdout``; tests pass a ``StringIO`` to capture the JSON.
        reason: The ``permissionDecisionReason`` text for the deny payload.
    """
    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    output_stream.write(json.dumps(deny_payload) + "\n")
    output_stream.flush()


def _preflight_deny_reason(payload_by_field: dict[str, object]) -> str | None:
    """Run both pre-flight checks and return a deny reason, or None to allow.

    Args:
        payload_by_field: The full PreToolUse hook payload, keyed by top-level
            field name.

    Returns:
        The deny reason when a check fired, or None when both checks pass or
        fail open.
    """
    working_directory = payload_by_field.get("cwd")
    resolution = _resolve_repo_root_and_base(
        working_directory if isinstance(working_directory, str) else None
    )
    if resolution is None:
        return None
    repo_root, merge_base_sha, base_ref = resolution
    conflicting_files = _conflicting_files(repo_root, base_ref)
    surface = _working_tree_added_lines_by_path(repo_root, merge_base_sha)
    code_rules_report = None
    if surface is not None:
        file_paths, added_lines_by_path = surface
        code_rules_report = _code_rules_report(repo_root, file_paths, added_lines_by_path)
    return _build_deny_reason(conflicting_files, base_ref, code_rules_report)


def main() -> None:
    try:
        hook_payload = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)
    if not isinstance(hook_payload, dict):
        sys.exit(0)
    if not _should_run(hook_payload):
        sys.exit(0)
    deny_reason = _preflight_deny_reason(hook_payload)
    if deny_reason is not None:
        _emit_deny_payload(sys.stdout, deny_reason)
    sys.exit(0)


if __name__ == "__main__":
    main()
