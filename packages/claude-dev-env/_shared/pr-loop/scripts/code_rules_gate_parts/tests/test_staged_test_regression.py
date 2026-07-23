"""Behavioral tests for the staged_test_regression parts module.

Every test drives a real git repository and a real pytest subprocess — no
mocked git state, no mocked pytest run — the same shape the live commit gate
exercises.
"""

from pathlib import Path

from code_rules_gate_parts import staged_test_regression
from code_rules_gate_parts.tests._repo_test_helpers import (
    init_repository,
    repository_with_root_pytest_config,
    run_git,
    write_and_stage,
    write_commit_and_stage_change,
)


def test_pre_existing_failure_does_not_block_an_unrelated_staged_change(
    tmp_path: Path,
) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_commit_and_stage_change(
        repository_root,
        "pkg_a/test_alpha.py",
        (
            "def test_already_fails() -> None:\n    assert False\n"
            "def test_passes() -> None:\n    assert True\n"
        ),
        (
            "def test_already_fails() -> None:\n    assert False\n"
            "def test_passes() -> None:\n    assert 1 == 1\n"
        ),
    )

    assert staged_test_regression.run_staged_test_files(repository_root) == 0


def test_staged_change_that_newly_breaks_a_passing_test_blocks(tmp_path: Path) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_commit_and_stage_change(
        repository_root,
        "pkg_a/test_alpha.py",
        "def test_alpha_passes() -> None:\n    assert True\n",
        "def test_alpha_passes() -> None:\n    assert False\n",
    )

    assert staged_test_regression.run_staged_test_files(repository_root) != 0


def test_brand_new_failing_test_with_no_baseline_blocks(tmp_path: Path) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_and_stage(
        repository_root,
        "pkg_a/test_alpha.py",
        "def test_alpha_fails() -> None:\n    assert False\n",
    )

    assert staged_test_regression.run_staged_test_files(repository_root) != 0


def test_mixed_group_blocks_only_on_the_newly_broken_test(tmp_path: Path) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_commit_and_stage_change(
        repository_root,
        "pkg_a/test_alpha.py",
        (
            "def test_already_red() -> None:\n    assert False\n"
            "def test_stays_green() -> None:\n    assert True\n"
        ),
        (
            "def test_already_red() -> None:\n    assert False\n"
            "def test_stays_green() -> None:\n    assert False\n"
        ),
    )

    assert staged_test_regression.run_staged_test_files(repository_root) != 0


def test_regression_gate_restores_the_staged_index_after_running(tmp_path: Path) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_commit_and_stage_change(
        repository_root,
        "pkg_a/test_alpha.py",
        (
            "def test_already_fails() -> None:\n    assert False\n"
            "def test_passes() -> None:\n    assert True\n"
        ),
        (
            "def test_already_fails() -> None:\n    assert False\n"
            "def test_passes() -> None:\n    assert 1 == 1\n"
        ),
    )

    staged_test_regression.run_staged_test_files(repository_root)

    staged_content = run_git(
        repository_root, "show", ":pkg_a/test_alpha.py"
    ).stdout.decode("utf-8")
    assert "assert 1 == 1" in staged_content
    status = run_git(repository_root, "status", "--porcelain").stdout.decode("utf-8")
    assert "M  pkg_a/test_alpha.py" in status
    stash_list = run_git(repository_root, "stash", "list").stdout.decode("utf-8")
    assert stash_list == ""


def test_run_staged_test_files_returns_zero_when_nothing_staged(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    init_repository(repository_root)

    assert staged_test_regression.run_staged_test_files(repository_root) == 0


def test_run_staged_test_files_returns_zero_when_only_multiple_confests_staged(
    tmp_path: Path,
) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_and_stage(repository_root, "pkg_a/conftest.py", "import pytest\n")
    write_and_stage(repository_root, "pkg_b/conftest.py", "import pytest\n")
    write_and_stage(repository_root, "pkg_c/tests/conftest.py", "import pytest\n")

    assert staged_test_regression.run_staged_test_files(repository_root) == 0


def test_run_staged_test_files_passes_when_confests_stage_with_passing_test(
    tmp_path: Path,
) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_and_stage(repository_root, "pkg_a/conftest.py", "import pytest\n")
    write_and_stage(repository_root, "pkg_b/conftest.py", "import pytest\n")
    write_and_stage(
        repository_root,
        "pkg_a/test_alpha.py",
        "def test_alpha_passes() -> None:\n    assert True\n",
    )

    assert staged_test_regression.run_staged_test_files(repository_root) == 0


def test_run_staged_test_files_fails_when_real_test_fails_alongside_confests(
    tmp_path: Path,
) -> None:
    repository_root = repository_with_root_pytest_config(tmp_path)
    write_and_stage(repository_root, "pkg_a/conftest.py", "import pytest\n")
    write_and_stage(repository_root, "pkg_b/conftest.py", "import pytest\n")
    write_and_stage(
        repository_root,
        "pkg_a/test_alpha.py",
        "def test_alpha_fails() -> None:\n    assert False\n",
    )

    assert staged_test_regression.run_staged_test_files(repository_root) != 0


def test_no_head_baseline_blocks_on_any_staged_failure(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    run_git(repository_root, "init", "--initial-branch=main")
    run_git(repository_root, "config", "user.email", "test@example.com")
    run_git(repository_root, "config", "user.name", "Test")
    run_git(repository_root, "config", "commit.gpgsign", "false")
    write_and_stage(repository_root, "pytest.ini", "[pytest]\n")
    write_and_stage(
        repository_root,
        "test_alpha.py",
        "def test_alpha_fails() -> None:\n    assert False\n",
    )

    assert staged_test_regression.run_staged_test_files(repository_root) != 0
