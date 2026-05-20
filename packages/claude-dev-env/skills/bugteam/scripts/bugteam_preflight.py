from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

_bugteam_scripts_directory = str(Path(__file__).absolute().parent)
while _bugteam_scripts_directory in sys.path:
    sys.path.remove(_bugteam_scripts_directory)
if _bugteam_scripts_directory not in sys.path:
    sys.path.insert(0, _bugteam_scripts_directory)

from bugteam_scripts_constants.bugteam_preflight_constants import (
    ALL_DISCOVERY_IGNORE_DIRECTORIES,
    ALL_GIT_CONFIG_HOOKS_PATH_ARGUMENTS,
    ALL_PRE_COMMIT_ARGUMENTS,
    BUGTEAM_PREFLIGHT_PREFIX,
    BUGTEAM_PREFLIGHT_SKIP_ENV_VAR_NAME,
    ENFORCEMENT_ABSENT_MESSAGE,
    EXIT_CODE_HOOKS_PATH_CHECK_FAILED,
    EXPECTED_HOOKS_PATH_SUFFIX,
    GIT_DIRECTORY_NAME,
    PRE_COMMIT_CONFIG_FILENAME,
    PYPROJECT_FILENAME,
    PYPROJECT_PYTEST_SECTION_PREFIX,
    PYTEST_EXIT_CODE_NO_TESTS_COLLECTED,
    PYTEST_INI_FILENAME,
)

_shared_pr_loop_scripts_directory = (
    Path(__file__).absolute().parent
    / ".." / ".." / ".." / "_shared" / "pr-loop" / "scripts"
).absolute()
if str(_shared_pr_loop_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_shared_pr_loop_scripts_directory))

from reviews_disabled import (
    CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN,
    CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME,
    EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV,
    is_bugteam_disabled_via_env,
)


def verify_git_hooks_path(repository_root: Path | None) -> int:
    """Check that core.hooksPath resolves to the claude-dev-env git-hooks directory.

    When *repository_root* is provided, queries the effective config for that
    repository (``git -C <root> config --get``), which detects repo-level
    overrides such as Husky or lefthook. Falls back to the current working
    directory's effective config when *repository_root* is None.

    Args:
        repository_root: Optional repository root to check. When None, uses
            the current working directory's effective config.

    Returns:
        Zero when the configured path ends with the expected hooks suffix.
        Non-zero and prints a correction message when unset or pointing elsewhere.
    """
    git_command: list[str] = ["git"]
    if repository_root is not None:
        git_command.extend(["-C", str(repository_root)])
    git_command.extend(list(ALL_GIT_CONFIG_HOOKS_PATH_ARGUMENTS))
    try:
        query_result = subprocess.run(
            git_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        print(
            f"{BUGTEAM_PREFLIGHT_PREFIX}git is not installed or not available on PATH.\n"
            f"{ENFORCEMENT_ABSENT_MESSAGE}",
            file=sys.stderr,
        )
        return EXIT_CODE_HOOKS_PATH_CHECK_FAILED
    except OSError as os_error:
        print(
            f"{BUGTEAM_PREFLIGHT_PREFIX}failed to run git: {os_error}\n"
            f"{ENFORCEMENT_ABSENT_MESSAGE}",
            file=sys.stderr,
        )
        return EXIT_CODE_HOOKS_PATH_CHECK_FAILED
    if query_result.returncode != 0:
        print(
            f"{BUGTEAM_PREFLIGHT_PREFIX}{ENFORCEMENT_ABSENT_MESSAGE}",
            file=sys.stderr,
        )
        return EXIT_CODE_HOOKS_PATH_CHECK_FAILED
    configured_path = query_result.stdout.strip().replace("\\", "/").rstrip("/")
    if not configured_path.endswith(EXPECTED_HOOKS_PATH_SUFFIX):
        print(
            f"{BUGTEAM_PREFLIGHT_PREFIX}core.hooksPath is '{configured_path}' — "
            f"expected path ending in '{EXPECTED_HOOKS_PATH_SUFFIX}'.\n"
            f"{ENFORCEMENT_ABSENT_MESSAGE}",
            file=sys.stderr,
        )
        return EXIT_CODE_HOOKS_PATH_CHECK_FAILED
    return 0


def find_repository_root(start: Path) -> Path:
    """Find the repository root by walking up from the starting directory.

    Searches for a ``.git`` directory or file in parent directories. Falls
    back to the nearest ancestor containing ``pytest.ini`` when no git
    repository is found.

    Args:
        start: The directory to start searching from.

    Returns:
        The repository root path, or *start* when no repository is found.
    """
    resolved = start.resolve()
    candidates = [resolved, *resolved.parents]
    for each_candidate in candidates:
        if (each_candidate / GIT_DIRECTORY_NAME).is_dir() or (each_candidate / GIT_DIRECTORY_NAME).is_file():
            return each_candidate
    for each_candidate in candidates:
        if (each_candidate / PYTEST_INI_FILENAME).is_file():
            return each_candidate
    return resolved


def has_pytest_configuration(root: Path) -> bool:
    """Check whether a directory has pytest configuration available.

    Checks for ``pytest.ini`` directly, then falls back to searching for
    ``[tool.pytest]`` in ``pyproject.toml``.

    Args:
        root: The directory to check for pytest configuration.

    Returns:
        True when pytest configuration is found in either location.
    """
    if (root / PYTEST_INI_FILENAME).is_file():
        return True
    pyproject = root / PYPROJECT_FILENAME
    if not pyproject.is_file():
        return False
    text = pyproject.read_text(encoding="utf-8", errors="replace")
    return PYPROJECT_PYTEST_SECTION_PREFIX in text


def has_discoverable_tests(root: Path) -> bool:
    """Check whether the directory tree contains discoverable test files.

    Searches for files matching ``test_*.py`` and ``*_test.py`` patterns,
    skipping directories in the configured ignore list (virtual environments,
    node_modules).

    Args:
        root: The directory tree root to search.

    Returns:
        True when at least one test file is found outside ignored directories.
    """
    for each_path in root.rglob("test_*.py"):
        if any(part_dir in ALL_DISCOVERY_IGNORE_DIRECTORIES for part_dir in each_path.parts):
            continue
        return True
    for each_path in root.rglob("*_test.py"):
        if any(part_dir in ALL_DISCOVERY_IGNORE_DIRECTORIES for part_dir in each_path.parts):
            continue
        return True
    return False


def _pytest_exit_code_no_tests_collected() -> int:
    return PYTEST_EXIT_CODE_NO_TESTS_COLLECTED


def run_pytest(repository_root: Path, verbose: bool) -> int:
    """Run pytest in the repository root and return the exit code.

    Treats the "no tests collected" exit code as a pass (exit 0).

    Args:
        repository_root: The repository root for running pytest.
        verbose: When True, pass no -q flag (shows individual test names).

    Returns:
        The pytest exit code, or 0 when no tests were collected.
    """
    command = [sys.executable, "-m", "pytest"]
    if not verbose:
        command.append("-q")
    completed = subprocess.run(
        command,
        cwd=str(repository_root),
        check=False,
    )
    if completed.returncode == _pytest_exit_code_no_tests_collected():
        return 0
    return completed.returncode


def run_pre_commit(repository_root: Path) -> int:
    """Run pre-commit on all files and return the exit code.

    Args:
        repository_root: The repository root for running pre-commit.

    Returns:
        The pre-commit exit code (0 on success, non-zero on failure).
    """
    completed = subprocess.run(
        ALL_PRE_COMMIT_ARGUMENTS,
        cwd=str(repository_root),
        check=False,
    )
    return completed.returncode


def parse_arguments(all_argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the preflight script.

    Args:
        all_argv: Command-line argument list.

    Returns:
        Parsed namespace with repo_root, no_pytest, pre_commit, and verbose.
    """
    parser = argparse.ArgumentParser(
        description="Run local checks before /bugteam (pytest, optional pre-commit).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: discover from cwd).",
    )
    parser.add_argument(
        "--no-pytest",
        action="store_true",
        help="Skip pytest.",
    )
    parser.add_argument(
        "--pre-commit",
        action="store_true",
        help="Run pre-commit when .pre-commit-config.yaml exists.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose pytest output.",
    )
    return parser.parse_args(all_argv)


def main(all_argv: list[str] | None = None) -> int:
    """Run the bugteam preflight checks (pytest, optional pre-commit).

    Args:
        all_argv: Command-line arguments to parse. Pass None to use sys.argv.

    Returns:
        Zero on success, non-zero exit code on failure.
    """
    arguments = parse_arguments(sys.argv[1:] if all_argv is None else all_argv)
    if os.environ.get(BUGTEAM_PREFLIGHT_SKIP_ENV_VAR_NAME, "").strip() == "1":
        print(f"{BUGTEAM_PREFLIGHT_PREFIX}skipped (BUGTEAM_PREFLIGHT_SKIP=1).", file=sys.stderr)
        return 0
    reviews_disabled_env_var_name = CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME
    reviews_disabled_bugteam_token = CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN
    disabled_via_env_exit_code = EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV
    if is_bugteam_disabled_via_env():
        print(
            f"{BUGTEAM_PREFLIGHT_PREFIX}halted "
            f"({reviews_disabled_env_var_name} contains "
            f"'{reviews_disabled_bugteam_token}').",
            file=sys.stderr,
        )
        return disabled_via_env_exit_code
    start = Path.cwd()
    resolved_repository_root: Path = (
        arguments.repo_root.resolve()
        if arguments.repo_root is not None
        else find_repository_root(start)
    )
    hooks_path_exit_code = verify_git_hooks_path(resolved_repository_root)
    if hooks_path_exit_code != 0:
        return hooks_path_exit_code
    if not arguments.no_pytest and has_pytest_configuration(resolved_repository_root):
        if not has_discoverable_tests(resolved_repository_root):
            print(
                f"{BUGTEAM_PREFLIGHT_PREFIX}pytest configured but no tests found; skipping pytest.",
                file=sys.stderr,
            )
        else:
            exit_code = run_pytest(resolved_repository_root, arguments.verbose)
            if exit_code != 0:
                return exit_code
    elif not arguments.no_pytest:
        print(
            f"{BUGTEAM_PREFLIGHT_PREFIX}no pytest configuration found; skipping pytest.",
            file=sys.stderr,
        )
    if arguments.pre_commit and (resolved_repository_root / PRE_COMMIT_CONFIG_FILENAME).is_file():
        exit_code = run_pre_commit(resolved_repository_root)
        if exit_code != 0:
            return exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
