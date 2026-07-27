"""Run the staged Python test files, grouped by owning pytest config or top-level directory.

The commit gate runs each staged test file so a broken test blocks the commit.
Files are grouped by the nearest ancestor holding a pytest config, falling back
to the file's own top-level directory under the repository root when no ancestor
owns one. Each group runs in its own pytest session with the working directory
at that root, so two packages exposing a same-named top-level package never
shadow each other.

``conftest.py`` paths are never passed as pytest collection targets: pytest loads
them automatically when nearby tests run, and collecting multiple bare confests
in one session collides on the shared module basename.

``staged_test_regression`` is the commit gate's entry point: it discovers the
staged test files, groups them by owning pytest-config root, and calls back
into this module's group-running primitives to run each group (optionally
with a JUnit XML report per batch, for its staged-vs-baseline comparison).

Boundaries of the top-level fallback, which fires only in a repository whose
root holds no pytest config::

    repository_root = /repo, holding no pytest config of its own
    ok:   /repo/alpha/test_a.py, /repo/beta/test_b.py           -> two sessions
    flag: /repo/pkgs/alpha/test_a.py, /repo/pkgs/beta/test_b.py -> one session

Config-less packages nested under one shared top-level directory run in that
directory's single session, so the split separates top-level neighbors alone.
A repository-root ``conftest.py`` stays unloaded for those groups as well: the
session works from the top-level directory, which leaves the root file outside
the tree pytest treats as its root.
"""

import os
import subprocess
import sys
from pathlib import Path

from pr_loop_shared_constants.code_rules_gate_constants import (
    ALL_POSIX_VENV_PYTHON_RELATIVE_PATH_SEGMENTS,
    ALL_PYTEST_CONFIG_FILE_SECTIONS,
    ALL_PYTEST_MODULE_INVOCATION,
    ALL_VENV_DIRECTORY_NAMES,
    ALL_WINDOWS_VENV_PYTHON_RELATIVE_PATH_SEGMENTS,
    CODE_RULES_GATE_PYTHON_ENV_VAR,
    CODE_RULES_GATE_PYTHONPATH_ENV_VAR,
    COMMAND_LINE_ARGUMENT_SEPARATOR_LENGTH,
    JUNIT_XML_FLAG_PREFIX,
    MAXIMUM_STAGED_PYTEST_COMMAND_LINE_CHARACTERS,
    PYTHON_FILE_EXTENSION,
    PYTHONPATH_ENV_VAR,
    STAGED_PYTEST_TIMEOUT_SECONDS,
    TEST_CONFTEST_FILENAME,
)
from pr_loop_shared_constants.preflight_constants import (
    PYTEST_NO_TESTS_COLLECTED_EXIT_CODE,
)
from terminology_sweep import repository_environment

from code_rules_gate_parts.git_file_sets import paths_from_git_staged
from code_rules_gate_parts.wrapper_plumb_check import is_test_path


def _is_conftest_path(file_path: Path) -> bool:
    """Return True when *file_path* is a pytest ``conftest.py`` fixture module."""
    return file_path.name == TEST_CONFTEST_FILENAME


def _pytest_target_paths(all_test_paths: list[Path]) -> list[Path]:
    """Return staged test paths that pytest should collect as targets.

    ::

        ok:   [pkg/test_a.py, pkg/conftest.py] -> [pkg/test_a.py]
        ok:   [a/conftest.py, b/conftest.py]   -> []
        flag: bare confests collected as targets share basename ``conftest``

    Args:
        all_test_paths: Staged paths that match the test-file classifier.

    Returns:
        The same paths with every ``conftest.py`` removed.
    """
    return [
        each_path for each_path in all_test_paths if not _is_conftest_path(each_path)
    ]


def _staged_test_file_paths(repository_root: Path) -> list[Path]:
    """Return the staged Python test files that exist under a repository.

    Args:
        repository_root: The repository root whose staged index is read.

    Returns:
        Staged paths whose extension is Python, whose name matches a test-file
        pattern, and which exist on disk.
    """
    all_test_paths: list[Path] = []
    for each_path in paths_from_git_staged(repository_root):
        if each_path.suffix != PYTHON_FILE_EXTENSION:
            continue
        if is_test_path(str(each_path)) and each_path.is_file():
            all_test_paths.append(each_path)
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


def _walk_to_owning_test_root(
    resolved_test_file_path: Path, resolved_repository_root: Path
) -> tuple[Path, bool]:
    """Walk up once for the owning test root and whether that root holds a config.

    ::

        resolved_repository_root = /repo, holding no pytest config of its own
        ok:   /repo/pkg/pytest.ini above /repo/pkg/suite/test_a.py -> (/repo/pkg, True)
        ok:   /repo/tools/tests/test_b.py                          -> (/repo, False)

    One walk answers both questions a caller has, so the repository root's
    config is read once per staged file rather than once per question.

    Args:
        resolved_test_file_path: The already-resolved staged test file.
        resolved_repository_root: The already-resolved repository root.

    Returns:
        The nearest config-owning ancestor paired with True, or the repository
        root paired with False when no ancestor up to it owns a config.
    """
    for each_ancestor in resolved_test_file_path.parents:
        if _directory_holds_pytest_config(each_ancestor):
            return each_ancestor, True
        if each_ancestor == resolved_repository_root:
            return resolved_repository_root, False
    return resolved_repository_root, False


def _resolve_owning_test_root(test_file_path: Path, repository_root: Path) -> Path:
    """Return the nearest ancestor of *test_file_path* owning a pytest config.

    Args:
        test_file_path: The staged test file to resolve a root for.
        repository_root: The repository root that bounds the upward walk.

    Returns:
        The resolved owning test root directory.
    """
    owning_root, _has_owning_pytest_config = _walk_to_owning_test_root(
        test_file_path.resolve(), repository_root.resolve()
    )
    return owning_root


def _resolved_path_or_none(each_path: Path) -> Path | None:
    """Return *each_path* resolved, or None when the filesystem refuses to resolve it."""
    try:
        return each_path.resolve()
    except OSError:
        return None


def _top_level_group_root(
    resolved_test_file_path: Path, resolved_repository_root: Path
) -> Path:
    """Return the repository top-level directory *resolved_test_file_path* sits under.

    ::

        resolved_repository_root = /repo
        ok:   /repo/tools/tests/test_a.py -> /repo/tools
        ok:   /repo/test_b.py             -> /repo
        ok:   /elsewhere/test_c.py        -> /repo   (outside the repository)

    Args:
        resolved_test_file_path: The already-resolved staged test file to place
            under a top-level directory.
        resolved_repository_root: The already-resolved repository root.

    Returns:
        The repository root joined to the file's first repository-relative path
        component; the repository root itself for a file sitting directly at it
        or outside it.
    """
    try:
        repository_relative_path = resolved_test_file_path.relative_to(resolved_repository_root)
    except ValueError:
        return resolved_repository_root
    all_relative_parts = repository_relative_path.parts
    if len(all_relative_parts) <= 1:
        return resolved_repository_root
    return resolved_repository_root / all_relative_parts[0]


def _group_root_for_test_file(test_file_path: Path, repository_root: Path) -> Path:
    """Return the pytest session root *test_file_path* runs under.

    ::

        repository_root = /repo, holding no pytest config of its own
        ok:   /repo/pkg/pytest.ini next to /repo/pkg/suite/test_a.py -> /repo/pkg
        ok:   /repo/tools/tests/test_b.py                            -> /repo/tools
        ok:   /repo/test_c.py                                        -> /repo
        flag: /repo/tools/... and /repo/pipeline/... in one /repo bucket

    A config-owning ancestor always wins. A file no ancestor config owns falls
    back to its top-level directory, so two config-less packages exposing a
    same-named top-level module run in separate pytest processes rather than
    shadowing each other in one. A staged path the filesystem refuses to
    resolve joins the repository-root group instead of aborting the gate.

    Args:
        test_file_path: The staged test file to place in a group.
        repository_root: The repository root that bounds the upward walk.

    Returns:
        The config-owning ancestor when one exists, the repository root when the
        root owns the config or the path fails to resolve, else the file's
        top-level directory.
    """
    resolved_repository_root = repository_root.resolve()
    resolved_test_file_path = _resolved_path_or_none(test_file_path)
    if resolved_test_file_path is None:
        return resolved_repository_root
    owning_root, has_owning_pytest_config = _walk_to_owning_test_root(
        resolved_test_file_path, resolved_repository_root
    )
    if has_owning_pytest_config:
        return owning_root
    return _top_level_group_root(resolved_test_file_path, resolved_repository_root)


def _group_staged_tests_by_root(
    all_test_paths: list[Path], repository_root: Path
) -> dict[Path, list[Path]]:
    """Group *all_test_paths* by the pytest session root that runs them.

    Args:
        all_test_paths: The staged test files to partition.
        repository_root: The repository root that bounds each upward walk.

    Returns:
        A mapping from group root to the staged test files running under it.
        Every input path lands in exactly one group.
    """
    all_tests_by_root: dict[Path, list[Path]] = {}
    for each_test_path in all_test_paths:
        group_root = _group_root_for_test_file(each_test_path, repository_root)
        all_tests_by_root.setdefault(group_root, []).append(each_test_path)
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


def _staged_pytest_environment() -> dict[str, str]:
    """Return the subprocess environment for the staged-test pytest run.

    Returns:
        The ``repository_environment`` mapping, with ``CODE_RULES_GATE_PYTHONPATH``
        prepended to ``PYTHONPATH`` when it is set.
    """
    environment = repository_environment()
    configured_pythonpath = os.environ.get(CODE_RULES_GATE_PYTHONPATH_ENV_VAR)
    if not configured_pythonpath:
        return environment
    existing_pythonpath = environment.get(PYTHONPATH_ENV_VAR, "")
    environment[PYTHONPATH_ENV_VAR] = (
        configured_pythonpath
        if not existing_pythonpath
        else os.pathsep.join([configured_pythonpath, existing_pythonpath])
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
    environment: dict[str, str],
    junit_xml_path: Path | None = None,
) -> int:
    """Run one pytest invocation and normalize its exit code.

    Args:
        all_batch_command: The full argv for this pytest invocation.
        group_root: The owning test root used as the working directory.
        environment: The environment the pytest subprocess runs under, which
            decides where its imports resolve from.
        junit_xml_path: When given, the batch also writes a JUnit XML report
            here (via ``--junitxml``), for a caller that needs the per-test
            pass/fail identities alongside the exit code.

    Returns:
        0 when the batch passes or collects no tests; pytest's exit code
        otherwise.
    """
    full_command = list(all_batch_command)
    if junit_xml_path is not None:
        full_command.append(f"{JUNIT_XML_FLAG_PREFIX}{junit_xml_path}")
    pytest_process = subprocess.run(
        full_command,
        cwd=str(group_root),
        timeout=STAGED_PYTEST_TIMEOUT_SECONDS,
        check=False,
        env=environment,
    )
    if pytest_process.returncode == PYTEST_NO_TESTS_COLLECTED_EXIT_CODE:
        return 0
    return pytest_process.returncode


def _pytest_fixed_command(repository_root: Path) -> list[str]:
    """Return the interpreter-and-pytest prefix shared by every batch."""
    return [
        _resolve_gate_python_executable(repository_root),
        *ALL_PYTEST_MODULE_INVOCATION,
    ]


def _first_failing_batch_exit_code(
    all_fixed_command: list[str],
    all_batches: list[list[str]],
    group_root: Path,
    environment: dict[str, str],
    junit_xml_dir: Path | None = None,
) -> int:
    """Run each batch and return the first non-zero pytest exit code, or zero.

    Args:
        all_fixed_command: The interpreter-and-pytest prefix shared by every batch.
        all_batches: The command-line-length-safe argument batches to run in order.
        group_root: The owning test root used as the working directory.
        environment: The environment every pytest subprocess runs under.
        junit_xml_dir: When given, each batch also writes its own JUnit XML report
            here (one file per batch index), for a caller that needs per-test
            pass/fail identities alongside the exit code.

    Returns:
        0 when every batch passes or collects no tests; the first non-zero batch
        exit code otherwise.
    """
    first_failing_exit_code = 0
    for batch_index, each_batch in enumerate(all_batches):
        junit_xml_path = (
            junit_xml_dir / f"batch_{batch_index}.xml" if junit_xml_dir is not None else None
        )
        batch_exit_code = _pytest_batch_exit_code(
            [*all_fixed_command, *each_batch],
            group_root,
            environment,
            junit_xml_path=junit_xml_path,
        )
        if batch_exit_code != 0 and first_failing_exit_code == 0:
            first_failing_exit_code = batch_exit_code
    return first_failing_exit_code


def _run_pytest_for_group(
    group_root: Path,
    all_group_test_paths: list[Path],
    repository_root: Path,
    junit_xml_dir: Path | None = None,
    environment: dict[str, str] | None = None,
) -> int:
    """Run pytest over one group's test files, split into budget-safe batches.

    Args:
        group_root: The owning test root used as the pytest working directory.
        all_group_test_paths: The staged test files that share *group_root*.
        repository_root: The repository root used to resolve a project venv.
        junit_xml_dir: When given, a JUnit XML report is written per batch under
            this directory, for a caller that needs per-test pass/fail identities
            (the regression gate) alongside the exit code.
        environment: When given, the environment every pytest subprocess runs
            under; the regression gate passes a baseline environment here so the
            HEAD run resolves its imports inside the baseline worktree. Defaults
            to the staged environment.

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
    return _first_failing_batch_exit_code(
        all_fixed_command,
        all_batches,
        group_root,
        _staged_pytest_environment() if environment is None else environment,
        junit_xml_dir=junit_xml_dir,
    )
