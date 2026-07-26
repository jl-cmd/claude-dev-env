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
    _parse_arguments,
    build_dry_run_steps,
    derive_split_depth_from_source_branch,
    execute_plan,
    guard_recursive_split_depth,
    is_working_tree_dirty,
    main,
    resolve_effective_split_depth,
    resolve_repo_root,
)
from split_pr_scripts_constants.config.analyze_constants import (  # noqa: E402
    EXIT_CODE_FAILURE,
    PAYLOAD_KEY_ERROR,
)
from split_pr_scripts_constants.config.execute_constants import (  # noqa: E402
    GENERATED_SLICE_BRANCH_DEPTH,
    MAXIMUM_EXECUTABLE_SPLIT_DEPTH,
    PAYLOAD_KEY_CREATED,
    PAYLOAD_KEY_DRY_RUN,
    PAYLOAD_KEY_SKIPPED,
    PAYLOAD_KEY_SKIP_REASON,
    PAYLOAD_KEY_SUPERSEDE,
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
        should_supersede=False,
        recursion_depth=0,
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
        recursion_depth=0,
    )
    assert execution_payload[PAYLOAD_KEY_DRY_RUN] is False
    assert len(execution_payload[PAYLOAD_KEY_CREATED]) == 2
    supersede_payload = execution_payload[PAYLOAD_KEY_SUPERSEDE]
    assert isinstance(supersede_payload, dict)
    assert supersede_payload[PAYLOAD_KEY_SKIPPED] is True
    assert supersede_payload[PAYLOAD_KEY_SKIP_REASON] == SUPERSEDE_SKIP_DISABLED

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
            recursion_depth=0,
        )
    payload = json.loads(str(raised.value))
    assert payload["partial"] is True
    assert len(payload[PAYLOAD_KEY_CREATED]) == 1
    assert payload[PAYLOAD_KEY_CREATED][0]["branch"] == "split/99/01-database"


def slice_source_plan() -> dict:
    plan_payload = sample_plan()
    plan_payload[PLAN_KEY_SOURCE_BRANCH] = "split/377/05-split-further"
    return plan_payload


@pytest.mark.parametrize(
    ("source_branch", "expected_depth"),
    [
        ("feature/big", 0),
        ("main", 0),
        ("cleanup/478-depth-guard", 0),
        ("split/377/05-split-further", GENERATED_SLICE_BRANCH_DEPTH),
        ("split/99/01-database", GENERATED_SLICE_BRANCH_DEPTH),
        ("split/377", GENERATED_SLICE_BRANCH_DEPTH),
        ("split", GENERATED_SLICE_BRANCH_DEPTH),
    ],
)
def test_derive_split_depth_from_source_branch_reads_generated_slice_shape(
    source_branch: str,
    expected_depth: int,
) -> None:
    assert derive_split_depth_from_source_branch(source_branch) == expected_depth


def test_resolve_effective_split_depth_keeps_the_higher_derived_depth() -> None:
    assert resolve_effective_split_depth(slice_source_plan(), 0) == (
        GENERATED_SLICE_BRANCH_DEPTH
    )


def test_resolve_effective_split_depth_keeps_a_higher_reported_depth() -> None:
    reported_depth = GENERATED_SLICE_BRANCH_DEPTH + 3
    assert resolve_effective_split_depth(sample_plan(), reported_depth) == (
        reported_depth
    )


def test_resolve_effective_split_depth_rejects_a_negative_reported_depth() -> None:
    with pytest.raises(ValueError) as raised:
        resolve_effective_split_depth(sample_plan(), -5)
    assert "-5" in str(raised.value)


def test_guard_recursive_split_depth_allows_pass_zero() -> None:
    guard_recursive_split_depth(sample_plan(), MAXIMUM_EXECUTABLE_SPLIT_DEPTH)


def test_guard_recursive_split_depth_rejects_depth_past_the_bound() -> None:
    with pytest.raises(ValueError) as raised:
        guard_recursive_split_depth(
            sample_plan(), MAXIMUM_EXECUTABLE_SPLIT_DEPTH + 1
        )
    assert str(MAXIMUM_EXECUTABLE_SPLIT_DEPTH) in str(raised.value)


def test_guard_blocks_a_generated_slice_source_with_no_reported_depth() -> None:
    with pytest.raises(ValueError) as raised:
        guard_recursive_split_depth(slice_source_plan(), 0)
    assert str(GENERATED_SLICE_BRANCH_DEPTH) in str(raised.value)


def is_depth_executable(candidate_depth: int) -> bool:
    try:
        guard_recursive_split_depth(sample_plan(), candidate_depth)
    except ValueError:
        return False
    return True


def test_exactly_one_generation_of_children_is_permitted() -> None:
    all_executable_depths = [
        each_depth for each_depth in range(5) if is_depth_executable(each_depth)
    ]
    assert all_executable_depths == [0]


def test_execute_plan_stops_when_recursion_depth_passes_the_bound(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    with pytest.raises(ValueError):
        execute_plan(
            plan_payload=sample_plan(),
            repo_root=repo,
            is_dry_run=False,
            should_create_prs=False,
            should_push=False,
            should_supersede=False,
            recursion_depth=MAXIMUM_EXECUTABLE_SPLIT_DEPTH + 1,
        )
    all_branch_lines = subprocess.run(
        ["git", "branch", "--list", "split/99/*"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert all_branch_lines == ""


def test_parse_arguments_defaults_recursion_depth_to_pass_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["execute_split.py", "--plan", "plan.json", "--push", "--create-prs", "--pretty"],
    )
    parsed_arguments = _parse_arguments()
    assert parsed_arguments.recursion_depth == 0
    assert parsed_arguments.push is True
    assert parsed_arguments.create_prs is True


def test_parse_arguments_reads_an_explicit_recursion_depth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        sys,
        "argv",
        ["execute_split.py", "--plan", "plan.json", "--recursion-depth", "3"],
    )
    assert _parse_arguments().recursion_depth == 3


def write_plan_file(tmp_path: Path, plan_payload: dict) -> Path:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan_payload), encoding="utf-8")
    return plan_path


def test_main_refuses_a_generated_slice_source_on_the_canonical_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = make_repo(tmp_path)
    plan_path = write_plan_file(tmp_path, slice_source_plan())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "execute_split.py",
            "--plan",
            str(plan_path),
            "--repo-path",
            str(repo),
            "--push",
            "--create-prs",
            "--pretty",
        ],
    )
    assert main() == EXIT_CODE_FAILURE
    reported_payload = json.loads(capsys.readouterr().out)
    assert str(GENERATED_SLICE_BRANCH_DEPTH) in reported_payload[PAYLOAD_KEY_ERROR]


def test_main_rejects_a_negative_recursion_depth(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = make_repo(tmp_path)
    plan_path = write_plan_file(tmp_path, sample_plan())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "execute_split.py",
            "--plan",
            str(plan_path),
            "--repo-path",
            str(repo),
            "--recursion-depth",
            "-5",
        ],
    )
    assert main() == EXIT_CODE_FAILURE
    reported_payload = json.loads(capsys.readouterr().out)
    assert "-5" in reported_payload[PAYLOAD_KEY_ERROR]


def test_canonical_phase_four_command_refuses_a_generated_slice_source(
    tmp_path: Path,
) -> None:
    repo = make_repo(tmp_path)
    plan_path = write_plan_file(tmp_path, slice_source_plan())
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIRECTORY / "execute_split.py"),
            "--plan",
            str(plan_path),
            "--push",
            "--create-prs",
            "--pretty",
        ],
        cwd=str(repo),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == EXIT_CODE_FAILURE
    assert str(GENERATED_SLICE_BRANCH_DEPTH) in json.loads(completed.stdout)[
        PAYLOAD_KEY_ERROR
    ]
    all_branch_lines = subprocess.run(
        ["git", "branch", "--list", "split/*"],
        cwd=str(repo),
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert all_branch_lines == ""


def test_resolve_repo_root_and_dirty_flag(tmp_path: Path) -> None:
    repo = make_repo(tmp_path)
    assert resolve_repo_root(repo) == repo.resolve()
    assert is_working_tree_dirty(repo) is False
    (repo / "dirty.txt").write_text("x\n", encoding="utf-8")
    assert is_working_tree_dirty(repo) is True
