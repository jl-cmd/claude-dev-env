"""Block a commit only on a test failure the staged change itself introduces.

::

    staged run:   pkg/test_a.py -> 2 failures (test_x, test_y)
    baseline run (HEAD worktree): pkg/test_a.py -> 1 failure (test_x)
    regression = staged - baseline = {test_y}   -> blocks
    test_x was already red before this change   -> does not block

A staged test group that fails is re-run against the code as it stood before
the change: a throwaway detached-HEAD worktree is created under the OS temp
root, the same group runs there with its paths remapped into that tree, and
the two failure sets are diffed by (classname, name) identity read from each
run's JUnit XML report. Only a failure absent from the baseline run blocks the
commit. The user's own working tree and index are never moved, so a crashed
run leaves every staged edit exactly where it was.

Moving the working directory alone would leave an absolute import route — a
``PYTHONPATH`` entry under the repository root, or an editable install pointing
at it — still feeding staged code to the baseline, whose identical failure
would then cancel a real regression out. ``baseline_import_isolation`` moves
every repository import root into the baseline worktree and reports which
modules the baseline actually loaded from the user's tree; a baseline that read
staged code is discarded, and every staged failure in that group blocks.
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
    BASELINE_LEAK_PLUGIN_DIRECTORY_NAME,
    BASELINE_LEAK_REPORT_FILENAME,
    ALL_GIT_WORKTREE_ADD_DETACH_ARGS,
    ALL_GIT_WORKTREE_PRUNE_ARGS,
    ALL_GIT_WORKTREE_REMOVE_FORCE_ARGS,
    GIT_HEAD_REVISION,
    JUNIT_XML_CLASSNAME_ATTRIBUTE,
    JUNIT_XML_ERROR_TAG,
    JUNIT_XML_FAILURE_TAG,
    JUNIT_XML_MISSING_ATTRIBUTE_FALLBACK,
    JUNIT_XML_NAME_ATTRIBUTE,
    JUNIT_XML_TESTCASE_TAG,
    REGRESSION_BASELINE_IMPORT_LEAK_MESSAGE,
    REGRESSION_BASELINE_JUNIT_SUBDIRECTORY_NAME,
    REGRESSION_BASELINE_LEAK_UNREPORTED_MESSAGE,
    REGRESSION_BASELINE_WORKTREE_DIRECTORY_NAME,
    REGRESSION_BASELINE_WORKTREE_TEMP_DIRECTORY_PREFIX,
    REGRESSION_GROUP_FAILURE_MESSAGE,
    REGRESSION_JUNIT_TEMP_DIRECTORY_PREFIX,
    REGRESSION_NO_BASELINE_MESSAGE,
    REGRESSION_PRE_EXISTING_FAILURE_BYPASSED_MESSAGE,
    REGRESSION_STAGED_JUNIT_SUBDIRECTORY_NAME,
    REGRESSION_WORKTREE_ADD_FAILED_MESSAGE,
    REGRESSION_WORKTREE_REMOVE_FAILED_MESSAGE,
    STAGED_TEST_FAILURE_HEADER,
)
from terminology_sweep import repository_environment

from code_rules_gate_parts import baseline_import_isolation, staged_test_running

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
    environment: dict[str, str] | None = None,
) -> GroupOutcome:
    """Run one test group and return its exit code with its failing test identities.

    Args:
        group_root: The pytest working directory for this run.
        all_group_test_paths: The collection targets to pass pytest.
        repository_root: The repository root the interpreter resolves against.
        junit_xml_dir: Where this run's JUnit XML reports are written.
        environment: When given, the environment the run uses; the baseline run
            passes one that resolves imports inside the baseline worktree.

    Returns:
        The run's exit code alongside every failing test identity it reported.
    """
    junit_xml_dir.mkdir(parents=True, exist_ok=True)
    exit_code = staged_test_running._run_pytest_for_group(
        group_root,
        all_group_test_paths,
        repository_root,
        junit_xml_dir=junit_xml_dir,
        environment=environment,
    )
    return GroupOutcome(exit_code, _junit_failure_identities(junit_xml_dir))


def _existing_group_targets(all_group_test_paths: list[Path]) -> list[Path]:
    """Return the given test paths that exist on disk.

    Applied to paths already remapped into the baseline worktree: a test file
    staged for the first time has no counterpart at HEAD, so its remapped path
    is absent from that worktree and drops out of the baseline run entirely —
    every one of its failures is then, correctly, treated as new by the
    staged/baseline set difference.
    """
    return [each_path for each_path in all_group_test_paths if each_path.is_file()]


def _path_under_baseline_worktree(
    original_path: Path, repository_root: Path, baseline_worktree: Path
) -> Path:
    """Return *original_path* rebased onto the baseline worktree.

    ::

        repository_root   = /repo
        baseline_worktree = /tmp/code_rules_gate_baseline_ab/tree
        ok: /repo/pkg_a/test_alpha.py -> /tmp/.../tree/pkg_a/test_alpha.py

    The baseline run happens inside a separate checkout, so every group root
    and every collection target moves with it.

    Args:
        original_path: A path under the user's repository root.
        repository_root: The repository root *original_path* is relative to.
        baseline_worktree: The detached-HEAD worktree the baseline run uses.

    Returns:
        The same repository-relative location inside *baseline_worktree*.
    """
    repository_relative_path = original_path.resolve().relative_to(repository_root.resolve())
    return baseline_worktree / repository_relative_path


def _baseline_group_targets(
    all_group_test_paths: list[Path], repository_root: Path, baseline_worktree: Path
) -> list[Path]:
    """Return the group's collection targets, rebased into the baseline worktree."""
    return _existing_group_targets(
        [
            _path_under_baseline_worktree(each_path, repository_root, baseline_worktree)
            for each_path in all_group_test_paths
        ]
    )


@dataclass(frozen=True)
class BaselineRunContext:
    """What every baseline group run in one gate run shares.

    Attributes:
        worktree: The detached-HEAD worktree the baseline runs happen in.
        all_import_roots: Every directory the interpreter resolves imported
            packages from, including the roots an editable install registers.
        plugin_directory: Where the import-origin reporting plugin was written.
        staged_environment: The environment the staged runs used.
    """

    worktree: Path
    all_import_roots: list[Path]
    plugin_directory: Path
    staged_environment: dict[str, str]


def _baseline_run_context(
    repository_root: Path, baseline_worktree: Path, junit_root: Path
) -> BaselineRunContext:
    """Install the leak plugin and probe the interpreter's import roots once per gate run."""
    plugin_directory = junit_root / BASELINE_LEAK_PLUGIN_DIRECTORY_NAME
    baseline_import_isolation.install_leak_plugin(plugin_directory)
    staged_environment = staged_test_running._staged_pytest_environment()
    all_import_roots = baseline_import_isolation.discover_import_roots(
        staged_test_running._resolve_gate_python_executable(repository_root),
        staged_environment,
        baseline_worktree.parent,
    )
    return BaselineRunContext(
        baseline_worktree, all_import_roots, plugin_directory, staged_environment
    )


def _trusted_baseline_outcome(
    group_root: Path, baseline_outcome: GroupOutcome, leak_report_path: Path
) -> GroupOutcome:
    """Return the baseline outcome, emptied of failures when the run read the user's own tree.

    ::

        ok:   report []                 -> baseline kept; its failures cancel staged ones
        flag: report [/repo/pkg/foo.py] -> baseline discarded; every staged failure blocks
        flag: no report at all          -> baseline discarded; nothing was proven

    A baseline that imported staged code fails the same way the staged run did,
    which would cancel a real regression out. Emptying its failure set makes
    every staged failure count as new, so the commit blocks instead.
    """
    all_leaked_modules = baseline_import_isolation.modules_imported_from_primary_tree(
        leak_report_path
    )
    if all_leaked_modules is None:
        sys.stderr.write(
            REGRESSION_BASELINE_LEAK_UNREPORTED_MESSAGE.format(group_root=group_root) + "\n"
        )
        return GroupOutcome(baseline_outcome.exit_code, frozenset())
    if not all_leaked_modules:
        return baseline_outcome
    sys.stderr.write(
        REGRESSION_BASELINE_IMPORT_LEAK_MESSAGE.format(
            group_root=group_root,
            count=len(all_leaked_modules),
            first_module=all_leaked_modules[0],
        )
        + "\n"
    )
    return GroupOutcome(baseline_outcome.exit_code, frozenset())


def _baseline_group_outcome(
    group_root: Path,
    baseline_targets: list[Path],
    repository_root: Path,
    group_junit_dir: Path,
    context: BaselineRunContext,
) -> GroupOutcome:
    """Run one group inside the baseline worktree and keep the result only when it stayed clean."""
    leak_report_path = group_junit_dir / BASELINE_LEAK_REPORT_FILENAME
    baseline_environment = baseline_import_isolation.baseline_pytest_environment(
        context.staged_environment,
        repository_root,
        context.worktree,
        context.all_import_roots,
        context.plugin_directory,
        leak_report_path,
    )
    baseline_outcome = _run_group_and_collect(
        _path_under_baseline_worktree(group_root, repository_root, context.worktree),
        baseline_targets,
        repository_root,
        group_junit_dir,
        environment=baseline_environment,
    )
    return _trusted_baseline_outcome(group_root, baseline_outcome, leak_report_path)


def _baseline_outcomes_for_failing_groups(
    repository_root: Path,
    failing_group_test_paths: dict[Path, list[Path]],
    junit_root: Path,
    baseline_worktree: Path,
) -> dict[Path, GroupOutcome]:
    """Run, inside the baseline worktree, only the groups whose staged run failed.

    Each group's root and collection targets are rebased into
    *baseline_worktree*, and so is every import root that resolves inside the
    user's repository, so an absolute import route never serves staged code to
    the baseline. *repository_root* stays the user's own repository, because
    the interpreter resolves against the project venv that lives there. Every
    outcome stays keyed by the original group root, which is the key the caller
    looks the staged outcome up by.
    """
    context = _baseline_run_context(repository_root, baseline_worktree, junit_root)
    baseline_outcomes: dict[Path, GroupOutcome] = {}
    for group_index, (group_root, all_group_test_paths) in enumerate(
        sorted(failing_group_test_paths.items())
    ):
        baseline_targets = _baseline_group_targets(
            all_group_test_paths, repository_root, baseline_worktree
        )
        if not baseline_targets:
            baseline_outcomes[group_root] = GroupOutcome(0, frozenset())
            continue
        group_junit_dir = (
            junit_root / REGRESSION_BASELINE_JUNIT_SUBDIRECTORY_NAME / str(group_index)
        )
        baseline_outcomes[group_root] = _baseline_group_outcome(
            group_root, baseline_targets, repository_root, group_junit_dir, context
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


def _add_baseline_worktree(repository_root: Path, baseline_worktree: Path) -> bool:
    """Attach a detached-HEAD checkout at *baseline_worktree*; True when git created it."""
    worktree_added = _run_git(
        repository_root,
        (*ALL_GIT_WORKTREE_ADD_DETACH_ARGS, str(baseline_worktree), GIT_HEAD_REVISION),
    )
    return worktree_added.returncode == 0


def _remove_baseline_worktree(repository_root: Path, baseline_worktree: Path) -> None:
    """Detach and delete the baseline worktree, pruning its registration when removal fails."""
    worktree_removed = _run_git(
        repository_root, (*ALL_GIT_WORKTREE_REMOVE_FORCE_ARGS, str(baseline_worktree))
    )
    if worktree_removed.returncode == 0:
        return
    _run_git(repository_root, ALL_GIT_WORKTREE_PRUNE_ARGS)
    sys.stderr.write(REGRESSION_WORKTREE_REMOVE_FAILED_MESSAGE + "\n")


def _score_groups_against_baseline(
    failing_group_test_paths: dict[Path, list[Path]],
    staged_outcomes: dict[Path, GroupOutcome],
    baseline_outcomes: dict[Path, GroupOutcome],
) -> int:
    """Report each group's staged-minus-baseline diff and return the first blocking code."""
    return _first_nonzero(
        _report_group_outcome(
            group_root,
            staged_outcomes[group_root],
            baseline_outcomes.get(group_root, GroupOutcome(0, frozenset())).failing_identities,
        )
        for group_root in sorted(failing_group_test_paths)
    )


def _run_regression_gate(
    repository_root: Path,
    failing_group_test_paths: dict[Path, list[Path]],
    staged_outcomes: dict[Path, GroupOutcome],
    junit_root: Path,
) -> int:
    """Re-run the failing groups in a throwaway HEAD worktree and score the diff.

    The user's own working tree and index stay where they are for the whole
    run: the baseline lives in its own detached checkout under the OS temp
    root, and that checkout is removed before the gate returns.
    """
    with tempfile.TemporaryDirectory(
        prefix=REGRESSION_BASELINE_WORKTREE_TEMP_DIRECTORY_PREFIX, ignore_cleanup_errors=True
    ) as baseline_parent_text:
        baseline_worktree = (
            Path(baseline_parent_text) / REGRESSION_BASELINE_WORKTREE_DIRECTORY_NAME
        )
        if not _add_baseline_worktree(repository_root, baseline_worktree):
            sys.stderr.write(REGRESSION_WORKTREE_ADD_FAILED_MESSAGE + "\n")
            return _first_nonzero(outcome.exit_code for outcome in staged_outcomes.values())
        try:
            baseline_outcomes = _baseline_outcomes_for_failing_groups(
                repository_root, failing_group_test_paths, junit_root, baseline_worktree
            )
        finally:
            _remove_baseline_worktree(repository_root, baseline_worktree)
        return _score_groups_against_baseline(
            failing_group_test_paths, staged_outcomes, baseline_outcomes
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
    further check. A group that fails is re-run against the HEAD baseline (a
    throwaway detached-HEAD worktree under the OS temp root), and only a
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
