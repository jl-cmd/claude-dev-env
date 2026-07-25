"""Resolve the test files whose freshness can satisfy the gate for a module.

Given a production file, builds every path a matching test could live at: the
flat sibling ``test_<stem>.py``, the package-mirroring candidates under an
ancestor ``tests`` directory, and the ``test_<stem>_*.py`` split test family
that any module's own stem anchors. A ``code_rules_*`` module additionally
draws on the shared ``code_rules_enforcer`` split family.
"""

from pathlib import Path

from tdd_enforcer_parts.config.tdd_enforcer_constants import (
    ALL_JAVASCRIPT_TEST_EXTENSIONS,
    ALL_REPO_BOUNDARY_SENTINELS,
    PARENT_WALK_LIMIT,
    PYTHON_SOURCE_EXTENSION,
    SPLIT_MODULE_STEM_PREFIX,
    SPLIT_TEST_FAMILY_ANCHOR_STEM,
    SPLIT_TEST_FAMILY_GLOB_SUFFIX,
    TEST_FILE_NAME_PREFIX,
)


def _tests_directory_name() -> str:
    return "tests"


def _parent_walk_limit() -> int:
    return PARENT_WALK_LIMIT


def _repo_boundary_sentinels() -> frozenset[str]:
    return ALL_REPO_BOUNDARY_SENTINELS


def _split_module_stem_prefix() -> str:
    return SPLIT_MODULE_STEM_PREFIX


def _split_test_family_anchor_stem() -> str:
    return SPLIT_TEST_FAMILY_ANCHOR_STEM


def _split_test_family_glob_for(stem: str) -> str:
    return f"{TEST_FILE_NAME_PREFIX}{stem}{SPLIT_TEST_FAMILY_GLOB_SUFFIX}"


def _javascript_test_extensions() -> frozenset[str]:
    return ALL_JAVASCRIPT_TEST_EXTENSIONS


def _is_repo_boundary(candidate_directory: Path) -> bool:
    for each_sentinel in _repo_boundary_sentinels():
        if (candidate_directory / each_sentinel).exists():
            return True
    return False


def _ancestor_tests_directories(start_directory: Path) -> list[tuple[Path, Path]]:
    """Collect each ancestor's sibling ``tests`` directory up to the repo root.

    Args:
        start_directory: Directory of the production file under edit.

    Returns:
        Ordered ``(ancestor, tests_directory)`` pairs, nearer ancestors first.
    """
    all_pairs: list[tuple[Path, Path]] = []
    current_directory = start_directory
    remaining_steps = _parent_walk_limit()
    while remaining_steps > 0:
        remaining_steps -= 1
        sibling_tests = current_directory / _tests_directory_name()
        if sibling_tests.is_dir():
            all_pairs.append((current_directory, sibling_tests))
        if _is_repo_boundary(current_directory):
            break
        if current_directory.parent == current_directory:
            break
        current_directory = current_directory.parent
    return all_pairs


def _split_family_globs(stem: str) -> list[str]:
    """List the split-family globs a module's own stem earns it.

    ::

        invoke_code_review  -> test_invoke_code_review_*.py
        code_rules_comments -> test_code_rules_comments_*.py
                               test_code_rules_enforcer_*.py

    Every glob stays anchored to a stem, so an unrelated neighbour's tests
    never count. The anchor family is added only for the shared prefix.

    Args:
        stem: Stem of the production module under edit.

    Returns:
        Glob patterns to match against the module's own directory.
    """
    all_globs = [_split_test_family_glob_for(stem)]
    anchor_glob = _split_test_family_glob_for(_split_test_family_anchor_stem())
    if stem.startswith(_split_module_stem_prefix()) and anchor_glob not in all_globs:
        all_globs.append(anchor_glob)
    return all_globs


def _split_family_candidates(directory: Path, stem: str) -> list[Path]:
    all_matches: list[Path] = []
    for each_glob in _split_family_globs(stem):
        all_matches.extend(sorted(directory.glob(each_glob)))
    return list(dict.fromkeys(all_matches))


def _flat_stem_candidates(directory: Path, stem: str) -> list[Path]:
    return [directory / f"test_{stem}.py", directory / f"{stem}_test.py"]


def _mirrored_nested_candidates(
    directory: Path, ancestor: Path, tests_directory: Path, stem: str
) -> list[Path]:
    all_candidates: list[Path] = []
    nested_directory = tests_directory
    for each_relative_part in directory.relative_to(ancestor).parts:
        nested_directory = nested_directory / each_relative_part
        all_candidates.append(nested_directory / f"test_{stem}.py")
    return all_candidates


def _nested_tests_candidates(directory: Path, stem: str) -> list[Path]:
    all_candidates: list[Path] = []
    for each_ancestor, each_tests_directory in _ancestor_tests_directories(directory):
        all_candidates.append(each_tests_directory / f"test_{stem}.py")
        all_candidates.extend(
            _mirrored_nested_candidates(directory, each_ancestor, each_tests_directory, stem)
        )
    return all_candidates


def _python_candidate_test_paths(directory: Path, stem: str) -> list[Path]:
    all_candidates = _flat_stem_candidates(directory, stem)
    all_candidates.extend(_nested_tests_candidates(directory, stem))
    all_candidates.extend(_split_family_candidates(directory, stem))
    return all_candidates


def _javascript_candidate_test_paths(directory: Path, stem: str, extension: str) -> list[Path]:
    return [directory / f"{stem}.test{extension}", directory / f"{stem}.spec{extension}"]


def candidate_test_paths_for(production_path: Path) -> list[Path]:
    """Return the test files that can satisfy the gate for a production file.

    ::

        pkg/orders.py -> pkg/test_orders.py, pkg/orders_test.py,
                         pkg/tests/test_orders.py (and package mirrors)

    A Python module also gains the ``test_<stem>_*.py`` split family found
    beside it, and a ``code_rules_*`` module gains the shared
    ``code_rules_enforcer`` family too. Plain stem-derived candidates always
    come first.

    Args:
        production_path: The production source file being written or edited.

    Returns:
        Ordered candidate test paths; stem-derived siblings precede any
        split-family additions.
    """
    directory = production_path.parent
    stem = production_path.stem
    extension = production_path.suffix.lower()
    if extension == PYTHON_SOURCE_EXTENSION:
        return _python_candidate_test_paths(directory, stem)
    if extension in _javascript_test_extensions():
        return _javascript_candidate_test_paths(directory, stem, extension)
    return []
