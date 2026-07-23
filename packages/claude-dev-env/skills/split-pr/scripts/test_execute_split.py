"""Behavioral tests for execute_split dry-run and real local slice creation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIRECTORY = Path(__file__).resolve().parent
if str(SCRIPTS_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIRECTORY))

from execute_split import (  # noqa: E402
    build_dry_run_steps,
    execute_plan,
    is_working_tree_dirty,
    resolve_repo_root,
)
from split_pr_scripts_constants.config.execute_constants import (  # noqa: E402
    PAYLOAD_KEY_CREATED,
    PAYLOAD_KEY_DRY_RUN,
)
from split_pr_scripts_constants.config.plan_constants import (  # noqa: E402
    FILE_KEY_PATH,
    PLAN_KEY_ALL_FILES,
    PLAN_KEY_BASE_REF,
    PLAN_KEY_PR_NUMBER,
    PLAN_KEY_PROPOSED_SLICES,
    PLAN_KEY_SOURCE_BRANCH,
    PLAN_KEY_TITLE,
    SLICE_KEY_BASE,
    SLICE_KEY_BRANCH,
    SLICE_KEY_FILES,
    SLICE_KEY_INDEX,
    SLICE_KEY_STORY,
    SLICE_KEY_TITLE,
)

GIT_USER_NAME = "split-pr-test"
GIT_USER_EMAIL = "split-pr-test@example.com"


def run_git(all_arguments: list[str], working_directory: Path) -> None:
    subprocess.run(
        ["git", *all_arguments],
        cwd=str(working_directory),
        check=True,
        capture_output=True,
        text=True,
    )


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(["init", "-b", "main"], repo)
    run_git(["config", "user.name", GIT_USER_NAME], repo)
    run_git(["config", "user.email", GIT_USER_EMAIL], repo)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    run_git(["add", "README.md"], repo)
    run_git(["commit", "-m", "initial"], repo)

    run_git(["checkout", "-b", "feature/big"], repo)
    (repo / "prisma").mkdir()
    (repo / "prisma" / "schema.prisma").write_text("model N {}\n", encoding="utf-8")
    (repo / "src").mkdir()
    (repo / "src" / "api").mkdir(parents=True)
    (repo / "src" / "api" / "n.ts").write_text("export const n = 1\n", encoding="utf-8")
    run_git(["add", "."], repo)
    run_git(["commit", "-m", "feature dump"], repo)
    run_git(["checkout", "main"], repo)
    return repo


def sample_plan() -> dict:
    return {
        PLAN_KEY_PR_NUMBER: 99,
        PLAN_KEY_TITLE: "Big feature",
        PLAN_KEY_BASE_REF: "main",
        PLAN_KEY_SOURCE_BRANCH: "feature/big",
        PLAN_KEY_ALL_FILES: [
            {FILE_KEY_PATH: "prisma/schema.prisma"},
            {FILE_KEY_PATH: "src/api/n.ts"},
        ],
        PLAN_KEY_PROPOSED_SLICES: [
            {
                SLICE_KEY_INDEX: 1,
                SLICE_KEY_BRANCH: "split/99/01-database",
                SLICE_KEY_BASE: "main",
                SLICE_KEY_TITLE: "feat: database",
                SLICE_KEY_STORY: "data foundation",
                SLICE_KEY_FILES: ["prisma/schema.prisma"],
            },
            {
                SLICE_KEY_INDEX: 2,
                SLICE_KEY_BRANCH: "split/99/02-backend",
                SLICE_KEY_BASE: "split/99/01-database",
                SLICE_KEY_TITLE: "feat: backend",
                SLICE_KEY_STORY: "api layer",
                SLICE_KEY_FILES: ["src/api/n.ts"],
            },
        ],
    }


def test_build_dry_run_steps_lists_slices() -> None:
    all_steps = build_dry_run_steps(sample_plan())
    assert len(all_steps) == 2
    assert all_steps[0]["branch"] == "split/99/01-database"


def test_execute_plan_dry_run() -> None:
    execution_payload = execute_plan(
        plan_payload=sample_plan(),
        repo_root=Path("."),
        is_dry_run=True,
        should_create_prs=False,
        should_push=False,
    )
    assert execution_payload[PAYLOAD_KEY_DRY_RUN] is True
    assert len(execution_payload[PAYLOAD_KEY_CREATED]) == 2


def test_execute_plan_creates_local_branches(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    execution_payload = execute_plan(
        plan_payload=sample_plan(),
        repo_root=repo,
        is_dry_run=False,
        should_create_prs=False,
        should_push=False,
    )
    assert execution_payload[PAYLOAD_KEY_DRY_RUN] is False
    assert len(execution_payload[PAYLOAD_KEY_CREATED]) == 2

    run_git(["checkout", "split/99/01-database"], repo)
    assert (repo / "prisma" / "schema.prisma").is_file()
    assert not (repo / "src" / "api" / "n.ts").exists()

    run_git(["checkout", "split/99/02-backend"], repo)
    assert (repo / "prisma" / "schema.prisma").is_file()
    assert (repo / "src" / "api" / "n.ts").is_file()


def test_execute_plan_partial_failure_includes_created(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    plan_payload = sample_plan()
    plan_payload[PLAN_KEY_PROPOSED_SLICES][1][SLICE_KEY_FILES] = ["ghost/missing.ts"]
    plan_payload[PLAN_KEY_ALL_FILES] = [
        {FILE_KEY_PATH: "prisma/schema.prisma"},
        {FILE_KEY_PATH: "ghost/missing.ts"},
    ]
    with pytest.raises(RuntimeError) as raised:
        execute_plan(
            plan_payload=plan_payload,
            repo_root=repo,
            is_dry_run=False,
            should_create_prs=False,
            should_push=False,
        )
    payload = json.loads(str(raised.value))
    assert payload["partial"] is True
    assert len(payload[PAYLOAD_KEY_CREATED]) == 1
    assert payload[PAYLOAD_KEY_CREATED][0]["branch"] == "split/99/01-database"


def test_resolve_repo_root_and_dirty_flag(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    assert resolve_repo_root(repo) == repo.resolve()
    assert is_working_tree_dirty(repo) is False
    (repo / "dirty.txt").write_text("x\n", encoding="utf-8")
    assert is_working_tree_dirty(repo) is True
