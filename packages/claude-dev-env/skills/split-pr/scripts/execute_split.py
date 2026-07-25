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
import tempfile
from pathlib import Path

from split_pr_scripts_constants.config.analyze_constants import (
    EXIT_CODE_FAILURE,
    EXIT_CODE_SUCCESS,
    PAYLOAD_KEY_ERROR,
    PLAN_THRESHOLD_NOTE_KEY,
)
from split_pr_scripts_constants.config.execute_constants import (
    DEFAULT_COMMIT_MESSAGE_TEMPLATE,
    ERROR_BRANCH_EXISTS,
    ERROR_CHECKOUT_FILES,
    ERROR_COMMIT_FAILED,
    ERROR_DIRTY_TREE,
    ERROR_EXECUTE_FAILED,
    ERROR_NO_ORIGIN_REMOTE,
    ERROR_PLAN_MISSING_PR_IDENTITY,
    ERROR_PR_CREATE_FAILED,
    ERROR_PUSH_FAILED,
    ERROR_REPO_NOT_GIT,
    ERROR_RESTORE_FAILED,
    ERROR_SOURCE_HEAD_MOVED,
    ERROR_SOURCE_HEAD_UNREADABLE,
    ERROR_SPLIT_OPTIONAL_REFUSED,
    FRESH_BRANCH_SCRIPTS_DIRECTORY,
    GH_BASE,
    GH_BODY_FILE,
    GH_COMMAND,
    GH_CREATE,
    GH_DRAFT,
    GH_HEAD,
    GH_PR,
    GH_REPO_FLAG,
    GH_TITLE,
    GIT_ABBREV_REF_FLAG,
    GIT_ADD,
    GIT_ADD_PATHSPEC,
    GIT_BRANCH,
    GIT_CHECKOUT,
    GIT_CHECKOUT_FORCE_CREATE,
    GIT_COMMAND,
    GIT_COMMIT,
    GIT_DELETE_BRANCH_FLAG,
    GIT_FETCH,
    GIT_FORCE_FLAG,
    GIT_HEAD_REF,
    GIT_LIST_FLAG,
    GIT_MESSAGE_FLAG,
    GIT_ORIGIN,
    GIT_PORCELAIN,
    GIT_PUSH,
    GIT_QUIET_FLAG,
    GIT_REFS_HEADS_PREFIX,
    GIT_REFS_REMOTES_PREFIX,
    GIT_REMOTE,
    GIT_REMOVE,
    GIT_REV_PARSE,
    GIT_SET_UPSTREAM,
    GIT_SHORT_FLAG,
    GIT_SHOW_REF,
    GIT_SHOW_TOPLEVEL,
    GIT_STATUS,
    GIT_SYMBOLIC_REF,
    GIT_VERIFY_FLAG,
    JSON_INDENT_SPACES,
    MARKDOWN_BODY_SUFFIX,
    PAYLOAD_KEY_CREATED,
    PAYLOAD_KEY_DRY_RUN,
    PAYLOAD_KEY_FAILED_SLICE,
    PAYLOAD_KEY_PARTIAL,
    PAYLOAD_KEY_PR_URLS,
    PAYLOAD_KEY_CHILD_PR_NUMBERS,
    PAYLOAD_KEY_CLOSED,
    PAYLOAD_KEY_COMMENTED,
    PAYLOAD_KEY_RESTORE_ERROR,
    PAYLOAD_KEY_SKIPPED,
    PAYLOAD_KEY_SKIPPED_SLICES,
    PAYLOAD_KEY_SUPERSEDE,
    PRETTY_FLAG,
    SKIP_REASON_EMPTY_SLICE,
)
from supersede_source_pr import extract_pr_number_from_url, supersede_source_pr
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
from verify_plan import load_plan, verify_plan

if str(FRESH_BRANCH_SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(FRESH_BRANCH_SCRIPTS_DIRECTORY))

from fresh_branch_git_commands import assert_git_accepts_branch_name  # noqa: E402

JsonObject = dict[str, object]


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


def resolve_repo_root(repo_path: Path) -> Path:
    """Return the git toplevel for repo_path.

    Args:
        repo_path: Path inside a git repository.

    Returns:
        Absolute repository root.

    Raises:
        RuntimeError: When the path is not inside a git work tree.
    """
    completed = subprocess.run(
        [GIT_COMMAND, GIT_REV_PARSE, GIT_SHOW_TOPLEVEL],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(ERROR_REPO_NOT_GIT % repo_path)
    return Path(completed.stdout.strip())


def is_working_tree_dirty(repo_root: Path) -> bool:
    """Return True when the worktree has uncommitted changes.

    Args:
        repo_root: Git repository toplevel.

    Returns:
        True when ``git status --porcelain`` is non-empty.
    """
    completed = subprocess.run(
        [GIT_COMMAND, GIT_STATUS, GIT_PORCELAIN],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    return bool(completed.stdout.strip())


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
    threshold_note = plan_payload.get(PLAN_THRESHOLD_NOTE_KEY)
    if threshold_note:
        raise ValueError(ERROR_SPLIT_OPTIONAL_REFUSED % threshold_note)


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
    all_created: list[JsonObject] = []
    all_pr_urls: list[str] = []
    all_skipped: list[JsonObject] = []
    _create_slices_and_restore(
        all_planned_slices=all_planned_slices,
        plan_payload=plan_payload,
        repo_root=repo_root,
        source_branch=source_branch,
        pr_number=pr_number,
        should_push=should_push,
        should_create_prs=should_create_prs,
        repo_slug=repo_slug,
        all_created=all_created,
        all_pr_urls=all_pr_urls,
        all_skipped=all_skipped,
    )
    return _build_success_payload(
        all_created=all_created,
        all_pr_urls=all_pr_urls,
        all_skipped=all_skipped,
        pr_number=pr_number,
        planned_slice_count=len(all_planned_slices) - len(all_skipped),
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
    all_created: list[JsonObject],
    all_pr_urls: list[str],
    all_skipped: list[JsonObject],
) -> None:
    starting_state = _read_starting_state(repo_root)
    try:
        _create_all_slices(
            all_planned_slices=all_planned_slices,
            repo_root=repo_root,
            source_branch=source_branch,
            pr_number=pr_number,
            should_push=should_push,
            should_create_prs=should_create_prs,
            repo_slug=repo_slug,
            all_deleted_paths=_deleted_paths(plan_payload),
            all_created=all_created,
            all_pr_urls=all_pr_urls,
            all_skipped=all_skipped,
        )
    except SliceExecutionError as slice_error:
        slice_error.partial_payload[PAYLOAD_KEY_SKIPPED_SLICES] = all_skipped
        slice_error.partial_payload[PAYLOAD_KEY_RESTORE_ERROR] = (
            _restore_starting_state(repo_root, starting_state)
        )
        raise
    restore_failure = _restore_starting_state(repo_root, starting_state)
    if restore_failure:
        raise RuntimeError(ERROR_RESTORE_FAILED % (starting_state, restore_failure))


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
    if not _remote_exists(repo_root, GIT_ORIGIN):
        if should_push:
            raise RuntimeError(ERROR_NO_ORIGIN_REMOTE)
        return
    _run_git([GIT_FETCH, GIT_ORIGIN, base_ref, source_branch], repo_root)


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
    current_completed = _read_ref_commit(repo_root, source_branch)
    if current_completed.returncode != 0:
        detail = (current_completed.stderr or current_completed.stdout or "").strip()
        raise RuntimeError(ERROR_SOURCE_HEAD_UNREADABLE % (source_branch, detail))
    current_head_sha = current_completed.stdout.strip()
    if not current_head_sha.startswith(planned_head_sha):
        raise RuntimeError(
            ERROR_SOURCE_HEAD_MOVED
            % (source_branch, current_head_sha, planned_head_sha)
        )


def _read_ref_commit(
    repo_root: Path,
    ref_name: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [GIT_COMMAND, GIT_REV_PARSE, ref_name],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
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
    all_created: list[JsonObject],
    all_pr_urls: list[str],
    all_skipped: list[JsonObject],
) -> None:
    base_override: str | None = None
    for each_slice in all_planned_slices:
        base_name = base_override or str(each_slice[SLICE_KEY_BASE])
        try:
            created = _execute_one_slice(
                slice_record=each_slice,
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
                {
                    PAYLOAD_KEY_DRY_RUN: False,
                    PAYLOAD_KEY_CREATED: all_created,
                    PAYLOAD_KEY_PR_URLS: all_pr_urls,
                    PAYLOAD_KEY_ERROR: str(slice_error),
                    PAYLOAD_KEY_FAILED_SLICE: each_slice.get(SLICE_KEY_BRANCH),
                    PAYLOAD_KEY_PARTIAL: True,
                }
            ) from slice_error
        if created is None:
            base_override = base_name
            all_skipped.append(
                _build_skipped_record(each_slice, base_name, SKIP_REASON_EMPTY_SLICE)
            )
            continue
        base_override = None
        all_created.append(created)
        pr_url = created.get(SLICE_KEY_PR_URL)
        if pr_url:
            all_pr_urls.append(str(pr_url))


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
    all_created: list[JsonObject],
    all_pr_urls: list[str],
    all_skipped: list[JsonObject],
    pr_number: int,
    planned_slice_count: int,
    should_create_prs: bool,
    should_supersede: bool,
    repo_slug: str | None,
    repo_root: Path,
) -> JsonObject:
    execution_payload: JsonObject = {
        PAYLOAD_KEY_DRY_RUN: False,
        PAYLOAD_KEY_CREATED: all_created,
        PAYLOAD_KEY_PR_URLS: all_pr_urls,
        PAYLOAD_KEY_SKIPPED_SLICES: all_skipped,
        PAYLOAD_KEY_PARTIAL: False,
    }
    execution_payload[PAYLOAD_KEY_SUPERSEDE] = _run_supersede_safely(
        pr_number=pr_number,
        all_pr_urls=all_pr_urls,
        planned_slice_count=planned_slice_count,
        should_create_prs=should_create_prs,
        should_supersede=should_supersede,
        repo_slug=repo_slug,
        repo_root=repo_root,
    )
    return execution_payload


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
        all_child_numbers = [
            each_number
            for each_url in all_pr_urls
            if (each_number := extract_pr_number_from_url(each_url)) is not None
        ]
        return {
            PAYLOAD_KEY_COMMENTED: False,
            PAYLOAD_KEY_CLOSED: False,
            PAYLOAD_KEY_CHILD_PR_NUMBERS: all_child_numbers,
            PAYLOAD_KEY_SKIPPED: False,
            PAYLOAD_KEY_ERROR: str(supersede_error),
        }


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
    if _branch_exists(repo_root, branch_name):
        raise RuntimeError(ERROR_BRANCH_EXISTS % branch_name)
    base_ref_for_checkout = _resolve_base_ref(repo_root, base_name, source_branch)
    _run_git(
        [GIT_CHECKOUT, GIT_CHECKOUT_FORCE_CREATE, branch_name, base_ref_for_checkout],
        repo_root,
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
    _run_git([GIT_CHECKOUT, GIT_FORCE_FLAG, base_ref_for_checkout], repo_root)
    _run_git([GIT_BRANCH, GIT_DELETE_BRANCH_FLAG, branch_name], repo_root, is_check=False)


def _resolve_base_ref(repo_root: Path, base_name: str, source_branch: str) -> str:
    if base_name.startswith(f"{GIT_ORIGIN}/") or base_name == source_branch:
        return base_name
    origin_candidate = f"{GIT_ORIGIN}/{base_name}"
    if _remote_ref_exists(repo_root, origin_candidate):
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
        _run_git([GIT_ADD, GIT_ADD_PATHSPEC, *all_present_paths], repo_root)
    for each_removed_path in all_removed_paths:
        _remove_slice_path(repo_root, each_removed_path)


def _remove_slice_path(repo_root: Path, removed_path: str) -> None:
    _run_git(
        [GIT_REMOVE, GIT_QUIET_FLAG, GIT_ADD_PATHSPEC, removed_path],
        repo_root,
        is_check=False,
    )


def _checkout_source_files(
    repo_root: Path,
    source_branch: str,
    all_files: list[str],
) -> None:
    checkout_outcome = subprocess.run(
        [GIT_COMMAND, GIT_CHECKOUT, source_branch, GIT_ADD_PATHSPEC, *all_files],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if checkout_outcome.returncode != 0:
        detail = (checkout_outcome.stderr or checkout_outcome.stdout or "").strip()
        raise RuntimeError(ERROR_CHECKOUT_FILES % (source_branch, detail))


def _commit_slice(
    repo_root: Path,
    title: str,
    story: str,
    pr_number: int,
    branch_name: str,
) -> None:
    commit_message = DEFAULT_COMMIT_MESSAGE_TEMPLATE % (title, story, pr_number)
    commit_outcome = subprocess.run(
        [GIT_COMMAND, GIT_COMMIT, GIT_MESSAGE_FLAG, commit_message],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if commit_outcome.returncode != 0:
        detail = (commit_outcome.stderr or commit_outcome.stdout or "").strip()
        raise RuntimeError(ERROR_COMMIT_FAILED % (branch_name, detail))


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
    push_outcome = subprocess.run(
        [GIT_COMMAND, GIT_PUSH, GIT_SET_UPSTREAM, GIT_ORIGIN, branch_name],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if push_outcome.returncode != 0:
        detail = (push_outcome.stderr or push_outcome.stdout or "").strip()
        raise RuntimeError(ERROR_PUSH_FAILED % (branch_name, detail))
    if not should_create_prs:
        return None
    return _create_draft_pr(
        repo_root=repo_root,
        title=title,
        story=story,
        base_name=base_name,
        head_name=branch_name,
        pr_number=pr_number,
        repo=repo,
    )


def _create_draft_pr(
    repo_root: Path,
    title: str,
    story: str,
    base_name: str,
    head_name: str,
    pr_number: int,
    repo: str | None,
) -> str:
    body = (
        f"## Summary\n\n{story}\n\n"
        f"## Split source\n\nExcised from pull request #{pr_number} via `/split-pr`.\n\n"
        f"## Dependencies\n\nBase branch: `{base_name}`. Merge earlier slices first.\n\n"
        "## Testing\n\n"
        "File-partitioned from the parent pull request. Project-wide CI on this "
        "slice alone is not claimed by `/split-pr` unless verified separately.\n"
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=MARKDOWN_BODY_SUFFIX,
        delete=False,
    ) as body_file:
        body_file.write(body)
        body_path = body_file.name
    all_command = [
        GH_COMMAND,
        GH_PR,
        GH_CREATE,
        GH_DRAFT,
        GH_TITLE,
        title,
        GH_BODY_FILE,
        body_path,
        GH_BASE,
        base_name,
        GH_HEAD,
        head_name,
    ]
    if repo:
        all_command.extend([GH_REPO_FLAG, repo])
    try:
        completed = subprocess.run(
            all_command,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
        )
    finally:
        Path(body_path).unlink(missing_ok=True)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(ERROR_PR_CREATE_FAILED % (head_name, detail))
    return (completed.stdout or "").strip()


def _run_git(
    all_arguments: list[str],
    repo_root: Path,
    is_check: bool = True,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [GIT_COMMAND, *all_arguments],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if is_check and completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(ERROR_EXECUTE_FAILED % detail)
    return completed


def _read_starting_state(repo_root: Path) -> str:
    """Return the ref to return to: the checked-out branch, else its commit."""
    branch_completed = _run_git(
        [GIT_SYMBOLIC_REF, GIT_QUIET_FLAG, GIT_SHORT_FLAG, GIT_HEAD_REF],
        repo_root,
        is_check=False,
    )
    branch_name = branch_completed.stdout.strip()
    if branch_completed.returncode == 0 and branch_name:
        return branch_name
    commit_completed = _run_git([GIT_REV_PARSE, GIT_HEAD_REF], repo_root)
    return commit_completed.stdout.strip()


def _restore_starting_state(repo_root: Path, starting_state: str) -> str | None:
    """Return to starting_state, discarding staged slice work; None when clean."""
    completed = _run_git(
        [GIT_CHECKOUT, GIT_FORCE_FLAG, starting_state],
        repo_root,
        is_check=False,
    )
    if completed.returncode == 0:
        return None
    return (completed.stderr or completed.stdout or "").strip()


def _current_branch(repo_root: Path) -> str:
    completed = _run_git([GIT_REV_PARSE, GIT_ABBREV_REF_FLAG, GIT_HEAD_REF], repo_root)
    return completed.stdout.strip()


def _branch_exists(repo_root: Path, branch_name: str) -> bool:
    completed = subprocess.run(
        [GIT_COMMAND, GIT_BRANCH, GIT_LIST_FLAG, branch_name],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(completed.stdout.strip())


def _show_ref_verifies(repo_root: Path, full_ref: str) -> bool:
    completed = subprocess.run(
        [GIT_COMMAND, GIT_SHOW_REF, GIT_VERIFY_FLAG, GIT_QUIET_FLAG, full_ref],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0


def _remote_ref_exists(repo_root: Path, remote_ref_name: str) -> bool:
    """Answer whether ``refs/remotes/<remote_ref_name>`` is present."""
    return _show_ref_verifies(repo_root, f"{GIT_REFS_REMOTES_PREFIX}{remote_ref_name}")


def _local_branch_ref_exists(repo_root: Path, ref_name: str) -> bool:
    """Answer whether a local branch exists, ignoring any ``origin/`` prefix."""
    origin_prefix = f"{GIT_ORIGIN}/"
    local_name = (
        ref_name[len(origin_prefix) :]
        if ref_name.startswith(origin_prefix)
        else ref_name
    )
    return _show_ref_verifies(repo_root, f"{GIT_REFS_HEADS_PREFIX}{local_name}")


def _remote_exists(repo_root: Path, remote_name: str) -> bool:
    completed = subprocess.run(
        [GIT_COMMAND, GIT_REMOTE],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return False
    all_remotes = {each.strip() for each in completed.stdout.splitlines() if each.strip()}
    return remote_name in all_remotes


def main() -> int:
    """CLI entry: execute or dry-run a verified plan.

    Returns:
        Process exit code (0 success, 1 failure).

    Raises:
        Does not raise; failures print JSON error and return 1.
    """
    try:
        parsed_arguments = _parse_arguments()
        if not parsed_arguments.plan:
            raise ValueError(ERROR_PLAN_PATH_REQUIRED)
        plan_payload = load_plan(Path(parsed_arguments.plan))
        if PLAN_KEY_TITLE not in plan_payload or PLAN_KEY_PR_NUMBER not in plan_payload:
            raise ValueError(ERROR_EXECUTE_FAILED % ERROR_PLAN_MISSING_PR_IDENTITY)
        repo_root = resolve_repo_root(Path(parsed_arguments.repo_path).resolve())
        is_create_prs = parsed_arguments.create_prs and not parsed_arguments.dry_run
        should_push = (
            parsed_arguments.push or parsed_arguments.create_prs
        ) and not parsed_arguments.dry_run
        if parsed_arguments.supersede_source is None:
            is_supersede = is_create_prs
        else:
            is_supersede = bool(parsed_arguments.supersede_source)
        execution_payload = execute_plan(
            plan_payload=plan_payload,
            repo_root=repo_root,
            is_dry_run=parsed_arguments.dry_run,
            should_create_prs=is_create_prs,
            should_push=should_push,
            should_supersede=is_supersede,
            should_allow_optional_split=parsed_arguments.allow_optional_split,
        )
        indent = JSON_INDENT_SPACES if parsed_arguments.pretty else None
        print(json.dumps(execution_payload, indent=indent))
        return EXIT_CODE_SUCCESS
    except SliceExecutionError as partial_error:
        indent = JSON_INDENT_SPACES if PRETTY_FLAG in sys.argv else None
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


def _parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Execute an approved split-pr plan")
    parser.add_argument("--plan", required=True, help="Path to approved plan JSON")
    parser.add_argument(
        "--repo-path",
        default=".",
        help="Path inside the target git repository",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned steps without git mutations",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Push created branches to origin",
    )
    parser.add_argument(
        "--create-prs",
        action="store_true",
        help="Open draft stacked PRs; implies --push",
    )
    parser.add_argument(
        "--allow-optional-split",
        action="store_true",
        help="Execute even when the plan says the split is optional",
    )
    parser.add_argument(
        "--supersede-source",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Comment on and close source_pr_number after a full multi-slice draft "
            "stack lands (default: on when --create-prs)"
        ),
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
