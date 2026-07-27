"""Behavioral tests for the staged_test_running parts module."""

from pathlib import Path

import pytest

from code_rules_gate_parts import staged_test_running
from code_rules_gate_parts.tests._repo_test_helpers import repository_root_without_pytest_config


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


def _refuse_to_resolve(monkeypatch: pytest.MonkeyPatch, refused_path: Path) -> None:
    """Make ``Path.resolve`` raise ``OSError`` for *refused_path* and nothing else.

    Stands in for a staged file the filesystem accepts as a file yet refuses to
    resolve, such as a broken junction or a path the user may not traverse.
    """
    original_resolve = Path.resolve

    def _resolve_unless_refused(each_path: Path, strict: bool = False) -> Path:
        if each_path == refused_path:
            raise OSError("resolve refused")
        return original_resolve(each_path, strict=strict)

    monkeypatch.setattr(Path, "resolve", _resolve_unless_refused)


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


def test_group_staged_tests_by_root_splits_config_less_top_level_directories(
    tmp_path: Path,
) -> None:
    repository_root = repository_root_without_pytest_config(tmp_path)
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
    repository_root = repository_root_without_pytest_config(tmp_path)
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
    repository_root = repository_root_without_pytest_config(tmp_path)
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
    repository_root = repository_root_without_pytest_config(tmp_path)
    root_level_test_path = _write_test_file(repository_root, "test_at_repository_root.py")

    all_tests_by_root = staged_test_running._group_staged_tests_by_root(
        [root_level_test_path], repository_root
    )

    assert all_tests_by_root == {repository_root.resolve(): [root_level_test_path]}


def test_group_staged_tests_by_root_falls_back_to_the_root_when_resolve_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository_root = repository_root_without_pytest_config(tmp_path)
    unresolvable_test_path = _write_test_file(
        repository_root, "alpha_package/tests/test_alpha.py"
    )
    _refuse_to_resolve(monkeypatch, unresolvable_test_path)

    all_tests_by_root = staged_test_running._group_staged_tests_by_root(
        [unresolvable_test_path], repository_root
    )

    assert all_tests_by_root == {repository_root.resolve(): [unresolvable_test_path]}
