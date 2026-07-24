"""Behavioral tests for the staged_test_running parts module."""

import subprocess
from pathlib import Path

from code_rules_gate_parts import git_file_sets, staged_test_running


def _git(repository_root: Path, *arguments: str) -> None:
    subprocess.run(
        ["git", *arguments],
        cwd=str(repository_root),
        check=True,
        capture_output=True,
        env=git_file_sets.repository_environment(),
    )


def _init_repository(repository_root: Path) -> None:
    _git(repository_root, "init", "--initial-branch=main")
    _git(repository_root, "config", "user.email", "test@example.com")
    _git(repository_root, "config", "user.name", "Test")
    _git(repository_root, "config", "commit.gpgsign", "false")
    (repository_root / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repository_root, "add", "-A")
    _git(repository_root, "commit", "-m", "seed")


def _write_and_stage(repository_root: Path, relative_path: str, file_text: str) -> Path:
    file_path = repository_root / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(file_text, encoding="utf-8")
    _git(repository_root, "add", "--", relative_path)
    return file_path


def _repository_with_root_pytest_config(tmp_path: Path) -> Path:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)
    (repository_root / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    return repository_root


def test_run_staged_test_files_returns_zero_when_nothing_staged(tmp_path: Path) -> None:
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    _init_repository(repository_root)

    assert staged_test_running.run_staged_test_files(repository_root) == 0


def test_batched_pytest_arguments_splits_over_the_budget() -> None:
    all_batches = staged_test_running._batched_pytest_arguments(["aaaa", "bbbb", "cccc"], 10)
    assert all_batches == [["aaaa", "bbbb"], ["cccc"]]


def test_batched_pytest_arguments_keeps_oversized_argument_in_its_own_batch() -> None:
    all_batches = staged_test_running._batched_pytest_arguments(["wide_argument"], 4)
    assert all_batches == [["wide_argument"]]


def test_pytest_target_paths_drops_conftest_and_keeps_real_tests() -> None:
    all_staged_paths = [
        Path("pkg_a/conftest.py"),
        Path("pkg_b/conftest.py"),
        Path("pkg_a/test_alpha.py"),
        Path("pkg_b/tests/conftest.py"),
    ]

    all_targets = staged_test_running._pytest_target_paths(all_staged_paths)

    assert all_targets == [Path("pkg_a/test_alpha.py")]


def test_run_staged_test_files_returns_zero_when_only_multiple_confests_staged(
    tmp_path: Path,
) -> None:
    repository_root = _repository_with_root_pytest_config(tmp_path)
    _write_and_stage(repository_root, "pkg_a/conftest.py", "import pytest\n")
    _write_and_stage(repository_root, "pkg_b/conftest.py", "import pytest\n")
    _write_and_stage(
        repository_root, "pkg_c/tests/conftest.py", "import pytest\n"
    )

    assert staged_test_running.run_staged_test_files(repository_root) == 0


def test_run_staged_test_files_passes_when_confests_stage_with_passing_test(
    tmp_path: Path,
) -> None:
    repository_root = _repository_with_root_pytest_config(tmp_path)
    _write_and_stage(repository_root, "pkg_a/conftest.py", "import pytest\n")
    _write_and_stage(repository_root, "pkg_b/conftest.py", "import pytest\n")
    _write_and_stage(
        repository_root,
        "pkg_a/test_alpha.py",
        "def test_alpha_passes() -> None:\n    assert True\n",
    )

    assert staged_test_running.run_staged_test_files(repository_root) == 0


def test_run_staged_test_files_fails_when_real_test_fails_alongside_confests(
    tmp_path: Path,
) -> None:
    repository_root = _repository_with_root_pytest_config(tmp_path)
    _write_and_stage(repository_root, "pkg_a/conftest.py", "import pytest\n")
    _write_and_stage(repository_root, "pkg_b/conftest.py", "import pytest\n")
    _write_and_stage(
        repository_root,
        "pkg_a/test_alpha.py",
        "def test_alpha_fails() -> None:\n    assert False\n",
    )

    assert staged_test_running.run_staged_test_files(repository_root) != 0
