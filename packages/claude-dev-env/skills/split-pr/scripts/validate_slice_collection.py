"""Gate a stacked slice with pytest collection after commit.

Path-layer splits put definitions on the wrong side of a cut without a
diff-reading review ever seeing the break. Running collection on the slice tip
surfaces ImportError and missing-module failures before push.

::

    validate_slice_collection(repo, ["pkg/tests/test_a.py"], branch="split/1/01")
    # ok: passed when imports resolve on this branch tip
    # flag: passed False when a test imports a symbol only later slices add
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from split_pr_scripts_constants.config.execute_constants import (
    COLLECTION_SKIP_DISABLED,
    COLLECTION_SKIP_NO_ON_DISK_TESTS,
    COLLECTION_SKIP_NO_TEST_PATHS,
    COLLECTION_SKIP_PYTEST_UNAVAILABLE,
    COLLECTION_TIMEOUT_SECONDS,
    CONFTEST_BASENAME,
    ERROR_COLLECTION_FAILED,
    PAYLOAD_KEY_CHECKED,
    PAYLOAD_KEY_COLLECTION_ERROR,
    PAYLOAD_KEY_PASSED,
    PAYLOAD_KEY_SKIPPED,
    PAYLOAD_KEY_SKIP_REASON,
    PAYLOAD_KEY_TEST_PATHS,
    PYTEST_COLLECT_ONLY_FLAG,
    ALL_PYTEST_MISSING_MARKERS,
    PYTEST_MODULE,
    PYTEST_PATHSPEC,
    PYTEST_QUIET_FLAG,
    PYTHON_FILE_SUFFIX,
    PYTHON_MODULE_FLAG,
    TEST_MODULE_PREFIX,
    TEST_MODULE_SUFFIX,
)

JsonObject = dict[str, object]
CollectRunner = Callable[[Path, list[str]], subprocess.CompletedProcess[str]]


def is_pytest_collectable_path(path: str) -> bool:
    """Return whether a path is a pytest test module (not conftest).

    ::

        is_pytest_collectable_path("pkg/tests/test_a.py")  # ok: True
        is_pytest_collectable_path("pkg/tests/conftest.py")  # ok: False

    Args:
        path: Repository-relative path.

    Returns:
        True when the basename is a ``test_*.py`` or ``*_test.py`` module.
    """
    normalized = path.replace("\\", "/").strip()
    if not normalized.lower().endswith(PYTHON_FILE_SUFFIX):
        return False
    basename = normalized.rsplit("/", 1)[-1]
    lowered_basename = basename.lower()
    if lowered_basename == CONFTEST_BASENAME:
        return False
    return lowered_basename.startswith(TEST_MODULE_PREFIX) or lowered_basename.endswith(
        TEST_MODULE_SUFFIX
    )


def select_collectable_paths(all_paths: list[str]) -> list[str]:
    """Return sorted unique pytest-collectable paths from a path list.

    Args:
        all_paths: Repository-relative paths from the cumulative stack.

    Returns:
        Deduplicated collectable test module paths in sorted order.
    """
    all_collectable = {
        each_path.replace("\\", "/").strip()
        for each_path in all_paths
        if is_pytest_collectable_path(each_path)
    }
    return sorted(all_collectable)


def run_pytest_collect_only(
    repo_root: Path,
    all_test_paths: list[str],
) -> subprocess.CompletedProcess[str]:
    """Run ``python -m pytest --collect-only`` on the given test paths.

    Args:
        repo_root: Git repository root used as the process working directory.
        all_test_paths: On-disk test module paths relative to ``repo_root``.

    Returns:
        Completed process with stdout/stderr captured.
    """
    all_command = [
        sys.executable,
        PYTHON_MODULE_FLAG,
        PYTEST_MODULE,
        PYTEST_COLLECT_ONLY_FLAG,
        PYTEST_QUIET_FLAG,
        PYTEST_PATHSPEC,
        *all_test_paths,
    ]
    return subprocess.run(
        all_command,
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
        timeout=COLLECTION_TIMEOUT_SECONDS,
    )


def validate_slice_collection(
    repo_root: Path,
    all_paths: list[str],
    *,
    branch_name: str,
    is_enabled: bool = True,
    run_collect: CollectRunner | None = None,
) -> JsonObject:
    """Collect stack test modules at a slice tip; fail when imports break.

    ::

        # tests import a symbol only a later slice adds -> passed False
        # no test paths in the cumulative set -> skipped, passed True

    Args:
        repo_root: Repository root checked out on the slice branch tip.
        all_paths: Cumulative stack file paths through the current slice.
        branch_name: Slice branch name for error text.
        is_enabled: When False, skip the gate (``--skip-collection-check``).
        run_collect: Optional runner override for tests.

    Returns:
        Report with ``checked``, ``passed``, ``skipped``, optional ``error``.
    """
    if not is_enabled:
        return _skipped_report(COLLECTION_SKIP_DISABLED)
    all_collectable = select_collectable_paths(all_paths)
    if not all_collectable:
        return _skipped_report(COLLECTION_SKIP_NO_TEST_PATHS)
    all_on_disk = [
        each_path
        for each_path in all_collectable
        if (repo_root / each_path).is_file()
    ]
    if not all_on_disk:
        return _skipped_report(COLLECTION_SKIP_NO_ON_DISK_TESTS)
    collector = run_collect if run_collect is not None else run_pytest_collect_only
    try:
        completed = collector(repo_root, all_on_disk)
    except subprocess.TimeoutExpired as timeout_error:
        detail = str(timeout_error)
        return _failed_report(
            branch_name=branch_name,
            all_test_paths=all_on_disk,
            detail=detail,
        )
    process_text = _join_process_streams(completed)
    if _is_pytest_unavailable(process_text, completed.returncode):
        return _skipped_report(COLLECTION_SKIP_PYTEST_UNAVAILABLE)
    if completed.returncode != 0:
        return _failed_report(
            branch_name=branch_name,
            all_test_paths=all_on_disk,
            detail=process_text,
        )
    return {
        PAYLOAD_KEY_SKIPPED: False,
        PAYLOAD_KEY_CHECKED: True,
        PAYLOAD_KEY_PASSED: True,
        PAYLOAD_KEY_TEST_PATHS: all_on_disk,
    }


def format_collection_failure_message(branch_name: str, report: JsonObject) -> str:
    """Build the RuntimeError text for a failed collection gate.

    Args:
        branch_name: Slice branch that failed collection.
        report: Failed report from ``validate_slice_collection``.

    Returns:
        Human-readable failure string for partial-stack error payloads.
    """
    detail = str(report.get(PAYLOAD_KEY_COLLECTION_ERROR) or "")
    return ERROR_COLLECTION_FAILED % (branch_name, detail)


def _skipped_report(skip_reason: str) -> JsonObject:
    return {
        PAYLOAD_KEY_SKIPPED: True,
        PAYLOAD_KEY_SKIP_REASON: skip_reason,
        PAYLOAD_KEY_CHECKED: False,
        PAYLOAD_KEY_PASSED: True,
        PAYLOAD_KEY_TEST_PATHS: [],
    }


def _failed_report(
    branch_name: str,
    all_test_paths: list[str],
    detail: str,
) -> JsonObject:
    message = ERROR_COLLECTION_FAILED % (branch_name, detail.strip())
    return {
        PAYLOAD_KEY_SKIPPED: False,
        PAYLOAD_KEY_CHECKED: True,
        PAYLOAD_KEY_PASSED: False,
        PAYLOAD_KEY_TEST_PATHS: all_test_paths,
        PAYLOAD_KEY_COLLECTION_ERROR: message,
    }


def _join_process_streams(completed: subprocess.CompletedProcess[str]) -> str:
    stdout_text = (completed.stdout or "").strip()
    stderr_text = (completed.stderr or "").strip()
    if stdout_text and stderr_text:
        return f"{stdout_text}\n{stderr_text}"
    return stdout_text or stderr_text


def _is_pytest_unavailable(process_text: str, returncode: int) -> bool:
    if returncode == 0:
        return False
    lowered = process_text.lower()
    for each_marker in ALL_PYTEST_MISSING_MARKERS:
        if each_marker.lower() in lowered:
            return True
    return False
