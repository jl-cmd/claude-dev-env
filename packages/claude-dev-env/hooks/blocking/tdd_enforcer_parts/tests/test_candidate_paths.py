"""Behavioral tests for the candidate_paths parts module."""

from pathlib import Path

from tdd_enforcer_parts import candidate_paths


def test_candidate_paths_offers_flat_stem_candidates_first(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    all_candidates = candidate_paths.candidate_test_paths_for(tmp_path / "orders.py")
    assert all_candidates[0] == tmp_path / "test_orders.py"
    assert all_candidates[1] == tmp_path / "orders_test.py"


def test_candidate_paths_returns_empty_for_unknown_extension(tmp_path: Path) -> None:
    assert candidate_paths.candidate_test_paths_for(tmp_path / "data.rs") == []


def test_candidate_paths_offers_javascript_test_siblings(tmp_path: Path) -> None:
    all_candidates = candidate_paths.candidate_test_paths_for(tmp_path / "Button.tsx")
    assert tmp_path / "Button.test.tsx" in all_candidates


def test_ancestor_tests_directories_finds_sibling_tests(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "tests").mkdir()
    all_pairs = candidate_paths._ancestor_tests_directories(package)
    all_tests_directories = [each_tests_directory for _, each_tests_directory in all_pairs]
    assert package / "tests" in all_tests_directories
