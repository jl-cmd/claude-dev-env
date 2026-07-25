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
    FAMILY_TREE_SKIP_CREATE_PRS_OFF,
    PAYLOAD_KEY_CREATED,
    PAYLOAD_KEY_DRY_RUN,
    PAYLOAD_KEY_FAMILY_TREE,
    PAYLOAD_KEY_SKIPPED,
    PAYLOAD_KEY_SKIP_REASON,
    PAYLOAD_KEY_STACK_LABELS,
    PAYLOAD_KEY_SUPERSEDE,
    STACK_LABELS_SKIP_CREATE_PRS_OFF,
    SUPERSEDE_SKIP_DISABLED,
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
    # Fixture repos must not run the host's pre-commit code_rules_gate on
    # synthetic Python modules (those hooks expect real package layout).
    resolved_arguments = list(all_arguments)
    if resolved_arguments and resolved_arguments[0] == "commit":
        resolved_arguments = ["commit", "--no-verify", *resolved_arguments[1:]]
    subprocess.run(
        ["git", *resolved_arguments],
        cwd=str(working_directory),
        check=True,
        capture_output=True,
        text=True,
    )


def _disable_repo_hooks(repo: Path) -> None:
    """Point core.hooksPath at an empty dir so fixture commits skip host hooks."""
    hooks_directory = repo / ".split-pr-empty-hooks"
    hooks_directory.mkdir(exist_ok=True)
    run_git(
        ["config", "core.hooksPath", hooks_directory.resolve().as_posix()],
        repo,
    )


def make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run_git(["init", "-b", "main"], repo)
    run_git(["config", "user.name", GIT_USER_NAME], repo)
    run_git(["config", "user.email", GIT_USER_EMAIL], repo)
    _disable_repo_hooks(repo)
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
        should_supersede=False,
        should_check_collection=True,
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
        should_supersede=False,
        should_check_collection=True,
    )
    assert execution_payload[PAYLOAD_KEY_DRY_RUN] is False
    assert len(execution_payload[PAYLOAD_KEY_CREATED]) == 2
    supersede_payload = execution_payload[PAYLOAD_KEY_SUPERSEDE]
    assert isinstance(supersede_payload, dict)
    assert supersede_payload[PAYLOAD_KEY_SKIPPED] is True
    assert supersede_payload[PAYLOAD_KEY_SKIP_REASON] == SUPERSEDE_SKIP_DISABLED
    family_tree_payload = execution_payload[PAYLOAD_KEY_FAMILY_TREE]
    assert isinstance(family_tree_payload, dict)
    assert family_tree_payload[PAYLOAD_KEY_SKIPPED] is True
    assert (
        family_tree_payload[PAYLOAD_KEY_SKIP_REASON] == FAMILY_TREE_SKIP_CREATE_PRS_OFF
    )
    stack_labels_payload = execution_payload[PAYLOAD_KEY_STACK_LABELS]
    assert isinstance(stack_labels_payload, dict)
    assert stack_labels_payload[PAYLOAD_KEY_SKIPPED] is True
    assert (
        stack_labels_payload[PAYLOAD_KEY_SKIP_REASON]
        == STACK_LABELS_SKIP_CREATE_PRS_OFF
    )

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
            should_supersede=False,
            should_check_collection=True,
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


def _make_python_wrong_side_repo(tmp_path: Path) -> Path:
    """Feature branch where tests import a module that lands only later."""
    repo = tmp_path / "py-repo"
    repo.mkdir()
    run_git(["init", "-b", "main"], repo)
    run_git(["config", "user.name", GIT_USER_NAME], repo)
    run_git(["config", "user.email", GIT_USER_EMAIL], repo)
    _disable_repo_hooks(repo)
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    run_git(["add", "README.md"], repo)
    run_git(["commit", "-m", "initial"], repo)

    run_git(["checkout", "-b", "feature/big"], repo)
    package_directory = repo / "pkg"
    package_directory.mkdir()
    (package_directory / "__init__.py").write_text("", encoding="utf-8")
    (package_directory / "definitions.py").write_text(
        "def build_token() -> str:\n"
        "    return 'ready'\n",
        encoding="utf-8",
    )
    tests_directory = package_directory / "tests"
    tests_directory.mkdir()
    (tests_directory / "__init__.py").write_text("", encoding="utf-8")
    (tests_directory / "test_definitions.py").write_text(
        "from pkg.definitions import build_token\n\n"
        "def test_build_token_returns_ready() -> None:\n"
        "    assert build_token().startswith('re')\n",
        encoding="utf-8",
    )
    run_git(["add", "."], repo)
    run_git(["commit", "-m", "feature dump"], repo)
    run_git(["checkout", "main"], repo)
    return repo


def _python_wrong_side_plan() -> dict:
    return {
        PLAN_KEY_PR_NUMBER: 1041,
        PLAN_KEY_TITLE: "Backwards stack",
        PLAN_KEY_BASE_REF: "main",
        PLAN_KEY_SOURCE_BRANCH: "feature/big",
        PLAN_KEY_ALL_FILES: [
            {FILE_KEY_PATH: "pkg/tests/test_definitions.py"},
            {FILE_KEY_PATH: "pkg/definitions.py"},
            {FILE_KEY_PATH: "pkg/__init__.py"},
            {FILE_KEY_PATH: "pkg/tests/__init__.py"},
        ],
        PLAN_KEY_PROPOSED_SLICES: [
            {
                SLICE_KEY_INDEX: 1,
                SLICE_KEY_BRANCH: "split/1041/01-tests",
                SLICE_KEY_BASE: "main",
                SLICE_KEY_TITLE: "feat: tests first",
                SLICE_KEY_STORY: "tests before definitions",
                SLICE_KEY_FILES: [
                    "pkg/tests/test_definitions.py",
                    "pkg/tests/__init__.py",
                    "pkg/__init__.py",
                ],
            },
            {
                SLICE_KEY_INDEX: 2,
                SLICE_KEY_BRANCH: "split/1041/02-definitions",
                SLICE_KEY_BASE: "split/1041/01-tests",
                SLICE_KEY_TITLE: "feat: definitions later",
                SLICE_KEY_STORY: "definitions after tests",
                SLICE_KEY_FILES: ["pkg/definitions.py"],
            },
        ],
    }


def test_execute_plan_fails_when_definitions_are_on_wrong_side(
    tmp_path: Path,
) -> None:
    repo = _make_python_wrong_side_repo(tmp_path)
    with pytest.raises(RuntimeError) as raised:
        execute_plan(
            plan_payload=_python_wrong_side_plan(),
            repo_root=repo,
            is_dry_run=False,
            should_create_prs=False,
            should_push=False,
            should_supersede=False,
            should_check_collection=True,
        )
    payload = json.loads(str(raised.value))
    assert payload["partial"] is True
    assert payload["failed_slice"] == "split/1041/01-tests"
    assert "wrong side of the cut" in payload["error"]
    assert payload[PAYLOAD_KEY_CREATED] == []


def test_execute_plan_passes_when_definitions_precede_tests(tmp_path: Path) -> None:
    repo = _make_python_wrong_side_repo(tmp_path)
    plan_payload = _python_wrong_side_plan()
    plan_payload[PLAN_KEY_PROPOSED_SLICES] = [
        {
            SLICE_KEY_INDEX: 1,
            SLICE_KEY_BRANCH: "split/1041/01-definitions",
            SLICE_KEY_BASE: "main",
            SLICE_KEY_TITLE: "feat: definitions first",
            SLICE_KEY_STORY: "definitions before tests",
            SLICE_KEY_FILES: [
                "pkg/definitions.py",
                "pkg/__init__.py",
            ],
        },
        {
            SLICE_KEY_INDEX: 2,
            SLICE_KEY_BRANCH: "split/1041/02-tests",
            SLICE_KEY_BASE: "split/1041/01-definitions",
            SLICE_KEY_TITLE: "feat: tests second",
            SLICE_KEY_STORY: "tests after definitions",
            SLICE_KEY_FILES: [
                "pkg/tests/test_definitions.py",
                "pkg/tests/__init__.py",
            ],
        },
    ]
    execution_payload = execute_plan(
        plan_payload=plan_payload,
        repo_root=repo,
        is_dry_run=False,
        should_create_prs=False,
        should_push=False,
        should_supersede=False,
        should_check_collection=True,
    )
    assert execution_payload[PAYLOAD_KEY_DRY_RUN] is False
    assert len(execution_payload[PAYLOAD_KEY_CREATED]) == 2
    second_slice = execution_payload[PAYLOAD_KEY_CREATED][1]
    assert second_slice["collection"]["passed"] is True
    assert second_slice["collection"]["checked"] is True
