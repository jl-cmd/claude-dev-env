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


def _existing_candidates_for(production_path: Path) -> list[Path]:
    """Return the candidate test paths that are present on disk.

    Args:
        production_path: The production source file the gate is resolving.

    Returns:
        Candidate paths from the production code path that exist as files.
    """
    all_candidates = candidate_paths.candidate_test_paths_for(production_path)
    return [each_candidate for each_candidate in all_candidates if each_candidate.is_file()]


def test_split_family_counts_for_a_module_outside_the_code_rules_prefix(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "invoke_code_review.py").write_text("", encoding="utf-8")
    chain_test = tmp_path / "test_invoke_code_review_chain.py"
    contract_test = tmp_path / "test_invoke_code_review_contract.py"
    chain_test.write_text("", encoding="utf-8")
    contract_test.write_text("", encoding="utf-8")

    all_found = _existing_candidates_for(tmp_path / "invoke_code_review.py")

    assert chain_test in all_found
    assert contract_test in all_found


def test_split_family_still_counts_for_a_code_rules_module(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "code_rules_docstrings.py").write_text("", encoding="utf-8")
    enforcer_family_test = tmp_path / "test_code_rules_enforcer_docstring_format.py"
    enforcer_family_test.write_text("", encoding="utf-8")

    all_found = _existing_candidates_for(tmp_path / "code_rules_docstrings.py")

    assert enforcer_family_test in all_found


def test_flat_stem_test_file_still_counts(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "orders.py").write_text("", encoding="utf-8")
    flat_test = tmp_path / "test_orders.py"
    flat_test.write_text("", encoding="utf-8")

    assert _existing_candidates_for(tmp_path / "orders.py") == [flat_test]


def test_module_without_any_tests_finds_nothing(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "orders.py").write_text("", encoding="utf-8")

    assert _existing_candidates_for(tmp_path / "orders.py") == []


def test_unrelated_neighbour_test_does_not_count(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "orders.py").write_text("", encoding="utf-8")
    (tmp_path / "test_billing_totals.py").write_text("", encoding="utf-8")

    assert _existing_candidates_for(tmp_path / "orders.py") == []


def test_ancestor_tests_directories_finds_sibling_tests(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "tests").mkdir()
    all_pairs = candidate_paths._ancestor_tests_directories(package)
    all_tests_directories = [each_tests_directory for _, each_tests_directory in all_pairs]
    assert package / "tests" in all_tests_directories
