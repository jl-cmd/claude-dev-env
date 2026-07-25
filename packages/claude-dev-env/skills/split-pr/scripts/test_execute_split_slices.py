"""Behavioral tests for execute_split against real temporary git repositories."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

import execute_split  # noqa: E402
from execute_split import (  # noqa: E402
    SliceExecutionError,
    _local_branch_ref_exists,
    _remote_ref_exists,
    _resolve_base_ref,
    build_dry_run_steps,
    execute_plan,
)
from split_pr_scripts_constants.config.analyze_constants import (  # noqa: E402
    PAYLOAD_KEY_ERROR,
    PLAN_THRESHOLD_NOTE_KEY,
)
from split_pr_scripts_constants.config.execute_constants import (  # noqa: E402
    PAYLOAD_KEY_CREATED,
    PAYLOAD_KEY_PARTIAL,
    PAYLOAD_KEY_RESTORE_ERROR,
    PAYLOAD_KEY_SKIPPED_SLICES,
    PAYLOAD_KEY_SUPERSEDE,
)
from split_pr_scripts_constants.config.plan_constants import (  # noqa: E402
    FILE_KEY_PATH,
    FILE_KEY_STATUS,
    FILE_STATUS_ADDED,
    FILE_STATUS_MODIFIED,
    FILE_STATUS_REMOVED,
    PLAN_KEY_ALL_FILES,
    PLAN_KEY_BASE_REF,
    PLAN_KEY_HEAD_SHA,
    PLAN_KEY_PR_NUMBER,
    PLAN_KEY_PROPOSED_SLICES,
    PLAN_KEY_SOURCE_BRANCH,
    PLAN_KEY_TITLE,
    SLICE_KEY_BASE,
    SLICE_KEY_BRANCH,
    SLICE_KEY_FILES,
    SLICE_KEY_INDEX,
    SLICE_KEY_SLUG,
    SLICE_KEY_STORY,
    SLICE_KEY_TITLE,
)

EXECUTE_SCRIPT_PATH = SCRIPTS_DIRECTORY / "execute_split.py"
GIT_USER_NAME = "split-pr-test"
GIT_USER_EMAIL = "split-pr-test@example.com"
MAIN_BRANCH_NAME = "main"
SOURCE_BRANCH_NAME = "feature/split-me"
KEEP_PATH = "src/services/keep.py"
GONE_PATH = "src/services/gone.py"
NEW_PATH = "src/services/new.py"
GUIDE_PATH = "docs/guide.md"
README_PATH = "README.md"
BACKEND_BRANCH = "split/123/01-backend"
EMPTY_BRANCH = "split/123/02-guide"
DOCS_BRANCH = "split/123/03-docs"
PR_NUMBER = 123
PLAN_FILE_NAME = "plan.json"
ORIGINAL_TEXT = "original\n"
UPDATED_TEXT = "updated\n"


def run_git(all_arguments: list[str], working_directory: Path) -> str:
    completed = subprocess.run(
        ["git", *all_arguments],
        cwd=str(working_directory),
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def write_file(repo_path: Path, relative_path: str, contents: str) -> None:
    target_path = repo_path / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(contents, encoding="utf-8")


def build_repository(workspace_path: Path) -> tuple[Path, Path]:
    """Return (origin_path, repo_path) with a main branch and a source branch."""
    origin_path = workspace_path / "origin.git"
    repo_path = workspace_path / "work"
    empty_hooks_path = workspace_path / "empty-hooks"
    empty_hooks_path.mkdir(parents=True, exist_ok=True)
    run_git(
        ["init", "--bare", f"--initial-branch={MAIN_BRANCH_NAME}", str(origin_path)],
        workspace_path,
    )
    run_git(["clone", str(origin_path), str(repo_path)], workspace_path)
    run_git(["config", "core.hooksPath", str(empty_hooks_path)], repo_path)
    run_git(["config", "user.name", GIT_USER_NAME], repo_path)
    run_git(["config", "user.email", GIT_USER_EMAIL], repo_path)
    run_git(["checkout", "-B", MAIN_BRANCH_NAME], repo_path)
    write_file(repo_path, KEEP_PATH, ORIGINAL_TEXT)
    write_file(repo_path, GONE_PATH, ORIGINAL_TEXT)
    write_file(repo_path, GUIDE_PATH, ORIGINAL_TEXT)
    write_file(repo_path, README_PATH, ORIGINAL_TEXT)
    run_git(["add", "--all"], repo_path)
    run_git(["commit", "-m", "seed"], repo_path)
    run_git(["push", "-u", "origin", MAIN_BRANCH_NAME], repo_path)
    run_git(["checkout", "-B", SOURCE_BRANCH_NAME], repo_path)
    write_file(repo_path, KEEP_PATH, UPDATED_TEXT)
    write_file(repo_path, NEW_PATH, UPDATED_TEXT)
    write_file(repo_path, README_PATH, UPDATED_TEXT)
    (repo_path / GONE_PATH).unlink()
    run_git(["add", "--all"], repo_path)
    run_git(["commit", "-m", "source work"], repo_path)
    run_git(["push", "-u", "origin", SOURCE_BRANCH_NAME], repo_path)
    run_git(["checkout", MAIN_BRANCH_NAME], repo_path)
    return origin_path, repo_path


def build_plan(repo_path: Path) -> dict[str, object]:
    head_sha = run_git(["rev-parse", SOURCE_BRANCH_NAME], repo_path)
    return {
        PLAN_KEY_PR_NUMBER: PR_NUMBER,
        PLAN_KEY_TITLE: "Add the bell",
        PLAN_KEY_BASE_REF: MAIN_BRANCH_NAME,
        PLAN_KEY_SOURCE_BRANCH: SOURCE_BRANCH_NAME,
        PLAN_KEY_HEAD_SHA: head_sha,
        PLAN_KEY_ALL_FILES: [
            {FILE_KEY_PATH: KEEP_PATH, FILE_KEY_STATUS: FILE_STATUS_MODIFIED},
            {FILE_KEY_PATH: NEW_PATH, FILE_KEY_STATUS: FILE_STATUS_ADDED},
            {FILE_KEY_PATH: GUIDE_PATH, FILE_KEY_STATUS: FILE_STATUS_MODIFIED},
            {FILE_KEY_PATH: README_PATH, FILE_KEY_STATUS: FILE_STATUS_MODIFIED},
            {FILE_KEY_PATH: GONE_PATH, FILE_KEY_STATUS: FILE_STATUS_REMOVED},
        ],
        PLAN_KEY_PROPOSED_SLICES: [
            {
                SLICE_KEY_INDEX: 1,
                SLICE_KEY_SLUG: "backend",
                SLICE_KEY_TITLE: "feat: bell backend",
                SLICE_KEY_STORY: "Implement backend services and API",
                SLICE_KEY_FILES: [KEEP_PATH, NEW_PATH],
                SLICE_KEY_BRANCH: BACKEND_BRANCH,
                SLICE_KEY_BASE: MAIN_BRANCH_NAME,
            },
            {
                SLICE_KEY_INDEX: 2,
                SLICE_KEY_SLUG: "guide",
                SLICE_KEY_TITLE: "feat: bell guide",
                SLICE_KEY_STORY: "Document the feature",
                SLICE_KEY_FILES: [GUIDE_PATH],
                SLICE_KEY_BRANCH: EMPTY_BRANCH,
                SLICE_KEY_BASE: BACKEND_BRANCH,
            },
            {
                SLICE_KEY_INDEX: 3,
                SLICE_KEY_SLUG: "docs",
                SLICE_KEY_TITLE: "feat: bell docs",
                SLICE_KEY_STORY: "Document the feature",
                SLICE_KEY_FILES: [README_PATH, GONE_PATH],
                SLICE_KEY_BRANCH: DOCS_BRANCH,
                SLICE_KEY_BASE: EMPTY_BRANCH,
            },
        ],
    }


def run_execute(repo_path: Path, plan_payload: dict[str, object]) -> dict[str, object]:
    return execute_plan(
        plan_payload=plan_payload,
        repo_root=repo_path,
        is_dry_run=False,
        should_create_prs=False,
        should_push=False,
        should_supersede=False,
        should_allow_optional_split=False,
    )


def test_a_stale_local_base_loses_to_the_remote_tracking_ref(tmp_path: Path) -> None:
    _, repo_path = build_repository(tmp_path)
    run_git(["checkout", MAIN_BRANCH_NAME], repo_path)
    write_file(repo_path, README_PATH, "remote only\n")
    run_git(["add", "--all"], repo_path)
    run_git(["commit", "-m", "remote main advance"], repo_path)
    run_git(["push", "origin", MAIN_BRANCH_NAME], repo_path)
    remote_main_sha = run_git(["rev-parse", MAIN_BRANCH_NAME], repo_path)
    run_git(["reset", "--hard", "HEAD~1"], repo_path)

    resolved_ref = _resolve_base_ref(repo_path, MAIN_BRANCH_NAME, SOURCE_BRANCH_NAME)

    assert resolved_ref == f"origin/{MAIN_BRANCH_NAME}"
    assert run_git(["rev-parse", resolved_ref], repo_path) == remote_main_sha


def test_the_local_branch_probe_ignores_an_origin_prefix(tmp_path: Path) -> None:
    _, repo_path = build_repository(tmp_path)

    assert _local_branch_ref_exists(repo_path, f"origin/{MAIN_BRANCH_NAME}") is True
    assert _remote_ref_exists(repo_path, f"origin/{MAIN_BRANCH_NAME}") is True
    assert _remote_ref_exists(repo_path, "origin/never-pushed") is False


def test_a_failed_fetch_stops_a_no_push_run(tmp_path: Path) -> None:
    _, repo_path = build_repository(tmp_path)
    run_git(["remote", "set-url", "origin", str(tmp_path / "missing.git")], repo_path)

    with pytest.raises(RuntimeError):
        run_execute(repo_path, build_plan(repo_path))

    assert not _local_branch_ref_exists(repo_path, BACKEND_BRANCH)


def test_an_empty_slice_is_skipped_and_the_stack_keeps_going(tmp_path: Path) -> None:
    _, repo_path = build_repository(tmp_path)

    execution_payload = run_execute(repo_path, build_plan(repo_path))

    all_skipped = execution_payload[PAYLOAD_KEY_SKIPPED_SLICES]
    all_created = execution_payload[PAYLOAD_KEY_CREATED]
    assert isinstance(all_skipped, list)
    assert isinstance(all_created, list)
    assert [each[SLICE_KEY_BRANCH] for each in all_skipped] == [EMPTY_BRANCH]
    assert [each[SLICE_KEY_BRANCH] for each in all_created] == [
        BACKEND_BRANCH,
        DOCS_BRANCH,
    ]
    assert all_created[1][SLICE_KEY_BASE] == BACKEND_BRANCH
    assert not _local_branch_ref_exists(repo_path, EMPTY_BRANCH)


def test_a_deleted_path_is_removed_inside_its_slice(tmp_path: Path) -> None:
    _, repo_path = build_repository(tmp_path)

    run_execute(repo_path, build_plan(repo_path))

    all_docs_paths = run_git(["ls-tree", "-r", "--name-only", DOCS_BRANCH], repo_path)
    all_main_paths = run_git(
        ["ls-tree", "-r", "--name-only", MAIN_BRANCH_NAME], repo_path
    )
    assert GONE_PATH in all_main_paths
    assert GONE_PATH not in all_docs_paths


def test_a_moved_source_head_aborts_before_any_branch_exists(tmp_path: Path) -> None:
    _, repo_path = build_repository(tmp_path)
    plan_payload = build_plan(repo_path)
    run_git(["checkout", SOURCE_BRANCH_NAME], repo_path)
    write_file(repo_path, "src/services/teammate.py", UPDATED_TEXT)
    run_git(["add", "--all"], repo_path)
    run_git(["commit", "-m", "teammate work"], repo_path)
    run_git(["push", "origin", SOURCE_BRANCH_NAME], repo_path)
    run_git(["checkout", MAIN_BRANCH_NAME], repo_path)

    with pytest.raises(RuntimeError) as raised:
        run_execute(repo_path, plan_payload)

    assert str(plan_payload[PLAN_KEY_HEAD_SHA]) in str(raised.value)
    assert not _local_branch_ref_exists(repo_path, BACKEND_BRANCH)


def test_a_failed_slice_restores_a_detached_head_and_clears_the_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, repo_path = build_repository(tmp_path)
    starting_sha = run_git(["rev-parse", "HEAD"], repo_path)
    run_git(["checkout", "--detach", starting_sha], repo_path)

    def fail_after_staging(*_arguments: object, **_keyword_arguments: object) -> None:
        raise RuntimeError("commit refused by policy")

    monkeypatch.setattr(execute_split, "_commit_slice", fail_after_staging)

    with pytest.raises(SliceExecutionError) as raised:
        run_execute(repo_path, build_plan(repo_path))

    assert raised.value.partial_payload[PAYLOAD_KEY_PARTIAL] is True
    assert raised.value.partial_payload[PAYLOAD_KEY_RESTORE_ERROR] is None
    assert run_git(["rev-parse", "HEAD"], repo_path) == starting_sha
    assert run_git(["status", "--porcelain"], repo_path) == ""


def test_dry_run_and_executed_records_share_one_key_shape(tmp_path: Path) -> None:
    _, repo_path = build_repository(tmp_path)
    plan_payload = build_plan(repo_path)

    all_dry_run_steps = build_dry_run_steps(plan_payload)
    execution_payload = run_execute(repo_path, plan_payload)

    all_created = execution_payload[PAYLOAD_KEY_CREATED]
    assert isinstance(all_created, list)
    assert set(all_dry_run_steps[0]) == set(all_created[0])


def test_an_optional_split_plan_needs_an_explicit_override(tmp_path: Path) -> None:
    _, repo_path = build_repository(tmp_path)
    plan_payload = build_plan(repo_path)
    plan_payload[PLAN_THRESHOLD_NOTE_KEY] = "parent already fits review budget"

    with pytest.raises(ValueError):
        run_execute(repo_path, plan_payload)

    execution_payload = execute_plan(
        plan_payload=plan_payload,
        repo_root=repo_path,
        is_dry_run=False,
        should_create_prs=False,
        should_push=False,
        should_supersede=False,
        should_allow_optional_split=True,
    )

    assert execution_payload[PAYLOAD_KEY_CREATED]


def test_a_branch_name_shaped_like_an_option_is_rejected(tmp_path: Path) -> None:
    _, repo_path = build_repository(tmp_path)
    plan_payload = build_plan(repo_path)
    all_slices = plan_payload[PLAN_KEY_PROPOSED_SLICES]
    assert isinstance(all_slices, list)
    all_slices[0][SLICE_KEY_BRANCH] = "--upload-pack=touch pwned"

    with pytest.raises(ValueError):
        run_execute(repo_path, plan_payload)


def test_a_supersede_value_error_keeps_the_created_slices(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, repo_path = build_repository(tmp_path)

    def raise_value_error(**_keyword_arguments: object) -> dict[str, object]:
        raise ValueError("gh emitted an unexpected payload")

    monkeypatch.setattr(execute_split, "supersede_source_pr", raise_value_error)

    execution_payload = execute_plan(
        plan_payload=build_plan(repo_path),
        repo_root=repo_path,
        is_dry_run=False,
        should_create_prs=False,
        should_push=False,
        should_supersede=True,
        should_allow_optional_split=False,
    )

    all_created = execution_payload[PAYLOAD_KEY_CREATED]
    supersede_payload = execution_payload[PAYLOAD_KEY_SUPERSEDE]
    assert isinstance(all_created, list)
    assert isinstance(supersede_payload, dict)
    assert len(all_created) == 2
    assert supersede_payload[PAYLOAD_KEY_ERROR]


def test_create_prs_pushes_the_branches_without_an_explicit_push_flag(
    tmp_path: Path,
) -> None:
    origin_path, repo_path = build_repository(tmp_path)
    plan_path = tmp_path / PLAN_FILE_NAME
    plan_path.write_text(json.dumps(build_plan(repo_path)), encoding="utf-8")

    subprocess.run(
        [
            sys.executable,
            str(EXECUTE_SCRIPT_PATH),
            "--plan",
            str(plan_path),
            "--repo-path",
            str(repo_path),
            "--create-prs",
            "--no-supersede-source",
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert BACKEND_BRANCH in run_git(["branch", "--list", BACKEND_BRANCH], origin_path)


def test_a_plan_without_a_pr_number_reports_a_json_error(tmp_path: Path) -> None:
    _, repo_path = build_repository(tmp_path)
    plan_payload = build_plan(repo_path)
    del plan_payload[PLAN_KEY_PR_NUMBER]
    plan_path = tmp_path / PLAN_FILE_NAME
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(EXECUTE_SCRIPT_PATH),
            "--plan",
            str(plan_path),
            "--repo-path",
            str(repo_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert PAYLOAD_KEY_ERROR in json.loads(completed.stdout)
    assert "Traceback" not in completed.stderr


def test_a_non_integer_pr_number_reports_a_json_error(tmp_path: Path) -> None:
    _, repo_path = build_repository(tmp_path)
    plan_payload = build_plan(repo_path)
    plan_payload[PLAN_KEY_PR_NUMBER] = {"unexpected": "object"}
    plan_path = tmp_path / PLAN_FILE_NAME
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            str(EXECUTE_SCRIPT_PATH),
            "--plan",
            str(plan_path),
            "--repo-path",
            str(repo_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert PAYLOAD_KEY_ERROR in json.loads(completed.stdout)
    assert "Traceback" not in completed.stderr


def test_the_draft_pr_body_file_is_removed_after_gh_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, repo_path = build_repository(tmp_path)
    all_body_paths: list[str] = []

    def fake_run(
        all_command: list[str],
        **keyword_arguments: object,
    ) -> subprocess.CompletedProcess[str]:
        if all_command and all_command[0] == "gh":
            all_body_paths.append(all_command[all_command.index("--body-file") + 1])
            return subprocess.CompletedProcess(all_command, 0, "https://pr/1", "")
        return original_run(all_command, **keyword_arguments)

    original_run = execute_split.subprocess.run
    monkeypatch.setattr(execute_split.subprocess, "run", fake_run)

    execute_plan(
        plan_payload=build_plan(repo_path),
        repo_root=repo_path,
        is_dry_run=False,
        should_create_prs=True,
        should_push=True,
        should_supersede=False,
        should_allow_optional_split=False,
    )

    assert all_body_paths
    for each_body_path in all_body_paths:
        assert not Path(each_body_path).exists()
