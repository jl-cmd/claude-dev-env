"""Require a fix pull request to carry a test that fails on its base and passes on its head.

::

    title "docs: ..."                               -> pass, nothing to prove
    title "fix: ..." changing only docs or .github  -> pass, nothing to prove
    title "fix: ..." with no changed Python test    -> fail
    title "fix: ..." with no changed Python or Node test -> fail
    changed test passes on head, fails on base      -> pass
    changed test passes on both                     -> fail
    any changed test fails on head                  -> fail

Python tests reuse the regression gate's detached worktree: the changed test
files are copied onto the base checkout, which runs them with import isolation.
Node tests (``*.test.mjs``, ``*.test.js``, ``*.test.cjs``) run through
``node --test`` on the head, then on a detached base checkout that holds a copy
of the changed test files. The fix is proven when at least one language's
changed tests fail on the base.
"""

import argparse
import shutil
import subprocess
import sys
import tempfile
from enum import Enum
from pathlib import Path

from code_rules_gate_parts import staged_test_regression, staged_test_running
from code_rules_gate_parts.git_file_sets import paths_from_git_diff
from code_rules_gate_parts.wrapper_plumb_check import is_test_path
from pr_loop_shared_constants.fix_pr_test_proof_constants import (
    ALL_NODE_TEST_COMMAND,
    ALL_NODE_TEST_SUFFIXES,
    ALL_PRODUCTION_CODE_SUFFIXES,
    CI_CONFIG_DIRECTORY_NAME,
    FAILED_EXIT_CODE,
    FIX_TITLE_PATTERN,
    HEAD_FAILURE_MESSAGE,
    NO_BASE_FAILURE_MESSAGE,
    NO_CHANGED_TEST_MESSAGE,
    NO_PRODUCTION_CHANGE_MESSAGE,
    NODE_BASE_WORKTREE_DIRECTORY_NAME,
    NODE_BASE_WORKTREE_TEMP_DIRECTORY_PREFIX,
    NOT_A_FIX_MESSAGE,
    PASSED_EXIT_CODE,
    PROVEN_MESSAGE,
    WORKTREE_FAILED_MESSAGE,
)


class ProofVerdict(Enum):
    """The result of running one language's changed tests on the head and the base."""

    HEAD_FAILED = "head_failed"
    BASE_UNAVAILABLE = "base_unavailable"
    PASSES_ON_BASE = "passes_on_base"
    PROVEN = "proven"


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


def _changed_node_tests(all_changed_paths: list[Path]) -> list[Path]:
    return [
        each_path
        for each_path in all_changed_paths
        if each_path.name.endswith(ALL_NODE_TEST_SUFFIXES) and each_path.is_file()
    ]


def _python_proof_verdict(
    all_changed_tests: list[Path], repository_root: Path, base_revision: str
) -> ProofVerdict:
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
            return ProofVerdict.HEAD_FAILED
    if base_outcomes is None:
        sys.stderr.write(WORKTREE_FAILED_MESSAGE.format(revision=base_revision) + "\n")
        return ProofVerdict.BASE_UNAVAILABLE
    base_failure_count = sum(
        len(each_outcome.failing_identities) for each_outcome in base_outcomes.values()
    )
    if base_failure_count == 0:
        return ProofVerdict.PASSES_ON_BASE
    sys.stdout.write(PROVEN_MESSAGE.format(count=base_failure_count) + "\n")
    return ProofVerdict.PROVEN


def _node_tests_pass(working_directory: Path, all_relative_tests: list[Path]) -> bool:
    node_run = subprocess.run(
        [*ALL_NODE_TEST_COMMAND, *(each_path.as_posix() for each_path in all_relative_tests)],
        cwd=working_directory,
        capture_output=True,
        text=True,
        check=False,
    )
    return node_run.returncode == 0


def _copy_tests_onto(
    base_worktree: Path, repository_root: Path, all_relative_tests: list[Path]
) -> None:
    for each_relative_test in all_relative_tests:
        base_test_path = base_worktree / each_relative_test
        base_test_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repository_root / each_relative_test, base_test_path)


def _node_proof_verdict(
    all_changed_tests: list[Path], repository_root: Path, base_revision: str
) -> ProofVerdict:
    all_relative_tests = [each_path.relative_to(repository_root) for each_path in all_changed_tests]
    if not _node_tests_pass(repository_root, all_relative_tests):
        sys.stderr.write(HEAD_FAILURE_MESSAGE.format(group_root=repository_root) + "\n")
        return ProofVerdict.HEAD_FAILED
    with tempfile.TemporaryDirectory(
        prefix=NODE_BASE_WORKTREE_TEMP_DIRECTORY_PREFIX, ignore_cleanup_errors=True
    ) as base_parent_text:
        base_worktree = Path(base_parent_text) / NODE_BASE_WORKTREE_DIRECTORY_NAME
        if not staged_test_regression._add_baseline_worktree(
            repository_root, base_worktree, base_revision
        ):
            sys.stderr.write(WORKTREE_FAILED_MESSAGE.format(revision=base_revision) + "\n")
            return ProofVerdict.BASE_UNAVAILABLE
        try:
            _copy_tests_onto(base_worktree, repository_root, all_relative_tests)
            passes_on_base = _node_tests_pass(base_worktree, all_relative_tests)
        finally:
            staged_test_regression._remove_baseline_worktree(repository_root, base_worktree)
    if passes_on_base:
        return ProofVerdict.PASSES_ON_BASE
    sys.stdout.write(PROVEN_MESSAGE.format(count=len(all_relative_tests)) + "\n")
    return ProofVerdict.PROVEN


def _proof_exit_code(
    all_verdicts: list[ProofVerdict], base_revision: str
) -> int:
    if any(
        each_verdict in (ProofVerdict.HEAD_FAILED, ProofVerdict.BASE_UNAVAILABLE)
        for each_verdict in all_verdicts
    ):
        return FAILED_EXIT_CODE
    if ProofVerdict.PROVEN in all_verdicts:
        return PASSED_EXIT_CODE
    sys.stderr.write(NO_BASE_FAILURE_MESSAGE.format(revision=base_revision) + "\n")
    return FAILED_EXIT_CODE


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
    all_changed_python_tests = _changed_python_tests(all_changed_paths)
    all_changed_node_tests = _changed_node_tests(all_changed_paths)
    if not all_changed_python_tests and not all_changed_node_tests:
        sys.stderr.write(NO_CHANGED_TEST_MESSAGE + "\n")
        return FAILED_EXIT_CODE
    base_revision = parsed_arguments.base_revision
    all_verdicts: list[ProofVerdict] = []
    if all_changed_python_tests:
        all_verdicts.append(
            _python_proof_verdict(all_changed_python_tests, repository_root, base_revision)
        )
    if all_changed_node_tests:
        all_verdicts.append(
            _node_proof_verdict(all_changed_node_tests, repository_root, base_revision)
        )
    return _proof_exit_code(all_verdicts, base_revision)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
