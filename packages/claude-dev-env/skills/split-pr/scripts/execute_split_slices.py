"""Materialize an entire split plan as ordered local commits.

::

    all_commit_records = materialize_plan_locally(repo, plan)
    # one commit per slice in dependency topological order
"""

from __future__ import annotations

from pathlib import Path

from config.dependency_constants import GRAPH_KEY_ORDER
from config.git_operations_constants import RECORD_KEY_COMMIT_SHA
from config.plan_constants import (
    PLAN_KEY_ALL_SLICES,
    PLAN_KEY_SOURCE_COMMIT,
    SLICE_KEY_ALL_PATHS,
    SLICE_KEY_ID,
    SLICE_KEY_TITLE,
)
from split_pr_dependency_graph import build_dependency_graph
from split_pr_git_operations import materialize_slice_commit, restore_repository_state
from split_pr_process_runner import ProcessRunner, run_process
from split_pr_script_types import JsonObject, validate_split_plan
from verify_plan import verify_split_plan_coverage


def materialize_plan_locally(
    repository_path: Path,
    all_plan: JsonObject,
    run: ProcessRunner = run_process,
) -> list[JsonObject]:
    """Validate the plan, then commit each slice in topological layer order.

    Args:
        repository_path: Git repository root.
        all_plan: Split-plan document (schema v1).
        run: Process runner for git invocations.

    Returns:
        List of per-slice materialization records in commit order.

    Raises:
        ValueError: When the plan fails coverage or graph validation.
        RuntimeError: When any git step fails; repository is restored to
            the plan source_commit on failure.
    """
    verify_split_plan_coverage(all_plan)
    validate_split_plan(all_plan)
    source_commit = str(all_plan[PLAN_KEY_SOURCE_COMMIT])
    all_slices = all_plan[PLAN_KEY_ALL_SLICES]
    assert isinstance(all_slices, list)
    graph = build_dependency_graph(all_slices)
    order = graph[GRAPH_KEY_ORDER]
    assert isinstance(order, list)
    slice_by_id = {
        str(each[SLICE_KEY_ID]): each
        for each in all_slices
        if isinstance(each, dict)
    }
    all_commit_records: list[JsonObject] = []
    current_base = source_commit
    try:
        for each_slice_id in order:
            each_slice = slice_by_id[str(each_slice_id)]
            all_paths = each_slice[SLICE_KEY_ALL_PATHS]
            assert isinstance(all_paths, list)
            title = str(each_slice[SLICE_KEY_TITLE])
            commit_record = materialize_slice_commit(
                repository_path=repository_path,
                all_slice_paths=[str(each) for each in all_paths],
                commit_message=title,
                expected_base_sha=current_base,
                run=run,
            )
            all_commit_records.append(commit_record)
            current_base = str(commit_record[RECORD_KEY_COMMIT_SHA])
    except RuntimeError:
        restore_repository_state(repository_path, source_commit, run)
        raise
    return all_commit_records
