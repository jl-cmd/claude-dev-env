"""Run the staged Python test files, grouped by their owning pytest config.

The commit gate runs each staged test file so a broken test blocks the commit.
Files are grouped by the nearest ancestor holding a pytest config, and each
group runs in its own pytest session with the working directory at that root, so
two packages exposing a same-named top-level package never shadow each other.

``conftest.py`` paths are never passed as pytest collection targets: pytest loads
them automatically when nearby tests run, and collecting multiple bare confests
in one session collides on the shared module basename.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

from pr_loop_shared_constants.code_rules_gate_constants import (
    ALL_GIT_CHECKOUT_INDEX_COMMAND,
    ALL_GIT_EMPTY_TREE_COMMIT_COMMAND,
    ALL_GIT_HEAD_COMMAND,
    ALL_GIT_READ_TREE_COMMAND,
    ALL_GIT_TOP_LEVEL_COMMAND,
    ALL_GIT_WORKTREE_ADD_COMMAND,
    ALL_GIT_WORKTREE_PRUNE_COMMAND,
    ALL_GIT_WORKTREE_REMOVE_COMMAND,
    ALL_GIT_WRITE_TREE_COMMAND,
    ALL_POSIX_VENV_PYTHON_RELATIVE_PATH_SEGMENTS,
    ALL_PYTEST_CONFIG_FILE_SECTIONS,
    ALL_STAGED_PYTEST_ARGUMENTS,
    ALL_VENV_DIRECTORY_NAMES,
    ALL_WINDOWS_VENV_PYTHON_RELATIVE_PATH_SEGMENTS,
    CODE_RULES_GATE_PYTHON_ENV_VAR,
    CODE_RULES_GATE_PYTHONPATH_ENV_VAR,
    COMMAND_LINE_ARGUMENT_SEPARATOR_LENGTH,
    MAXIMUM_STAGED_PYTEST_COMMAND_LINE_CHARACTERS,
    PYTHON_FILE_EXTENSION,
    PYTHONPATH_ENV_VAR,
    STAGED_PYTEST_TIMEOUT_SECONDS,
    STAGED_TEST_ORIGINAL_ROOT_ENV_VAR,
    STAGED_TEST_SNAPSHOT_ROOT_ENV_VAR,
    STAGED_TEST_FAILURE_HEADER,
    STAGED_TEST_GROUP_FAILURE_MESSAGE,
    TEST_CONFTEST_FILENAME,
)
from pr_loop_shared_constants.preflight_constants import (
    PYTEST_NO_TESTS_COLLECTED_EXIT_CODE,
)
from terminology_sweep import repository_environment

from code_rules_gate_parts.git_file_sets import paths_from_git_staged
from code_rules_gate_parts.staged_pytest_entry import _mapped_snapshot_path
from code_rules_gate_parts.wrapper_plumb_check import is_test_path


def _is_conftest_path(file_path: Path) -> bool:
    """Return True when *file_path* is a pytest ``conftest.py`` fixture module."""
    return file_path.name == TEST_CONFTEST_FILENAME


def _staged_test_relative_paths(repository_root: Path) -> list[Path]:
    """Return collectable staged Python test paths relative to the top level.

    Args:
        repository_root: The repository root whose staged index is read.

    Returns:
        Relative staged Python test paths, excluding bare conftest modules.
    """
    all_test_paths: list[Path] = []
    for each_path in paths_from_git_staged(repository_root):
        if each_path.suffix != PYTHON_FILE_EXTENSION:
            continue
        if is_test_path(str(each_path)) and not _is_conftest_path(each_path):
            all_test_paths.append(each_path.relative_to(repository_root))
    return all_test_paths


def _directory_holds_pytest_config(directory: Path) -> bool:
    """Return True when *directory* holds a recognized pytest configuration file."""
    for each_filename, each_required_section in ALL_PYTEST_CONFIG_FILE_SECTIONS:
        config_path = directory / each_filename
        if not config_path.is_file():
            continue
        if each_required_section is None:
            return True
        try:
            config_text = config_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if each_required_section in config_text:
            return True
    return False


def _resolve_owning_test_root(test_file_path: Path, repository_root: Path) -> Path:
    """Return the nearest ancestor of *test_file_path* owning a pytest config.

    Args:
        test_file_path: The staged test file to resolve a root for.
        repository_root: The repository root that bounds the upward walk.

    Returns:
        The resolved owning test root directory.
    """
    resolved_repository_root = repository_root.resolve()
    for each_ancestor in test_file_path.resolve().parents:
        if _directory_holds_pytest_config(each_ancestor):
            return each_ancestor
        if each_ancestor == resolved_repository_root:
            return resolved_repository_root
    return resolved_repository_root


def _group_staged_tests_by_root(
    all_test_paths: list[Path], repository_root: Path
) -> dict[Path, list[Path]]:
    """Group *all_test_paths* by their owning pytest-config root.

    Args:
        all_test_paths: The staged test files to partition.
        repository_root: The repository root that bounds each upward walk.

    Returns:
        A mapping from owning test root to the staged test files under it.
    """
    all_tests_by_root: dict[Path, list[Path]] = {}
    for each_test_path in all_test_paths:
        owning_root = _resolve_owning_test_root(each_test_path, repository_root)
        all_tests_by_root.setdefault(owning_root, []).append(each_test_path)
    return all_tests_by_root


def _venv_python_relative_path() -> tuple[str, ...]:
    """Return the venv-relative python executable path segments for this platform."""
    if os.name == "nt":
        return ALL_WINDOWS_VENV_PYTHON_RELATIVE_PATH_SEGMENTS
    return ALL_POSIX_VENV_PYTHON_RELATIVE_PATH_SEGMENTS


def _venv_python_executable(repository_root: Path) -> Path | None:
    """Return the first existing venv interpreter under *repository_root*.

    Args:
        repository_root: The repository root to search for a venv directory.

    Returns:
        The resolved interpreter path, or None when no candidate exists.
    """
    relative_python_path = _venv_python_relative_path()
    for each_venv_directory_name in ALL_VENV_DIRECTORY_NAMES:
        candidate_path = repository_root.joinpath(each_venv_directory_name, *relative_python_path)
        if candidate_path.is_file():
            return candidate_path
    return None


def _resolve_gate_python_executable(repository_root: Path) -> str:
    """Return the interpreter the staged-test subprocess runs under.

    Resolves the ``CODE_RULES_GATE_PYTHON`` variable, then a project venv
    interpreter, then the interpreter running the gate.

    Args:
        repository_root: The repository root used to locate a project venv.

    Returns:
        The absolute path or command name of the interpreter to invoke.
    """
    configured_python = os.environ.get(CODE_RULES_GATE_PYTHON_ENV_VAR)
    if configured_python:
        return configured_python
    venv_python = _venv_python_executable(repository_root)
    if venv_python is not None:
        return str(venv_python)
    return sys.executable


def _mapped_python_path(
    path_text: str, repository_root: Path, snapshot_root: Path
) -> str:
    return str(_mapped_snapshot_path(Path(path_text), repository_root, snapshot_root))


def _rewritten_pythonpath(
    pythonpath_text: str, repository_root: Path, snapshot_root: Path
) -> str:
    return os.pathsep.join(
        _mapped_python_path(each_path, repository_root, snapshot_root)
        for each_path in pythonpath_text.split(os.pathsep)
        if each_path
    )


def _staged_pytest_environment(
    repository_root: Path | None = None, snapshot_root: Path | None = None
) -> dict[str, str]:
    """Return the subprocess environment for the staged-test pytest run.

    Returns:
        The ``repository_environment`` mapping, with ``CODE_RULES_GATE_PYTHONPATH``
        prepended to ``PYTHONPATH`` when it is set.
    """
    environment = repository_environment()
    configured_pythonpath = os.environ.get(CODE_RULES_GATE_PYTHONPATH_ENV_VAR, "")
    existing_pythonpath = environment.get(PYTHONPATH_ENV_VAR, "")
    all_pythonpath_entries = [configured_pythonpath, existing_pythonpath]
    if repository_root is not None and snapshot_root is not None:
        all_pythonpath_entries.insert(0, str(Path(__file__).resolve().parent.parent))
    combined_pythonpath = os.pathsep.join(
        each_path for each_path in all_pythonpath_entries if each_path
    )
    if repository_root is None or snapshot_root is None:
        if combined_pythonpath:
            environment[PYTHONPATH_ENV_VAR] = combined_pythonpath
        return environment
    environment[STAGED_TEST_ORIGINAL_ROOT_ENV_VAR] = str(repository_root)
    environment[STAGED_TEST_SNAPSHOT_ROOT_ENV_VAR] = str(snapshot_root)
    environment[PYTHONPATH_ENV_VAR] = _rewritten_pythonpath(
        combined_pythonpath, repository_root, snapshot_root
    )
    return environment


def _relative_pytest_argument(test_path: Path, group_root: Path) -> str:
    """Express *test_path* as a pytest argument relative to *group_root*.

    ::

        group_root = /repo/package
        ok:   /repo/package/tests/test_a.py -> "tests/test_a.py"
        flag: /elsewhere/test_b.py          -> passed absolute

    Args:
        test_path: The staged test file to express as a pytest argument.
        group_root: The pytest working directory for the group.

    Returns:
        The path relative to *group_root* when nested under it, else absolute.
    """
    try:
        return str(test_path.relative_to(group_root))
    except ValueError:
        return str(test_path)


def _batched_pytest_arguments(
    all_pytest_arguments: list[str], character_budget: int
) -> list[list[str]]:
    """Split pytest path arguments into command-line-length-safe batches.

    Args:
        all_pytest_arguments: The path arguments to distribute, in order.
        character_budget: The joined length each batch stays within; an argument
            wider than the budget lands in a batch by itself.

    Returns:
        One argument list per pytest invocation, preserving input order.
    """
    all_batches: list[list[str]] = []
    current_batch: list[str] = []
    current_length = 0
    for each_argument in all_pytest_arguments:
        argument_length = len(each_argument) + COMMAND_LINE_ARGUMENT_SEPARATOR_LENGTH
        if current_batch and current_length + argument_length > character_budget:
            all_batches.append(current_batch)
            current_batch = []
            current_length = 0
        current_batch.append(each_argument)
        current_length += argument_length
    if current_batch:
        all_batches.append(current_batch)
    return all_batches


def _pytest_batch_exit_code(
    all_batch_command: list[str],
    group_root: Path,
    repository_root: Path | None = None,
    snapshot_root: Path | None = None,
) -> int:
    """Run one pytest invocation and normalize its exit code.

    Args:
        all_batch_command: The full argv for this pytest invocation.
        group_root: The owning test root used as the working directory.

    Returns:
        0 when the batch passes or collects no tests; pytest's exit code
        otherwise.
    """
    pytest_process = subprocess.run(
        all_batch_command,
        cwd=str(group_root),
        timeout=STAGED_PYTEST_TIMEOUT_SECONDS,
        check=False,
        env=_staged_pytest_environment(repository_root, snapshot_root),
    )
    if pytest_process.returncode == PYTEST_NO_TESTS_COLLECTED_EXIT_CODE:
        return 0
    return pytest_process.returncode


def _pytest_fixed_command(repository_root: Path) -> list[str]:
    """Return the interpreter-and-pytest prefix shared by every batch."""
    return [
        _resolve_gate_python_executable(repository_root),
        str(Path(__file__).with_name("staged_pytest_entry.py")),
        *ALL_STAGED_PYTEST_ARGUMENTS,
    ]


def _first_failing_batch_exit_code(
    all_fixed_command: list[str],
    all_batches: list[list[str]],
    group_root: Path,
    repository_root: Path,
    snapshot_root: Path,
) -> int:
    """Run each batch and return the first non-zero pytest exit code, or zero."""
    first_failing_exit_code = 0
    for each_batch in all_batches:
        batch_exit_code = _pytest_batch_exit_code(
            [*all_fixed_command, *each_batch],
            group_root,
            repository_root,
            snapshot_root,
        )
        if batch_exit_code != 0 and first_failing_exit_code == 0:
            first_failing_exit_code = batch_exit_code
    return first_failing_exit_code


def _run_pytest_for_group(
    group_root: Path,
    all_group_test_paths: list[Path],
    repository_root: Path,
    snapshot_root: Path | None = None,
) -> int:
    """Run pytest over one group's test files, split into budget-safe batches.

    Args:
        group_root: The owning test root used as the pytest working directory.
        all_group_test_paths: The staged test files that share *group_root*.
        repository_root: The repository root used to resolve a project venv.

    Returns:
        0 when every batch passes or collects nothing; the first failing batch's
        exit code otherwise.
    """
    all_fixed_command = _pytest_fixed_command(repository_root)
    fixed_command_length = sum(
        len(each_part) + COMMAND_LINE_ARGUMENT_SEPARATOR_LENGTH for each_part in all_fixed_command
    )
    all_batches = _batched_pytest_arguments(
        [_relative_pytest_argument(each_path, group_root) for each_path in all_group_test_paths],
        MAXIMUM_STAGED_PYTEST_COMMAND_LINE_CHARACTERS - fixed_command_length,
    )
    resolved_snapshot_root = snapshot_root or repository_root
    return _first_failing_batch_exit_code(
        all_fixed_command,
        all_batches,
        group_root,
        repository_root,
        resolved_snapshot_root,
    )


def _run_grouped_staged_tests(
    all_tests_by_root: dict[Path, list[Path]],
    materialized_root: Path,
    repository_root: Path,
) -> int:
    """Run snapshot test groups and report their source-tree roots."""
    first_failing_exit_code = 0
    for each_materialized_group_root in sorted(all_tests_by_root):
        group_relative_path = each_materialized_group_root.relative_to(materialized_root)
        source_group_root = repository_root / group_relative_path
        group_exit_code = _run_pytest_for_group(
            each_materialized_group_root,
            all_tests_by_root[each_materialized_group_root],
            repository_root,
            materialized_root,
        )
        if group_exit_code == 0:
            continue
        sys.stderr.write(
            STAGED_TEST_GROUP_FAILURE_MESSAGE.format(group_root=source_group_root) + "\n"
        )
        if first_failing_exit_code == 0:
            first_failing_exit_code = group_exit_code
    return first_failing_exit_code


def _git_text(repository_root: Path, all_command: tuple[str, ...]) -> str | None:
    completed_process = subprocess.run(
        list(all_command),
        cwd=str(repository_root),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=STAGED_PYTEST_TIMEOUT_SECONDS,
        env=repository_environment(),
    )
    if completed_process.returncode != 0:
        return None
    return completed_process.stdout.strip()


def _run_git_command(repository_root: Path, all_command: list[str]) -> bool:
    return _git_text(repository_root, tuple(all_command)) is not None


def _create_snapshot_worktree(
    repository_root: Path, snapshot_root: Path, head_oid: str, index_tree_oid: str
) -> bool:
    if not _run_git_command(
        repository_root, [*ALL_GIT_WORKTREE_ADD_COMMAND, str(snapshot_root), head_oid]
    ):
        return False
    if not _run_git_command(snapshot_root, [*ALL_GIT_READ_TREE_COMMAND, index_tree_oid]):
        return False
    return _run_git_command(snapshot_root, list(ALL_GIT_CHECKOUT_INDEX_COMMAND))


def _remove_snapshot_worktree(repository_root: Path, snapshot_root: Path) -> None:
    is_worktree_removed = _run_git_command(
        repository_root, [*ALL_GIT_WORKTREE_REMOVE_COMMAND, str(snapshot_root)]
    )
    if is_worktree_removed:
        return
    _run_git_command(repository_root, list(ALL_GIT_WORKTREE_PRUNE_COMMAND))


def _canonical_repository_root(repository_root: Path) -> Path | None:
    top_level_text = _git_text(repository_root, ALL_GIT_TOP_LEVEL_COMMAND)
    if not top_level_text:
        return None
    return Path(top_level_text).resolve()


def run_staged_test_files(repository_root: Path) -> int:
    """Run pytest over the staged test files and return the gate exit code.

    ``conftest.py`` files are excluded from collection targets. Pytest still
    loads them automatically when a nearby staged test runs under the same
    owning root.

    Args:
        repository_root: The repository root the staged test files belong to.

    Returns:
        0 when no collectable test file is staged, when every group collects no
        tests, or when every group passes. The first failing group's exit code
        otherwise.
    """
    canonical_root = _canonical_repository_root(repository_root)
    if canonical_root is None:
        return 1
    all_staged_test_paths = _staged_test_relative_paths(canonical_root)
    if not all_staged_test_paths:
        return 0
    head_oid = _git_text(canonical_root, ALL_GIT_HEAD_COMMAND)
    if not head_oid:
        head_oid = _git_text(canonical_root, ALL_GIT_EMPTY_TREE_COMMIT_COMMAND)
    index_tree_oid = _git_text(canonical_root, ALL_GIT_WRITE_TREE_COMMAND)
    if not head_oid or not index_tree_oid:
        return 1
    with tempfile.TemporaryDirectory() as temporary_directory:
        materialized_root = Path(temporary_directory) / "worktree"
        if not _create_snapshot_worktree(
            canonical_root, materialized_root, head_oid, index_tree_oid
        ):
            _remove_snapshot_worktree(canonical_root, materialized_root)
            return 1
        try:
            all_materialized_test_paths = [
                materialized_root / each_path for each_path in all_staged_test_paths
            ]
            all_tests_by_root = _group_staged_tests_by_root(
                all_materialized_test_paths, materialized_root
            )
            first_failing_exit_code = _run_grouped_staged_tests(
                all_tests_by_root, materialized_root, canonical_root
            )
        finally:
            _remove_snapshot_worktree(canonical_root, materialized_root)
    if first_failing_exit_code != 0:
        sys.stderr.write(STAGED_TEST_FAILURE_HEADER + "\n")
    return first_failing_exit_code
