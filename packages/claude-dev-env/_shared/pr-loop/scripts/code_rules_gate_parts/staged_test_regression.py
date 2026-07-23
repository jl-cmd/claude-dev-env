"""Block a commit only on a test failure the staged change itself introduces.

::

    staged run:   pkg/test_a.py -> 2 failures (test_x, test_y)
    baseline run (HEAD, via git stash): pkg/test_a.py -> 1 failure (test_x)
    regression = staged - baseline = {test_y}   -> blocks
    test_x was already red before this change   -> does not block

A staged test group that fails is re-run against the code as it stood before
the change: the working tree is snapshotted to HEAD with 'git stash', the
same group runs again, and the two failure sets are diffed by (classname,
name) identity read from each run's JUnit XML report. Only a failure absent
from the baseline run blocks the commit.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ElementTree
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pr_loop_shared_constants.code_rules_gate_constants import (
    ALL_GIT_HEAD_EXISTS_ARGS,
    ALL_GIT_STASH_POP_ARGS,
    ALL_GIT_STASH_PUSH_ARGS,
    JUNIT_XML_CLASSNAME_ATTRIBUTE,
    JUNIT_XML_ERROR_TAG,
    JUNIT_XML_FAILURE_TAG,
    JUNIT_XML_MISSING_ATTRIBUTE_FALLBACK,
    JUNIT_XML_NAME_ATTRIBUTE,
    JUNIT_XML_TESTCASE_TAG,
    REGRESSION_BASELINE_JUNIT_SUBDIRECTORY_NAME,
    REGRESSION_GROUP_FAILURE_MESSAGE,
    REGRESSION_JUNIT_TEMP_DIRECTORY_PREFIX,
    REGRESSION_NO_BASELINE_MESSAGE,
    REGRESSION_PRE_EXISTING_FAILURE_BYPASSED_MESSAGE,
    REGRESSION_STAGED_JUNIT_SUBDIRECTORY_NAME,
    REGRESSION_STASH_FAILED_MESSAGE,
    REGRESSION_STASH_POP_FAILED_MESSAGE,
    STAGED_TEST_FAILURE_HEADER,
)
from terminology_sweep import repository_environment

from code_rules_gate_parts import staged_test_running

TestIdentity = tuple[str, str]


@dataclass(frozen=True)
class GroupOutcome:
    """One test group's run result.

    Attributes:
        exit_code: The pytest exit code from the run.
        failing_identities: The (classname, name) of every failed or errored
            testcase, read from that run's JUnit XML report.
    """

    exit_code: int
    failing_identities: frozenset[TestIdentity]


def _run_git(
    repository_root: Path, all_git_arguments: tuple[str, ...]
) -> subprocess.CompletedProcess[str]:
    """Run one git subcommand in *repository_root* with the gate's scrubbed environment."""
    return subprocess.run(
        ["git", "-C", str(repository_root), *all_git_arguments],
        capture_output=True,
        text=True,
        check=False,
        env=repository_environment(),
    )


def _head_exists(repository_root: Path) -> bool:
    """Return True when the repository has a prior commit to compare against."""
    return _run_git(repository_root, ALL_GIT_HEAD_EXISTS_ARGS).returncode == 0


def _junit_failure_identities(junit_xml_dir: Path) -> frozenset[TestIdentity]:
    """Return the (classname, name) of every failed/errored testcase under a report directory."""
    identities: set[TestIdentity] = set()
    if not junit_xml_dir.is_dir():
        return frozenset(identities)
    for each_report_path in junit_xml_dir.glob("*.xml"):
        try:
            report_root = ElementTree.parse(each_report_path).getroot()
        except ElementTree.ParseError:
            continue
        for each_testcase in report_root.iter(JUNIT_XML_TESTCASE_TAG):
            identities.update(_failing_identity_for_testcase(each_testcase))
    return frozenset(identities)


def _failing_identity_for_testcase(testcase: ElementTree.Element) -> list[TestIdentity]:
    """Return the testcase's (classname, name) as a one-item list when it failed, else empty."""
    has_failed = (
        testcase.find(JUNIT_XML_FAILURE_TAG) is not None
        or testcase.find(JUNIT_XML_ERROR_TAG) is not None
    )
    if not has_failed:
        return []
    return [
        (
            testcase.get(JUNIT_XML_CLASSNAME_ATTRIBUTE, JUNIT_XML_MISSING_ATTRIBUTE_FALLBACK),
            testcase.get(JUNIT_XML_NAME_ATTRIBUTE, JUNIT_XML_MISSING_ATTRIBUTE_FALLBACK),
        )
    ]


def _run_group_and_collect(
    group_root: Path,
    all_group_test_paths: list[Path],
    repository_root: Path,
    junit_xml_dir: Path,
) -> GroupOutcome:
    """Run one test group and return its exit code with its failing test identities."""
    junit_xml_dir.mkdir(parents=True, exist_ok=True)
    exit_code = staged_test_running._run_pytest_for_group(
        group_root, all_group_test_paths, repository_root, junit_xml_dir=junit_xml_dir
    )
    return GroupOutcome(exit_code, _junit_failure_identities(junit_xml_dir))


def _existing_group_targets(all_group_test_paths: list[Path]) -> list[Path]:
    """Return the staged test paths that exist on disk right now.

    Called after the working tree is reverted to HEAD: a test file staged for
    the first time does not exist at that point, so it drops out of the
    baseline run entirely — every one of its failures is then, correctly,
    treated as new by the staged/baseline set difference.
    """
    return [each_path for each_path in all_group_test_paths if each_path.is_file()]


def _baseline_outcomes_for_failing_groups(
    repository_root: Path,
    failing_group_test_paths: dict[Path, list[Path]],
    junit_root: Path,
) -> dict[Path, GroupOutcome]:
    """Run, against the HEAD baseline, only the groups whose staged run failed."""
    baseline_outcomes: dict[Path, GroupOutcome] = {}
    for group_index, (group_root, all_group_test_paths) in enumerate(
        sorted(failing_group_test_paths.items())
    ):
        baseline_targets = _existing_group_targets(all_group_test_paths)
        if not baseline_targets:
            baseline_outcomes[group_root] = GroupOutcome(0, frozenset())
            continue
        group_junit_dir = (
            junit_root / REGRESSION_BASELINE_JUNIT_SUBDIRECTORY_NAME / str(group_index)
        )
        baseline_outcomes[group_root] = _run_group_and_collect(
            group_root, baseline_targets, repository_root, group_junit_dir
        )
    return baseline_outcomes


def _report_group_outcome(
    group_root: Path, staged_outcome: GroupOutcome, baseline_failing: frozenset[TestIdentity]
) -> int:
    """Compare one group's staged failures against its baseline and report the result.

    Returns:
        0 when every staged failure was already present at the baseline; the
        staged exit code otherwise.
    """
    regression_identities = staged_outcome.failing_identities - baseline_failing
    if not regression_identities:
        sys.stderr.write(
            REGRESSION_PRE_EXISTING_FAILURE_BYPASSED_MESSAGE.format(
                group_root=group_root, count=len(staged_outcome.failing_identities)
            )
            + "\n"
        )
        return 0
    sys.stderr.write(
        REGRESSION_GROUP_FAILURE_MESSAGE.format(
            group_root=group_root, count=len(regression_identities)
        )
        + "\n"
    )
    return staged_outcome.exit_code


def _first_nonzero(all_exit_codes: Iterable[int]) -> int:
    """Return the first non-zero value in *all_exit_codes*, or 0 when none is non-zero."""
    for each_exit_code in all_exit_codes:
        if each_exit_code != 0:
            return each_exit_code
    return 0


def _run_regression_gate(
    repository_root: Path,
    failing_group_test_paths: dict[Path, list[Path]],
    staged_outcomes: dict[Path, GroupOutcome],
    junit_root: Path,
) -> int:
    """Snapshot HEAD, re-run the failing groups there, restore the stage, and score the diff."""
    stash_pushed = _run_git(repository_root, ALL_GIT_STASH_PUSH_ARGS)
    if stash_pushed.returncode != 0:
        sys.stderr.write(REGRESSION_STASH_FAILED_MESSAGE + "\n")
        return _first_nonzero(outcome.exit_code for outcome in staged_outcomes.values())
    try:
        baseline_outcomes = _baseline_outcomes_for_failing_groups(
            repository_root, failing_group_test_paths, junit_root
        )
    finally:
        stash_popped = _run_git(repository_root, ALL_GIT_STASH_POP_ARGS)
        if stash_popped.returncode != 0:
            sys.stderr.write(REGRESSION_STASH_POP_FAILED_MESSAGE + "\n")
    return _first_nonzero(
        _report_group_outcome(
            group_root,
            staged_outcomes[group_root],
            baseline_outcomes.get(group_root, GroupOutcome(0, frozenset())).failing_identities,
        )
        for group_root in sorted(failing_group_test_paths)
    )


def _run_staged_groups(
    all_tests_by_root: dict[Path, list[Path]], repository_root: Path, junit_root: Path
) -> dict[Path, GroupOutcome]:
    """Run every group once under the staged (working-tree) state."""
    staged_outcomes: dict[Path, GroupOutcome] = {}
    for group_index, group_root in enumerate(sorted(all_tests_by_root)):
        group_junit_dir = (
            junit_root / REGRESSION_STAGED_JUNIT_SUBDIRECTORY_NAME / str(group_index)
        )
        staged_outcomes[group_root] = _run_group_and_collect(
            group_root, all_tests_by_root[group_root], repository_root, group_junit_dir
        )
    return staged_outcomes


def run_grouped_tests_with_regression_gate(
    all_tests_by_root: dict[Path, list[Path]], repository_root: Path
) -> int:
    """Run every staged test group and block only on failures the staged change introduces.

    Every group runs once under the staged state. A group that passes needs no
    further check. A group that fails is re-run against the HEAD baseline (the
    working tree temporarily snapshotted back with 'git stash'), and only a
    failure absent from that baseline run blocks the commit — a failure
    already present before this change does not.

    Args:
        all_tests_by_root: Staged test files grouped by owning pytest-config root.
        repository_root: The repository root the staged test files belong to.

    Returns:
        0 when every group passes, or when every failing group's failures are
        all pre-existing at the baseline. The first group with a genuine
        regression's exit code otherwise.
    """
    with tempfile.TemporaryDirectory(
        prefix=REGRESSION_JUNIT_TEMP_DIRECTORY_PREFIX
    ) as junit_root_text:
        junit_root = Path(junit_root_text)
        staged_outcomes = _run_staged_groups(all_tests_by_root, repository_root, junit_root)
        failing_group_test_paths = {
            group_root: all_tests_by_root[group_root]
            for group_root, outcome in staged_outcomes.items()
            if outcome.exit_code != 0
        }
        if not failing_group_test_paths:
            return 0
        if not _head_exists(repository_root):
            sys.stderr.write(REGRESSION_NO_BASELINE_MESSAGE + "\n")
            first_failing_exit_code = _first_nonzero(
                _report_group_outcome(group_root, staged_outcomes[group_root], frozenset())
                for group_root in sorted(failing_group_test_paths)
            )
        else:
            first_failing_exit_code = _run_regression_gate(
                repository_root, failing_group_test_paths, staged_outcomes, junit_root
            )
    if first_failing_exit_code != 0:
        sys.stderr.write(STAGED_TEST_FAILURE_HEADER + "\n")
    return first_failing_exit_code


def run_staged_test_files(repository_root: Path) -> int:
    """Discover the staged test files and run them under the regression gate.

    ``conftest.py`` files are excluded from collection targets. Pytest still
    loads them automatically when a nearby staged test runs under the same
    owning root. A group whose staged run fails is re-checked against the
    pre-staged baseline: a failure already present before the staged change
    never blocks, only a failure the staged change introduces does.

    Args:
        repository_root: The repository root the staged test files belong to.

    Returns:
        0 when no collectable test file is staged, when every group collects no
        tests, when every group passes, or when every failing group's failures
        are all pre-existing at the baseline. The first group with a genuine
        regression's exit code otherwise.
    """
    all_test_paths = staged_test_running._staged_test_file_paths(repository_root)
    all_pytest_targets = staged_test_running._pytest_target_paths(all_test_paths)
    if not all_pytest_targets:
        return 0
    all_tests_by_root = staged_test_running._group_staged_tests_by_root(
        all_pytest_targets, repository_root
    )
    return run_grouped_tests_with_regression_gate(all_tests_by_root, repository_root)
