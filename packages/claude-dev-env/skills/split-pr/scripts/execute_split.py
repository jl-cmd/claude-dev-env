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
)
from split_pr_scripts_constants.config.execute_constants import (
    DEFAULT_COMMIT_MESSAGE_TEMPLATE,
    ERROR_BRANCH_EXISTS,
    ERROR_CHECKOUT_FILES,
    ERROR_COMMIT_FAILED,
    ERROR_DIRTY_TREE,
    ERROR_EMPTY_SLICE_AFTER_CHECKOUT,
    ERROR_EXECUTE_FAILED,
    ERROR_PR_CREATE_FAILED,
    ERROR_PUSH_FAILED,
    ERROR_REPO_NOT_GIT,
    GH_BASE,
    GH_BODY_FILE,
    GH_COMMAND,
    GH_CREATE,
    GH_DRAFT,
    GH_HEAD,
    GH_PR,
    GH_REPO_FLAG,
    GH_TITLE,
    GIT_ADD,
    GIT_ADD_PATHSPEC,
    GIT_BRANCH,
    GIT_CHECKOUT,
    GIT_CHECKOUT_FORCE_CREATE,
    GIT_COMMAND,
    GIT_COMMIT,
    GIT_FETCH,
    GIT_MESSAGE_FLAG,
    GIT_ORIGIN,
    GIT_PORCELAIN,
    GIT_PUSH,
    GIT_REFS_HEADS_PREFIX,
    GIT_REFS_REMOTES_PREFIX,
    GIT_REV_PARSE,
    GIT_SET_UPSTREAM,
    GIT_SHOW_TOPLEVEL,
    GIT_STATUS,
    JSON_INDENT_SPACES,
    MARKDOWN_BODY_SUFFIX,
    PAYLOAD_KEY_CREATED,
    PAYLOAD_KEY_DRY_RUN,
    PAYLOAD_KEY_FAILED_SLICE,
    PAYLOAD_KEY_PARTIAL,
    PAYLOAD_KEY_PR_URLS,
)
from split_pr_scripts_constants.config.plan_constants import (
    ERROR_PLAN_PATH_REQUIRED,
    PLAN_KEY_BASE_REF,
    PLAN_KEY_PR_NUMBER,
    PLAN_KEY_PROPOSED_SLICES,
    PLAN_KEY_REPO,
    PLAN_KEY_SOURCE_BRANCH,
    PLAN_KEY_TITLE,
    SLICE_KEY_BASE,
    SLICE_KEY_BRANCH,
    SLICE_KEY_FILES,
    SLICE_KEY_INDEX,
    SLICE_KEY_STORY,
    SLICE_KEY_TITLE,
    VERIFY_KEY_IS_VALID,
)
from verify_plan import load_plan, verify_plan

JsonObject = dict[str, object]


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
            {
                "index": each_slice.get(SLICE_KEY_INDEX),
                "branch": each_slice.get(SLICE_KEY_BRANCH),
                "base": each_slice.get(SLICE_KEY_BASE),
                "source_branch": source_branch,
                "files": list(each_slice.get(SLICE_KEY_FILES) or []),
                "title": each_slice.get(SLICE_KEY_TITLE),
                "story": each_slice.get(SLICE_KEY_STORY),
            }
        )
    return all_steps


def execute_plan(
    plan_payload: JsonObject,
    repo_root: Path,
    is_dry_run: bool,
    should_create_prs: bool,
    should_push: bool,
) -> JsonObject:
    """Run the split (or dry-run) against repo_root.

    Args:
        plan_payload: Verified plan.
        repo_root: Git toplevel.
        is_dry_run: When True, only describe steps.
        should_create_prs: When True, open draft PRs after push.
        should_push: When True, push branches to origin.

    Returns:
        Result payload with created slice metadata.

    Raises:
        RuntimeError: On dirty tree, git, or gh failures (partial payload JSON).
        ValueError: When the plan fails coverage verification.
    """
    report = verify_plan(plan_payload)
    if not report[VERIFY_KEY_IS_VALID]:
        raise ValueError(ERROR_EXECUTE_FAILED % report)
    if is_dry_run:
        return {
            PAYLOAD_KEY_DRY_RUN: True,
            PAYLOAD_KEY_CREATED: build_dry_run_steps(plan_payload),
            PAYLOAD_KEY_PR_URLS: [],
        }
    if is_working_tree_dirty(repo_root):
        raise RuntimeError(ERROR_DIRTY_TREE)
    return _execute_slices(
        plan_payload=plan_payload,
        repo_root=repo_root,
        should_create_prs=should_create_prs,
        should_push=should_push,
    )


def _execute_slices(
    plan_payload: JsonObject,
    repo_root: Path,
    should_create_prs: bool,
    should_push: bool,
) -> JsonObject:
    source_branch = str(plan_payload[PLAN_KEY_SOURCE_BRANCH])
    base_ref = str(plan_payload[PLAN_KEY_BASE_REF])
    pr_number = int(plan_payload[PLAN_KEY_PR_NUMBER])
    repo = plan_payload.get(PLAN_KEY_REPO)
    if should_push or _remote_exists(repo_root, GIT_ORIGIN):
        _run_git(
            [GIT_FETCH, GIT_ORIGIN, base_ref, source_branch],
            repo_root,
            is_check=should_push,
        )
    all_created: list[JsonObject] = []
    all_pr_urls: list[str] = []
    starting_branch = _current_branch(repo_root)
    try:
        for each_slice in plan_payload[PLAN_KEY_PROPOSED_SLICES]:
            if not isinstance(each_slice, dict):
                continue
            try:
                created = _execute_one_slice(
                    slice_record=each_slice,
                    repo_root=repo_root,
                    source_branch=source_branch,
                    pr_number=pr_number,
                    should_push=should_push,
                    should_create_prs=should_create_prs,
                    repo=repo if isinstance(repo, str) else None,
                )
            except RuntimeError as slice_error:
                partial_payload: JsonObject = {
                    PAYLOAD_KEY_DRY_RUN: False,
                    PAYLOAD_KEY_CREATED: all_created,
                    PAYLOAD_KEY_PR_URLS: all_pr_urls,
                    PAYLOAD_KEY_ERROR: str(slice_error),
                    PAYLOAD_KEY_FAILED_SLICE: each_slice.get(SLICE_KEY_BRANCH),
                    PAYLOAD_KEY_PARTIAL: True,
                }
                raise RuntimeError(json.dumps(partial_payload)) from slice_error
            all_created.append(created)
            pr_url = created.get("pr_url")
            if pr_url:
                all_pr_urls.append(str(pr_url))
    finally:
        _run_git([GIT_CHECKOUT, starting_branch], repo_root, is_check=False)
    return {
        PAYLOAD_KEY_DRY_RUN: False,
        PAYLOAD_KEY_CREATED: all_created,
        PAYLOAD_KEY_PR_URLS: all_pr_urls,
        PAYLOAD_KEY_PARTIAL: False,
    }


def _execute_one_slice(
    slice_record: JsonObject,
    repo_root: Path,
    source_branch: str,
    pr_number: int,
    should_push: bool,
    should_create_prs: bool,
    repo: str | None,
) -> JsonObject:
    branch_name = str(slice_record[SLICE_KEY_BRANCH])
    base_name = str(slice_record[SLICE_KEY_BASE])
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
    _checkout_source_files(repo_root, source_branch, all_files)
    _run_git([GIT_ADD, GIT_ADD_PATHSPEC, *all_files], repo_root)
    if not is_working_tree_dirty(repo_root):
        raise RuntimeError(ERROR_EMPTY_SLICE_AFTER_CHECKOUT % branch_name)
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
    return {
        "index": slice_record.get(SLICE_KEY_INDEX),
        "branch": branch_name,
        "base": base_name,
        "files": all_files,
        "title": title,
        "pr_url": pr_url,
    }


def _resolve_base_ref(repo_root: Path, base_name: str, source_branch: str) -> str:
    if base_name.startswith(f"{GIT_ORIGIN}/") or base_name == source_branch:
        return base_name
    origin_candidate = f"{GIT_ORIGIN}/{base_name}"
    if _ref_exists(repo_root, origin_candidate) and not _branch_exists(
        repo_root, base_name
    ):
        return origin_candidate
    return base_name


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
        f"## Split source\n\nExcised from PR #{pr_number} via `/split-pr`.\n\n"
        f"## Dependencies\n\nBase branch: `{base_name}`. Merge earlier slices first.\n\n"
        "## Testing\n\n"
        "File-partitioned from the source PR. Full project CI on this slice alone "
        "is not claimed by `/split-pr` unless verified separately.\n"
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
    completed = subprocess.run(
        all_command,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
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


def _current_branch(repo_root: Path) -> str:
    completed = _run_git([GIT_REV_PARSE, "--abbrev-ref", "HEAD"], repo_root)
    return completed.stdout.strip()


def _branch_exists(repo_root: Path, branch_name: str) -> bool:
    completed = subprocess.run(
        [GIT_COMMAND, GIT_BRANCH, "--list", branch_name],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(completed.stdout.strip())


def _ref_exists(repo_root: Path, ref_name: str) -> bool:
    remote_ref = f"{GIT_REFS_REMOTES_PREFIX}{ref_name}"
    completed = subprocess.run(
        [GIT_COMMAND, "show-ref", "--verify", "--quiet", remote_ref],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode == 0:
        return True
    local_ref = f"{GIT_REFS_HEADS_PREFIX}{ref_name}"
    completed_local = subprocess.run(
        [GIT_COMMAND, "show-ref", "--verify", "--quiet", local_ref],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return completed_local.returncode == 0


def _remote_exists(repo_root: Path, remote_name: str) -> bool:
    completed = subprocess.run(
        [GIT_COMMAND, "remote"],
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
        if PLAN_KEY_TITLE not in plan_payload and PLAN_KEY_PR_NUMBER not in plan_payload:
            raise ValueError(ERROR_EXECUTE_FAILED % "plan missing pr identity")
        repo_root = resolve_repo_root(Path(parsed_arguments.repo_path).resolve())
        execution_payload = execute_plan(
            plan_payload=plan_payload,
            repo_root=repo_root,
            is_dry_run=parsed_arguments.dry_run,
            should_create_prs=parsed_arguments.create_prs and not parsed_arguments.dry_run,
            should_push=parsed_arguments.push and not parsed_arguments.dry_run,
        )
        indent = JSON_INDENT_SPACES if parsed_arguments.pretty else None
        print(json.dumps(execution_payload, indent=indent))
        return EXIT_CODE_SUCCESS
    except (ValueError, RuntimeError, OSError) as error:
        message = str(error)
        indent = JSON_INDENT_SPACES if "--pretty" in sys.argv else None
        try:
            parsed_partial: object = json.loads(message)
        except json.JSONDecodeError:
            parsed_partial = None
        if isinstance(parsed_partial, dict) and parsed_partial.get(PAYLOAD_KEY_PARTIAL):
            print(json.dumps(parsed_partial, indent=indent))
        else:
            print(json.dumps({PAYLOAD_KEY_ERROR: message}))
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
        help="Open draft stacked PRs after push",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    return parser.parse_args()


if __name__ == "__main__":
    sys.exit(main())
