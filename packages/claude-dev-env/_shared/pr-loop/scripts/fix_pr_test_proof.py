"""Require a fix pull request to carry a test that fails on its base and passes on its head.

::

    title "docs: ..."                               -> pass, nothing to prove
    title "fix: ..." changing only docs or .github  -> pass, nothing to prove
    title "fix: ..." with no changed Python test    -> fail
    changed test passes on head, fails on base      -> pass
    changed test passes on both                     -> fail

The base run reuses the regression gate's detached worktree: the changed test
files are copied onto the base checkout, which runs them with import isolation.
Python tests only.
"""

import argparse
import sys
from pathlib import Path

from code_rules_gate_parts import staged_test_regression, staged_test_running
from code_rules_gate_parts.git_file_sets import paths_from_git_diff
from code_rules_gate_parts.wrapper_plumb_check import is_test_path
from pr_loop_shared_constants.fix_pr_test_proof_constants import (
    ALL_PRODUCTION_CODE_SUFFIXES,
    CI_CONFIG_DIRECTORY_NAME,
    FAILED_EXIT_CODE,
    FIX_TITLE_PATTERN,
    HEAD_FAILURE_MESSAGE,
    NO_BASE_FAILURE_MESSAGE,
    NO_CHANGED_TEST_MESSAGE,
    NO_PRODUCTION_CHANGE_MESSAGE,
    NOT_A_FIX_MESSAGE,
    PASSED_EXIT_CODE,
    PROVEN_MESSAGE,
    WORKTREE_FAILED_MESSAGE,
)


def _parse_arguments(all_arguments: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="fix_pr_test_proof")
    parser.add_argument("--title", required=True)
    parser.add_argument("--base", dest="base_revision", required=True)
    parser.add_argument("--repository-root", default=".")
    return parser.parse_args(all_arguments)


def is_production_code_path(file_path: Path, repository_root: Path) -> bool:
    """Return whether a changed path is production code a fix must prove.

    Args:
        file_path: An absolute changed path.
        repository_root: The repository the path belongs to.

    Returns:
        True for a code file outside the test patterns and outside ``.github``.
    """
    relative_path = file_path.relative_to(repository_root)
    if relative_path.parts and relative_path.parts[0] == CI_CONFIG_DIRECTORY_NAME:
        return False
    if file_path.suffix not in ALL_PRODUCTION_CODE_SUFFIXES:
        return False
    return not is_test_path(relative_path.as_posix())


def _changed_python_tests(all_changed_paths: list[Path]) -> list[Path]:
    return [
        each_path
        for each_path in all_changed_paths
        if each_path.suffix == ".py"
        and is_test_path(each_path.as_posix())
        and each_path.is_file()
    ]


def _proof_exit_code(
    all_changed_tests: list[Path], repository_root: Path, base_revision: str
) -> int:
    all_targets = staged_test_running._pytest_target_paths(all_changed_tests)
    all_tests_by_root = staged_test_running._group_staged_tests_by_root(
        all_targets, repository_root
    )
    head_outcomes, base_outcomes = (
        staged_test_regression.working_tree_and_revision_outcomes(
            all_tests_by_root, repository_root, base_revision, all_changed_tests
        )
    )
    for each_group_root, each_outcome in sorted(head_outcomes.items()):
        if each_outcome.exit_code != 0:
            sys.stderr.write(HEAD_FAILURE_MESSAGE.format(group_root=each_group_root) + "\n")
            return FAILED_EXIT_CODE
    if base_outcomes is None:
        sys.stderr.write(WORKTREE_FAILED_MESSAGE.format(revision=base_revision) + "\n")
        return FAILED_EXIT_CODE
    base_failure_count = sum(
        len(each_outcome.failing_identities) for each_outcome in base_outcomes.values()
    )
    if base_failure_count == 0:
        sys.stderr.write(NO_BASE_FAILURE_MESSAGE.format(revision=base_revision) + "\n")
        return FAILED_EXIT_CODE
    sys.stdout.write(PROVEN_MESSAGE.format(count=base_failure_count) + "\n")
    return PASSED_EXIT_CODE


def main(all_arguments: list[str]) -> int:
    """Run the fix test-proof check.

    Args:
        all_arguments: Command arguments naming the title, base, and repository.

    Returns:
        0 when the pull request passes, 1 when a fix lacks its proof test.
    """
    parsed_arguments = _parse_arguments(all_arguments)
    if not FIX_TITLE_PATTERN.match(parsed_arguments.title):
        sys.stdout.write(NOT_A_FIX_MESSAGE + "\n")
        return PASSED_EXIT_CODE
    repository_root = Path(parsed_arguments.repository_root).resolve()
    all_changed_paths = paths_from_git_diff(repository_root, parsed_arguments.base_revision)
    if not any(
        is_production_code_path(each_path, repository_root) for each_path in all_changed_paths
    ):
        sys.stdout.write(NO_PRODUCTION_CHANGE_MESSAGE + "\n")
        return PASSED_EXIT_CODE
    all_changed_tests = _changed_python_tests(all_changed_paths)
    if not all_changed_tests:
        sys.stderr.write(NO_CHANGED_TEST_MESSAGE + "\n")
        return FAILED_EXIT_CODE
    return _proof_exit_code(all_changed_tests, repository_root, parsed_arguments.base_revision)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
