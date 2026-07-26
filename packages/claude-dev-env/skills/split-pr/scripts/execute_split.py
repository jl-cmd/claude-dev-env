#!/usr/bin/env python3
"""Execute an approved split plan: branches, file checkout, commits, optional PRs.

::

    python execute_split.py --plan plan.json --dry-run
    {"dry_run": true, "created_slices": [...]}

Never rewrites the original source branch. Requires a clean working tree when
not in dry-run mode. Uses ``git checkout <source> -- <files>`` per slice.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from split_pr_draft_pr import create_draft_pr
from split_pr_git_operations import (
    branch_exists,
    is_working_tree_dirty,
    read_starting_state,
    remote_exists,
    remote_ref_exists,
    restore_starting_state,
)
from split_pr_process_runner import run_checked_git, run_git
from split_pr_script_types import JsonObject
from split_pr_scripts_constants.config.common_constants import (
    ALL_EMPTY_ERROR_CONTEXT,
    EXIT_CODE_FAILURE,
    EXIT_CODE_SUCCESS,
    JSON_INDENT_SPACES,
    PAYLOAD_KEY_ERROR,
)
from split_pr_scripts_constants.config.execute_constants import (
    ARGUMENT_ALLOW_OPTIONAL_SPLIT,
    ARGUMENT_CREATE_PRS,
    ARGUMENT_DRY_RUN,
    ARGUMENT_PLAN,
    ARGUMENT_PRETTY,
    ARGUMENT_PUSH,
    ARGUMENT_REPO_PATH,
    ARGUMENT_STORE_TRUE_ACTION,
    ARGUMENT_SUPERSEDE_SOURCE,
    DEFAULT_COMMIT_MESSAGE_TEMPLATE,
    DEFAULT_REPO_PATH,
    ERROR_BRANCH_EXISTS,
    ERROR_CHECKOUT_FILES,
    ERROR_COMMIT_FAILED,
    ERROR_DIRTY_TREE,
    ERROR_EXECUTE_FAILED,
    ERROR_NO_ORIGIN_REMOTE,
    ERROR_PLAN_MISSING_PR_IDENTITY,
    ERROR_PUSH_FAILED,
    ERROR_RESTORE_FAILED,
    ERROR_SOURCE_HEAD_MOVED,
    ERROR_SOURCE_HEAD_UNREADABLE,
    ERROR_SPLIT_OPTIONAL_REFUSED,
    FRESH_BRANCH_SCRIPTS_DIRECTORY,
    GIT_ADD,
    GIT_ADD_PATHSPEC,
    GIT_BRANCH,
    GIT_CHECKOUT,
    GIT_CHECKOUT_FORCE_CREATE,
    GIT_COMMIT,
    GIT_DELETE_BRANCH_FLAG,
    GIT_FETCH,
    GIT_FORCE_FLAG,
    GIT_MESSAGE_FLAG,
    GIT_ORIGIN,
    GIT_ORIGIN_PREFIX,
    GIT_PUSH,
    GIT_QUIET_FLAG,
    GIT_REMOVE,
    GIT_REV_PARSE,
    GIT_SET_UPSTREAM,
    HELP_ALLOW_OPTIONAL_SPLIT,
    HELP_CREATE_PRS,
    HELP_DRY_RUN,
    HELP_PLAN,
    HELP_PRETTY,
    HELP_PUSH,
    HELP_REPO_PATH,
    HELP_SUPERSEDE_SOURCE,
    PARSER_DESCRIPTION,
    PAYLOAD_KEY_CREATED,
    PAYLOAD_KEY_DRY_RUN,
    PAYLOAD_KEY_FAILED_SLICE,
    PAYLOAD_KEY_PARTIAL,
    PAYLOAD_KEY_PR_URLS,
    PAYLOAD_KEY_RESTORE_ERROR,
    PAYLOAD_KEY_SKIPPED_SLICES,
    PAYLOAD_KEY_SUPERSEDE,
    SKIP_REASON_EMPTY_SLICE,
)
from split_pr_scripts_constants.config.plan_constants import (
    ERROR_PLAN_PATH_REQUIRED,
    FILE_KEY_PATH,
    FILE_KEY_STATUS,
    FILE_STATUS_REMOVED,
    PLAN_KEY_ALL_FILES,
    PLAN_KEY_BASE_REF,
    PLAN_KEY_HEAD_SHA,
    PLAN_KEY_PR_NUMBER,
    PLAN_KEY_PROPOSED_SLICES,
    PLAN_KEY_REPO,
    PLAN_KEY_SOURCE_BRANCH,
    PLAN_KEY_THRESHOLD_NOTE,
    PLAN_KEY_TITLE,
    SLICE_KEY_BASE,
    SLICE_KEY_BRANCH,
    SLICE_KEY_FILES,
    SLICE_KEY_INDEX,
    SLICE_KEY_PR_URL,
    SLICE_KEY_SKIP_REASON,
    SLICE_KEY_SOURCE_BRANCH,
    SLICE_KEY_STORY,
    SLICE_KEY_TITLE,
    VERIFY_KEY_IS_VALID,
)
from supersede_source_pr import build_failed_payload, supersede_source_pr
from verify_plan import load_plan, verify_plan

if str(FRESH_BRANCH_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(FRESH_BRANCH_SCRIPTS_DIRECTORY))

from fresh_branch_git_commands import (  # noqa: E402
    assert_git_accepts_branch_name,
    resolve_repo_root,
)


class SliceExecutionError(RuntimeError):
    """Carry the partial-run payload when one slice fails mid-stack.

    ::

        raise SliceExecutionError(partial_payload)
        # ok:   caught payload is a dict the CLI prints as-is
        # flag: RuntimeError(json.dumps(payload)) re-parsed by the caller

    The CLI reports partial runs as JSON. Carrying the payload on the exception
    keeps it a structured object end to end instead of a string the caller has
    to re-parse.

    Args:
        partial_payload: Created slices, PR URLs, and the failing slice.
    """

    def __init__(self, partial_payload: JsonObject) -> None:
        super().__init__(str(partial_payload.get(PAYLOAD_KEY_ERROR, "")))
        self.partial_payload = partial_payload


@dataclass
class SliceStackOutcome:
    """What one pass over the planned slices produced.

    Attributes:
        all_created: Slice records for every branch that landed a commit.
        all_pr_urls: Draft PR URLs, in stack order.
        all_skipped: Records for slices that carried no change against base.
    """

    all_created: list[JsonObject] = field(default_factory=list)
    all_pr_urls: list[str] = field(default_factory=list)
    all_skipped: list[JsonObject] = field(default_factory=list)


def build_dry_run_steps(plan_payload: JsonObject) -> list[JsonObject]:
    """Describe each slice operation without touching git.

    Args:
        plan_payload: Verified plan dict.

    Returns:
        Ordered step records for the dry-run payload.
    """
    source_branch = str(plan_payload[PLAN_KEY_SOURCE_BRANCH])
    all_steps: list[JsonObject] = []
    for each_slice in plan_payload[PLAN_KEY_PROPOSED_SLICES]:
        if not isinstance(each_slice, dict):
            continue
        all_steps.append(
            build_slice_record(
                slice_record=each_slice,
                branch_name=str(each_slice.get(SLICE_KEY_BRANCH) or ""),
                base_name=str(each_slice.get(SLICE_KEY_BASE) or ""),
                source_branch=source_branch,
                all_files=[str(each) for each in (each_slice.get(SLICE_KEY_FILES) or [])],
                pr_url=None,
            )
        )
    return all_steps


def build_slice_record(
    slice_record: JsonObject,
    branch_name: str,
    base_name: str,
    source_branch: str,
    all_files: list[str],
    pr_url: str | None,
) -> JsonObject:
    """Return the one record shape both dry-run and real execution emit.

    ::

        build_slice_record(slice_record, "split/1-backend", "main", "feat/x", [], None)
        # ok: keys index, branch, base, source_branch, files, title, story, pr_url

    One builder keeps the dry-run preview and the executed result on identical
    keys, so a consumer written against ``--dry-run`` reads a real run too.

    Args:
        slice_record: The planned slice this record describes.
        branch_name: Branch the slice lands on.
        base_name: Branch the slice is stacked on.
        source_branch: Branch the slice files are taken from.
        all_files: Paths carried by the slice.
        pr_url: Draft PR URL when one was opened.

    Returns:
        Slice record keyed by the shared ``SLICE_KEY_*`` names.
    """
    return {
        SLICE_KEY_INDEX: slice_record.get(SLICE_KEY_INDEX),
        SLICE_KEY_BRANCH: branch_name,
        SLICE_KEY_BASE: base_name,
        SLICE_KEY_SOURCE_BRANCH: source_branch,
        SLICE_KEY_FILES: all_files,
        SLICE_KEY_TITLE: slice_record.get(SLICE_KEY_TITLE),
        SLICE_KEY_STORY: slice_record.get(SLICE_KEY_STORY),
        SLICE_KEY_PR_URL: pr_url,
    }


def execute_plan(
    plan_payload: JsonObject,
    repo_root: Path,
    is_dry_run: bool,
    should_create_prs: bool,
    should_push: bool,
    should_supersede: bool,
    should_allow_optional_split: bool,
) -> JsonObject:
    """Run the split (or dry-run) against repo_root.

    Args:
        plan_payload: Verified plan.
        repo_root: Git toplevel.
        is_dry_run: When True, only describe steps.
        should_create_prs: When True, open draft PRs after push.
        should_push: When True, push branches to origin.
        should_supersede: When True, close source_pr_number after a full
            multi-slice draft stack lands.
        should_allow_optional_split: When True, execute a plan whose
            ``threshold_note`` says the split is optional.

    Returns:
        Result payload with created slice metadata.

    Raises:
        RuntimeError: On dirty tree, git, or gh failures.
        SliceExecutionError: When one slice fails after others landed.
        ValueError: When the plan fails coverage verification or the plan
            advises against splitting without an explicit override.
    """
    report = verify_plan(plan_payload)
    if not report[VERIFY_KEY_IS_VALID]:
        raise ValueError(ERROR_EXECUTE_FAILED % report)
    assert_split_is_advised(plan_payload, should_allow_optional_split)
    if is_dry_run:
        return {
            PAYLOAD_KEY_DRY_RUN: True,
            PAYLOAD_KEY_CREATED: build_dry_run_steps(plan_payload),
            PAYLOAD_KEY_PR_URLS: [],
            PAYLOAD_KEY_SKIPPED_SLICES: [],
        }
    if is_working_tree_dirty(repo_root):
        raise RuntimeError(ERROR_DIRTY_TREE)
    return _execute_slices(
        plan_payload=plan_payload,
        repo_root=repo_root,
        should_create_prs=should_create_prs,
        should_push=should_push,
        should_supersede=should_supersede,
    )


def assert_split_is_advised(
    plan_payload: JsonObject,
    should_allow_optional_split: bool,
) -> None:
    """Raise when the plan advises against splitting and no override is set.

    ::

        assert_split_is_advised({"threshold_note": None}, False)      # ok
        assert_split_is_advised({"threshold_note": "optional"}, False)  # flag

    ``analyze_pr`` records a ``threshold_note`` when the parent already fits the
    review budget. Honouring it here stops the executor from stacking draft PRs
    and closing the source PR over a guard rail the plan already raised.

    Args:
        plan_payload: Parsed plan dict.
        should_allow_optional_split: The caller's explicit override.

    Raises:
        ValueError: When the note is present and the override is absent.
    """
    if should_allow_optional_split:
        return
    threshold_note = plan_payload.get(PLAN_KEY_THRESHOLD_NOTE)
    if threshold_note:
        raise ValueError(ERROR_SPLIT_OPTIONAL_REFUSED % threshold_note)


def assert_source_head_matches_plan(repo_root: Path, plan_payload: JsonObject) -> None:
    """Raise when the source branch has moved since the plan was written.

    ::

        assert_source_head_matches_plan(repo_root, plan)  # ok: heads agree
        # flag: RuntimeError naming the planned sha and the current head

    ``analyze_pr`` records ``head_sha`` on the plan. A branch that has advanced
    since then holds commits the plan never saw. Those files would be dropped
    from the stack, then superseded away with the source PR. Failing here sends
    the operator back to analyze instead.

    Args:
        repo_root: Git toplevel.
        plan_payload: Parsed plan carrying ``head_sha`` and ``source_branch``.

    Raises:
        RuntimeError: When the head moved or cannot be read.
    """
    planned_head_sha = str(plan_payload.get(PLAN_KEY_HEAD_SHA) or "")
    source_branch = str(plan_payload[PLAN_KEY_SOURCE_BRANCH])
    if not planned_head_sha:
        return
    current_completed = run_checked_git(
        [GIT_REV_PARSE, source_branch],
        repo_root,
        ERROR_SOURCE_HEAD_UNREADABLE,
        (source_branch,),
    )
    current_head_sha = current_completed.stdout.strip()
    if not current_head_sha.startswith(planned_head_sha):
        raise RuntimeError(
            ERROR_SOURCE_HEAD_MOVED
            % (source_branch, current_head_sha, planned_head_sha)
        )


def _execute_slices(
    plan_payload: JsonObject,
    repo_root: Path,
    should_create_prs: bool,
    should_push: bool,
    should_supersede: bool,
) -> JsonObject:
    source_branch = str(plan_payload[PLAN_KEY_SOURCE_BRANCH])
    base_ref = str(plan_payload[PLAN_KEY_BASE_REF])
    pr_number = int(plan_payload[PLAN_KEY_PR_NUMBER])
    repo = plan_payload.get(PLAN_KEY_REPO)
    repo_slug = repo if isinstance(repo, str) else None
    all_planned_slices = [
        each_slice
        for each_slice in plan_payload[PLAN_KEY_PROPOSED_SLICES]
        if isinstance(each_slice, dict)
    ]
    _assert_plan_refs_are_safe(
        source_branch=source_branch,
        base_ref=base_ref,
        all_planned_slices=all_planned_slices,
    )
    _fetch_plan_refs(
        repo_root=repo_root,
        base_ref=base_ref,
        source_branch=source_branch,
        should_push=should_push,
    )
    assert_source_head_matches_plan(repo_root, plan_payload)
    stack_outcome = _create_slices_and_restore(
        all_planned_slices=all_planned_slices,
        plan_payload=plan_payload,
        repo_root=repo_root,
        source_branch=source_branch,
        pr_number=pr_number,
        should_push=should_push,
        should_create_prs=should_create_prs,
        repo_slug=repo_slug,
    )
    return _build_success_payload(
        stack_outcome=stack_outcome,
        pr_number=pr_number,
        planned_slice_count=len(all_planned_slices) - len(stack_outcome.all_skipped),
        should_create_prs=should_create_prs,
        should_supersede=should_supersede,
        repo_slug=repo_slug,
        repo_root=repo_root,
    )


def _create_slices_and_restore(
    all_planned_slices: list[JsonObject],
    plan_payload: JsonObject,
    repo_root: Path,
    source_branch: str,
    pr_number: int,
    should_push: bool,
    should_create_prs: bool,
    repo_slug: str | None,
) -> SliceStackOutcome:
    starting_state = read_starting_state(repo_root)
    try:
        stack_outcome = _create_all_slices(
            all_planned_slices=all_planned_slices,
            repo_root=repo_root,
            source_branch=source_branch,
            pr_number=pr_number,
            should_push=should_push,
            should_create_prs=should_create_prs,
            repo_slug=repo_slug,
            all_deleted_paths=_deleted_paths(plan_payload),
        )
    except SliceExecutionError as slice_error:
        slice_error.partial_payload[PAYLOAD_KEY_RESTORE_ERROR] = (
            restore_starting_state(repo_root, starting_state)
        )
        raise
    restore_failure = restore_starting_state(repo_root, starting_state)
    if restore_failure:
        raise RuntimeError(ERROR_RESTORE_FAILED % (starting_state, restore_failure))
    return stack_outcome


def _assert_plan_refs_are_safe(
    source_branch: str,
    base_ref: str,
    all_planned_slices: list[JsonObject],
) -> None:
    all_ref_names = [source_branch, base_ref]
    for each_slice in all_planned_slices:
        all_ref_names.append(str(each_slice[SLICE_KEY_BRANCH]))
        all_ref_names.append(str(each_slice[SLICE_KEY_BASE]))
    for each_ref_name in all_ref_names:
        assert_git_accepts_branch_name(each_ref_name)


def _fetch_plan_refs(
    repo_root: Path,
    base_ref: str,
    source_branch: str,
    should_push: bool,
) -> None:
    if not remote_exists(repo_root, GIT_ORIGIN):
        if should_push:
            raise RuntimeError(ERROR_NO_ORIGIN_REMOTE)
        return
    run_checked_git(
        [GIT_FETCH, GIT_ORIGIN, base_ref, source_branch],
        repo_root,
        ERROR_EXECUTE_FAILED,
        ALL_EMPTY_ERROR_CONTEXT,
    )


def _deleted_paths(plan_payload: JsonObject) -> set[str]:
    all_source_records = plan_payload.get(PLAN_KEY_ALL_FILES)
    if not isinstance(all_source_records, list):
        return set()
    return {
        str(each_record[FILE_KEY_PATH])
        for each_record in all_source_records
        if isinstance(each_record, dict)
        and each_record.get(FILE_KEY_PATH)
        and str(each_record.get(FILE_KEY_STATUS) or "") == FILE_STATUS_REMOVED
    }


def _create_all_slices(
    all_planned_slices: list[JsonObject],
    repo_root: Path,
    source_branch: str,
    pr_number: int,
    should_push: bool,
    should_create_prs: bool,
    repo_slug: str | None,
    all_deleted_paths: set[str],
) -> SliceStackOutcome:
    stack_outcome = SliceStackOutcome()
    base_override: str | None = None
    for each_slice in all_planned_slices:
        base_name = base_override or str(each_slice[SLICE_KEY_BASE])
        created = _execute_one_slice_or_fail(
            slice_record=each_slice,
            repo_root=repo_root,
            base_name=base_name,
            source_branch=source_branch,
            pr_number=pr_number,
            should_push=should_push,
            should_create_prs=should_create_prs,
            repo_slug=repo_slug,
            all_deleted_paths=all_deleted_paths,
            stack_outcome=stack_outcome,
        )
        if created is None:
            base_override = base_name
            stack_outcome.all_skipped.append(
                _build_skipped_record(each_slice, base_name, SKIP_REASON_EMPTY_SLICE)
            )
            continue
        base_override = None
        stack_outcome.all_created.append(created)
        pr_url = created.get(SLICE_KEY_PR_URL)
        if pr_url:
            stack_outcome.all_pr_urls.append(str(pr_url))
    return stack_outcome


def _execute_one_slice_or_fail(
    slice_record: JsonObject,
    repo_root: Path,
    base_name: str,
    source_branch: str,
    pr_number: int,
    should_push: bool,
    should_create_prs: bool,
    repo_slug: str | None,
    all_deleted_paths: set[str],
    stack_outcome: SliceStackOutcome,
) -> JsonObject | None:
    try:
        return _execute_one_slice(
            slice_record=slice_record,
            repo_root=repo_root,
            base_name=base_name,
            source_branch=source_branch,
            pr_number=pr_number,
            should_push=should_push,
            should_create_prs=should_create_prs,
            repo=repo_slug,
            all_deleted_paths=all_deleted_paths,
        )
    except SliceExecutionError:
        raise
    except (RuntimeError, OSError, subprocess.SubprocessError) as slice_error:
        raise SliceExecutionError(
            _build_partial_payload(stack_outcome, slice_record, str(slice_error))
        ) from slice_error


def _build_partial_payload(
    stack_outcome: SliceStackOutcome,
    failed_slice_record: JsonObject,
    error_text: str,
) -> JsonObject:
    return {
        PAYLOAD_KEY_DRY_RUN: False,
        PAYLOAD_KEY_CREATED: stack_outcome.all_created,
        PAYLOAD_KEY_PR_URLS: stack_outcome.all_pr_urls,
        PAYLOAD_KEY_SKIPPED_SLICES: stack_outcome.all_skipped,
        PAYLOAD_KEY_ERROR: error_text,
        PAYLOAD_KEY_FAILED_SLICE: failed_slice_record.get(SLICE_KEY_BRANCH),
        PAYLOAD_KEY_PARTIAL: True,
    }


def _build_skipped_record(
    slice_record: JsonObject,
    base_name: str,
    skip_reason: str,
) -> JsonObject:
    return {
        SLICE_KEY_INDEX: slice_record.get(SLICE_KEY_INDEX),
        SLICE_KEY_BRANCH: slice_record.get(SLICE_KEY_BRANCH),
        SLICE_KEY_BASE: base_name,
        SLICE_KEY_FILES: [str(each) for each in (slice_record.get(SLICE_KEY_FILES) or [])],
        SLICE_KEY_SKIP_REASON: skip_reason,
    }


def _build_success_payload(
    stack_outcome: SliceStackOutcome,
    pr_number: int,
    planned_slice_count: int,
    should_create_prs: bool,
    should_supersede: bool,
    repo_slug: str | None,
    repo_root: Path,
) -> JsonObject:
    return {
        PAYLOAD_KEY_DRY_RUN: False,
        PAYLOAD_KEY_CREATED: stack_outcome.all_created,
        PAYLOAD_KEY_PR_URLS: stack_outcome.all_pr_urls,
        PAYLOAD_KEY_SKIPPED_SLICES: stack_outcome.all_skipped,
        PAYLOAD_KEY_PARTIAL: False,
        PAYLOAD_KEY_SUPERSEDE: _run_supersede_safely(
            pr_number=pr_number,
            all_pr_urls=stack_outcome.all_pr_urls,
            planned_slice_count=planned_slice_count,
            should_create_prs=should_create_prs,
            should_supersede=should_supersede,
            repo_slug=repo_slug,
            repo_root=repo_root,
        ),
    }


def _run_supersede_safely(
    pr_number: int,
    all_pr_urls: list[str],
    planned_slice_count: int,
    should_create_prs: bool,
    should_supersede: bool,
    repo_slug: str | None,
    repo_root: Path,
) -> JsonObject:
    try:
        return supersede_source_pr(
            source_pr_number=pr_number,
            all_child_pr_urls=all_pr_urls,
            planned_slice_count=planned_slice_count,
            should_create_prs=should_create_prs,
            should_supersede=should_supersede,
            repo=repo_slug,
            repo_root=repo_root,
        )
    except (
        RuntimeError,
        ValueError,
        OSError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as supersede_error:
        return build_failed_payload(all_pr_urls, str(supersede_error))


def _execute_one_slice(
    slice_record: JsonObject,
    repo_root: Path,
    base_name: str,
    source_branch: str,
    pr_number: int,
    should_push: bool,
    should_create_prs: bool,
    repo: str | None,
    all_deleted_paths: set[str],
) -> JsonObject | None:
    branch_name = str(slice_record[SLICE_KEY_BRANCH])
    all_files = [str(each) for each in (slice_record.get(SLICE_KEY_FILES) or [])]
    title = str(slice_record.get(SLICE_KEY_TITLE) or branch_name)
    story = str(slice_record.get(SLICE_KEY_STORY) or "")
    if branch_exists(repo_root, branch_name):
        raise RuntimeError(ERROR_BRANCH_EXISTS % branch_name)
    base_ref_for_checkout = _resolve_base_ref(repo_root, base_name, source_branch)
    run_checked_git(
        [GIT_CHECKOUT, GIT_CHECKOUT_FORCE_CREATE, branch_name, base_ref_for_checkout],
        repo_root,
        ERROR_EXECUTE_FAILED,
        ALL_EMPTY_ERROR_CONTEXT,
    )
    _stage_slice_files(repo_root, source_branch, all_files, all_deleted_paths)
    if not is_working_tree_dirty(repo_root):
        _abandon_empty_slice(repo_root, branch_name, base_ref_for_checkout)
        return None
    _commit_slice(repo_root, title, story, pr_number, branch_name)
    pr_url = _maybe_push_and_open_pr(
        repo_root=repo_root,
        branch_name=branch_name,
        base_name=base_name,
        title=title,
        story=story,
        pr_number=pr_number,
        should_push=should_push,
        should_create_prs=should_create_prs,
        repo=repo,
    )
    return build_slice_record(
        slice_record=slice_record,
        branch_name=branch_name,
        base_name=base_name,
        source_branch=source_branch,
        all_files=all_files,
        pr_url=pr_url,
    )


def _abandon_empty_slice(
    repo_root: Path,
    branch_name: str,
    base_ref_for_checkout: str,
) -> None:
    run_checked_git(
        [GIT_CHECKOUT, GIT_FORCE_FLAG, base_ref_for_checkout],
        repo_root,
        ERROR_EXECUTE_FAILED,
        ALL_EMPTY_ERROR_CONTEXT,
    )
    run_git([GIT_BRANCH, GIT_DELETE_BRANCH_FLAG, branch_name], repo_root)


def _resolve_base_ref(repo_root: Path, base_name: str, source_branch: str) -> str:
    if base_name.startswith(GIT_ORIGIN_PREFIX) or base_name == source_branch:
        return base_name
    origin_candidate = f"{GIT_ORIGIN_PREFIX}{base_name}"
    if remote_ref_exists(repo_root, origin_candidate):
        return origin_candidate
    return base_name


def _stage_slice_files(
    repo_root: Path,
    source_branch: str,
    all_files: list[str],
    all_deleted_paths: set[str],
) -> None:
    all_present_paths = [each for each in all_files if each not in all_deleted_paths]
    all_removed_paths = [each for each in all_files if each in all_deleted_paths]
    if all_present_paths:
        _checkout_source_files(repo_root, source_branch, all_present_paths)
        run_checked_git(
            [GIT_ADD, GIT_ADD_PATHSPEC, *all_present_paths],
            repo_root,
            ERROR_EXECUTE_FAILED,
            ALL_EMPTY_ERROR_CONTEXT,
        )
    for each_removed_path in all_removed_paths:
        run_git(
            [GIT_REMOVE, GIT_QUIET_FLAG, GIT_ADD_PATHSPEC, each_removed_path],
            repo_root,
        )


def _checkout_source_files(
    repo_root: Path,
    source_branch: str,
    all_files: list[str],
) -> None:
    run_checked_git(
        [GIT_CHECKOUT, source_branch, GIT_ADD_PATHSPEC, *all_files],
        repo_root,
        ERROR_CHECKOUT_FILES,
        (source_branch,),
    )


def _commit_slice(
    repo_root: Path,
    title: str,
    story: str,
    pr_number: int,
    branch_name: str,
) -> None:
    commit_message = DEFAULT_COMMIT_MESSAGE_TEMPLATE % (title, story, pr_number)
    run_checked_git(
        [GIT_COMMIT, GIT_MESSAGE_FLAG, commit_message],
        repo_root,
        ERROR_COMMIT_FAILED,
        (branch_name,),
    )


def _maybe_push_and_open_pr(
    repo_root: Path,
    branch_name: str,
    base_name: str,
    title: str,
    story: str,
    pr_number: int,
    should_push: bool,
    should_create_prs: bool,
    repo: str | None,
) -> str | None:
    if not should_push:
        return None
    run_checked_git(
        [GIT_PUSH, GIT_SET_UPSTREAM, GIT_ORIGIN, branch_name],
        repo_root,
        ERROR_PUSH_FAILED,
        (branch_name,),
    )
    if not should_create_prs:
        return None
    return create_draft_pr(
        repo_root=repo_root,
        title=title,
        story=story,
        base_name=base_name,
        head_name=branch_name,
        pr_number=pr_number,
        repo=repo,
    )


def main() -> int:
    """CLI entry: execute or dry-run a verified plan.

    Returns:
        Process exit code (0 success, 1 failure).

    Raises:
        Does not raise; failures print JSON error and return 1.
    """
    parsed_arguments = _parse_arguments()
    indent = JSON_INDENT_SPACES if parsed_arguments.pretty else None
    try:
        execution_payload = _execute_parsed_arguments(parsed_arguments)
    except SliceExecutionError as partial_error:
        print(json.dumps(partial_error.partial_payload, indent=indent))
        return EXIT_CODE_FAILURE
    except (
        ValueError,
        RuntimeError,
        OSError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
    ) as error:
        print(json.dumps({PAYLOAD_KEY_ERROR: str(error)}))
        return EXIT_CODE_FAILURE
    print(json.dumps(execution_payload, indent=indent))
    return EXIT_CODE_SUCCESS


def _execute_parsed_arguments(parsed_arguments: argparse.Namespace) -> JsonObject:
    if not parsed_arguments.plan:
        raise ValueError(ERROR_PLAN_PATH_REQUIRED)
    plan_payload = load_plan(Path(parsed_arguments.plan))
    if PLAN_KEY_TITLE not in plan_payload or PLAN_KEY_PR_NUMBER not in plan_payload:
        raise ValueError(ERROR_EXECUTE_FAILED % ERROR_PLAN_MISSING_PR_IDENTITY)
    is_create_prs = parsed_arguments.create_prs and not parsed_arguments.dry_run
    should_push = (
        parsed_arguments.push or parsed_arguments.create_prs
    ) and not parsed_arguments.dry_run
    return execute_plan(
        plan_payload=plan_payload,
        repo_root=resolve_repo_root(Path(parsed_arguments.repo_path).resolve()),
        is_dry_run=parsed_arguments.dry_run,
        should_create_prs=is_create_prs,
        should_push=should_push,
        should_supersede=_resolve_supersede_choice(parsed_arguments, is_create_prs),
        should_allow_optional_split=parsed_arguments.allow_optional_split,
    )


def _resolve_supersede_choice(
    parsed_arguments: argparse.Namespace,
    is_create_prs: bool,
) -> bool:
    if parsed_arguments.supersede_source is None:
        return is_create_prs
    return bool(parsed_arguments.supersede_source)


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=PARSER_DESCRIPTION)
    parser.add_argument(ARGUMENT_PLAN, required=True, help=HELP_PLAN)
    parser.add_argument(
        ARGUMENT_REPO_PATH,
        default=DEFAULT_REPO_PATH,
        help=HELP_REPO_PATH,
    )
    parser.add_argument(
        ARGUMENT_DRY_RUN,
        action=ARGUMENT_STORE_TRUE_ACTION,
        help=HELP_DRY_RUN,
    )
    parser.add_argument(ARGUMENT_PUSH, action=ARGUMENT_STORE_TRUE_ACTION, help=HELP_PUSH)
    parser.add_argument(
        ARGUMENT_CREATE_PRS,
        action=ARGUMENT_STORE_TRUE_ACTION,
        help=HELP_CREATE_PRS,
    )
    parser.add_argument(
        ARGUMENT_ALLOW_OPTIONAL_SPLIT,
        action=ARGUMENT_STORE_TRUE_ACTION,
        help=HELP_ALLOW_OPTIONAL_SPLIT,
    )
    parser.add_argument(
        ARGUMENT_SUPERSEDE_SOURCE,
        action=argparse.BooleanOptionalAction,
        default=None,
        help=HELP_SUPERSEDE_SOURCE,
    )
    parser.add_argument(
        ARGUMENT_PRETTY,
        action=ARGUMENT_STORE_TRUE_ACTION,
        help=HELP_PRETTY,
    )
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
