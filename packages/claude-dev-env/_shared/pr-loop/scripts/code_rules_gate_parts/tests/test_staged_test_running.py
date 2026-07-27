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


def _repository_root_without_pytest_config(tmp_path: Path) -> Path:
    """Return a fresh repository-root directory holding no pytest configuration."""
    repository_root = tmp_path / "repo"
    repository_root.mkdir()
    return repository_root


def _write_pytest_config(directory: Path) -> None:
    """Write a minimal ``pytest.ini`` into *directory*, creating it when absent."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")


def _write_test_file(repository_root: Path, relative_path: str) -> Path:
    """Write a trivially passing test module at *relative_path* and return its path."""
    file_path = repository_root / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        "def test_placeholder() -> None:\n    assert True\n", encoding="utf-8"
    )
    return file_path


def _stage_package_owning_a_bare_config(
    repository_root: Path, package_name: str, marker_value: str
) -> None:
    """Stage a config-less top-level package whose tests import a bare ``config``.

    Two such packages staged together reproduce the measured collision: one
    pytest session binds ``config`` to whichever package imports first, so the
    other package's test reads the wrong marker.
    """
    _write_and_stage(
        repository_root,
        f"{package_name}/config/__init__.py",
        f'PACKAGE_MARKER = "{marker_value}"\n',
    )
    _write_and_stage(
        repository_root,
        f"{package_name}/test_{package_name}.py",
        "from config import PACKAGE_MARKER\n\n\n"
        f"def test_{package_name}_reads_its_own_config() -> None:\n"
        f'    assert PACKAGE_MARKER == "{marker_value}"\n',
    )


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


def test_group_staged_tests_by_root_splits_config_less_top_level_directories(
    tmp_path: Path,
) -> None:
    repository_root = _repository_root_without_pytest_config(tmp_path)
    alpha_test_path = _write_test_file(repository_root, "alpha_package/tests/test_alpha.py")
    beta_test_path = _write_test_file(repository_root, "beta_package/tests/test_beta.py")

    all_tests_by_root = staged_test_running._group_staged_tests_by_root(
        [alpha_test_path, beta_test_path], repository_root
    )

    assert all_tests_by_root == {
        (repository_root / "alpha_package").resolve(): [alpha_test_path],
        (repository_root / "beta_package").resolve(): [beta_test_path],
    }


def test_group_staged_tests_by_root_places_every_input_in_exactly_one_group(
    tmp_path: Path,
) -> None:
    repository_root = _repository_root_without_pytest_config(tmp_path)
    _write_pytest_config(repository_root / "configured_package")
    all_staged_test_paths = [
        _write_test_file(repository_root, "configured_package/suite/test_configured.py"),
        _write_test_file(repository_root, "alpha_package/tests/test_alpha.py"),
        _write_test_file(repository_root, "alpha_package/tests/test_second_alpha.py"),
        _write_test_file(repository_root, "beta_package/test_beta.py"),
        _write_test_file(repository_root, "test_at_repository_root.py"),
    ]

    all_tests_by_root = staged_test_running._group_staged_tests_by_root(
        all_staged_test_paths, repository_root
    )

    all_grouped_test_paths = [
        each_path for each_group in all_tests_by_root.values() for each_path in each_group
    ]
    assert sorted(all_grouped_test_paths) == sorted(all_staged_test_paths)


def test_group_staged_tests_by_root_groups_at_the_config_owning_ancestor(
    tmp_path: Path,
) -> None:
    repository_root = _repository_root_without_pytest_config(tmp_path)
    configured_package_root = repository_root / "configured_package"
    _write_pytest_config(configured_package_root)
    nested_test_path = _write_test_file(
        repository_root, "configured_package/suite/test_configured.py"
    )

    all_tests_by_root = staged_test_running._group_staged_tests_by_root(
        [nested_test_path], repository_root
    )

    assert all_tests_by_root == {configured_package_root.resolve(): [nested_test_path]}


def test_group_staged_tests_by_root_keeps_a_repository_root_file_at_the_root(
    tmp_path: Path,
) -> None:
    repository_root = _repository_root_without_pytest_config(tmp_path)
    root_level_test_path = _write_test_file(repository_root, "test_at_repository_root.py")

    all_tests_by_root = staged_test_running._group_staged_tests_by_root(
        [root_level_test_path], repository_root
    )

    assert all_tests_by_root == {repository_root.resolve(): [root_level_test_path]}


def test_run_staged_test_files_passes_when_config_less_packages_share_a_module_name(
    tmp_path: Path,
) -> None:
    repository_root = _repository_root_without_pytest_config(tmp_path)
    _init_repository(repository_root)
    _stage_package_owning_a_bare_config(repository_root, "alpha_package", "alpha")
    _stage_package_owning_a_bare_config(repository_root, "beta_package", "beta")

    assert staged_test_running.run_staged_test_files(repository_root) == 0
