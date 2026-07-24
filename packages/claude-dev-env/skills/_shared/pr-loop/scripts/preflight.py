import argparse
import os
import subprocess
import sys
from pathlib import Path

parent_directory = str(Path(__file__).resolve().parent)
sys.path[:] = [
    each_existing_entry
    for each_existing_entry in sys.path
    if not (
        os.path.exists(each_existing_entry)
        and os.path.samefile(each_existing_entry, parent_directory)
    )
]
if parent_directory not in sys.path:
    sys.path.insert(0, parent_directory)

from pr_loop_shared_constants.fix_hookspath_constants import HOOKS_PATH_VERIFICATION_SUFFIX  # noqa: E402
from pr_loop_shared_constants.preflight_constants import (
    ALL_GIT_CONFIG_GET_CORE_HOOKS_PATH_SUBCOMMAND,
    ALL_GIT_DIFF_NAME_ONLY_SUBCOMMAND,
    ALL_GIT_LS_FILES_TEST_DISCOVERY_SUBCOMMAND,
    ALL_PRE_COMMIT_RUN_ALL_FILES_COMMAND,
    BUGTEAM_PREFLIGHT_SKIP_ENABLED_VALUE,
    BUGTEAM_PREFLIGHT_SKIP_ENV_VAR_NAME,
    GIT_DIRECTORY_NAME,
    PRE_COMMIT_CONFIG_YAML_FILENAME,
    PYPROJECT_TOML_FILENAME,
    PYTEST_FAILED_FIRST_FLAG,
    PYTEST_INI_FILENAME,
    ALL_PYTEST_SCOPE_CHOICES,
    PYTEST_NO_TESTS_COLLECTED_EXIT_CODE,
    PYTEST_SCOPE_ALL,
    PYTEST_SCOPE_CHANGED,
    PYTEST_TEST_FILENAME_PREFIX,
    PYTEST_TEST_FILENAME_SUFFIX,
    PYTEST_TOML_TABLE_PREFIX,
    PYTHON_FILE_SUFFIX,
    TESTS_DIRECTORY_NAME,
)
from preflight_self_heal import silently_clear_stale_local_hooks_path_override  # noqa: E402
from reviews_disabled import (
    CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN,
    CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME,
    EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV,
    is_bugteam_disabled_via_env,
)


def verify_git_hooks_path(repository_root: Path | None = None) -> int:
    """Check that core.hooksPath resolves to the claude-dev-env git-hooks directory.

    Silently clears any stale, non-canonical local-scope core.hooksPath
    override before querying the effective config, so a worktree-seeded local
    entry cannot shadow a correctly configured global setting. When
    *repository_root* is provided, queries the effective config for that
    repository (``git -C <root> config --get``). When a canonical global
    ``core.hooksPath`` is already configured, the preceding self-heal step
    clears non-canonical local-scope entries, so repo-level overrides such
    as Husky or lefthook at local scope are silently removed in favor of
    the canonical global; when the global is unset or non-canonical, the
    self-heal stands down and the ``--get`` query still surfaces those
    overrides through the failure path. Falls back to the current working
    directory's effective config when *repository_root* is None.

    Args:
        repository_root: Optional repository root to check. When None, uses
            the current working directory's effective config.

    Returns:
        Zero when the configured path ends with the expected hooks suffix.
        Non-zero and prints a correction message when unset or pointing elsewhere.
    """
    expected_hooks_path_suffix = HOOKS_PATH_VERIFICATION_SUFFIX
    silently_clear_stale_local_hooks_path_override(
        repository_root, expected_hooks_path_suffix
    )
    enforcement_absent_message = (
        "Git-side CODE_RULES enforcement is not active on this host.\n"
        "Run: npx claude-dev-env .\n"
        "Or set core.hooksPath at any scope, e.g.:\n"
        "  git config --global core.hooksPath ~/.claude/hooks/git-hooks"
    )
    git_command: list[str] = ["git"]
    if repository_root is not None:
        git_command.extend(["-C", str(repository_root)])
    git_command.extend(list(ALL_GIT_CONFIG_GET_CORE_HOOKS_PATH_SUBCOMMAND))
    try:
        query_completed_process = subprocess.run(
            git_command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        print(
            "bugteam_preflight: git is not installed or not available on PATH.\n"
            f"{enforcement_absent_message}",
            file=sys.stderr,
        )
        return 1
    except OSError as os_error:
        print(
            f"bugteam_preflight: failed to run git: {os_error}\n"
            f"{enforcement_absent_message}",
            file=sys.stderr,
        )
        return 1
    if query_completed_process.returncode != 0:
        print(
            f"bugteam_preflight: {enforcement_absent_message}",
            file=sys.stderr,
        )
        return 1
    configured_path = query_completed_process.stdout.strip().replace("\\", "/").rstrip("/")
    if not configured_path.endswith(expected_hooks_path_suffix):
        print(
            f"bugteam_preflight: core.hooksPath is '{configured_path}' — "
            f"expected path ending in '{expected_hooks_path_suffix}'.\n"
            f"{enforcement_absent_message}",
            file=sys.stderr,
        )
        return 1
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
    all_candidates = [resolved, *resolved.parents]
    for each_candidate in all_candidates:
        git_marker = each_candidate / GIT_DIRECTORY_NAME
        if git_marker.is_dir() or git_marker.is_file():
            return each_candidate
    for each_candidate in all_candidates:
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
    pyproject = root / PYPROJECT_TOML_FILENAME
    if not pyproject.is_file():
        return False
    text = pyproject.read_text(encoding="utf-8", errors="replace")
    return PYTEST_TOML_TABLE_PREFIX in text


def has_discoverable_tests(root: Path) -> bool | None:
    """Check whether the repository contains discoverable test files via git ls-files.

    When the root has no ``.git`` marker, returns True without invoking git.
    Otherwise asks git for tracked plus untracked test files matching the
    discovery patterns, respecting ``.gitignore``.

    Args:
        root: The directory tree root to search.

    Returns:
        True when at least one matching test file is found. False when git
        succeeds and returns an empty list. None when git is unavailable or
        the ls-files invocation fails.
    """
    git_marker = root / GIT_DIRECTORY_NAME
    if not (git_marker.is_dir() or git_marker.is_file()):
        return True
    command = ["git", "-C", str(root), *ALL_GIT_LS_FILES_TEST_DISCOVERY_SUBCOMMAND]
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True,
        )
    except FileNotFoundError:
        print(
            "bugteam_preflight: git is not installed or not available on PATH.",
            file=sys.stderr,
        )
        return None
    except subprocess.CalledProcessError as error:
        error_detail = (error.stderr or "").strip()
        print(
            f"bugteam_preflight: git ls-files failed (exit {error.returncode}):"
            + (f"\n{error_detail}" if error_detail else ""),
            file=sys.stderr,
        )
        return None
    except OSError as error:
        print(
            f"bugteam_preflight: failed to run git ls-files: {error}",
            file=sys.stderr,
        )
        return None
    return bool(completed.stdout.strip())


def _pytest_exit_code_no_tests_collected() -> int:
    pytest_no_tests_collected_exit_code = PYTEST_NO_TESTS_COLLECTED_EXIT_CODE
    return pytest_no_tests_collected_exit_code


def run_pytest(
    repository_root: Path,
    verbose: bool,
    all_test_paths: list[Path] | None = None,
) -> int:
    """Run pytest in the repository root and return the exit code.

    Passes ``--ff`` (failed-first) and ``-q`` unless *verbose* is True. When
    *all_test_paths* is provided, restricts the run to those paths via the
    ``--`` positional separator so pytest does not misinterpret leading
    hyphens as options. Treats the "no tests collected" exit code as a pass.

    Args:
        repository_root: The repository root for running pytest.
        verbose: When True, omit ``-q`` so individual test names show.
        all_test_paths: Optional list of test paths to restrict the run.

    Returns:
        The pytest exit code, or 0 when no tests were collected.
    """
    command = [sys.executable, "-m", "pytest", PYTEST_FAILED_FIRST_FLAG]
    if not verbose:
        command.append("-q")
    if all_test_paths is not None:
        command.append("--")
        command.extend(str(each_path) for each_path in all_test_paths)
    completed = subprocess.run(
        command,
        cwd=str(repository_root),
        check=False,
    )
    if completed.returncode == _pytest_exit_code_no_tests_collected():
        return 0
    return completed.returncode


def get_changed_files(repository_root: Path, base_ref: str) -> list[Path] | None:
    """Return the list of files changed between *base_ref* and HEAD.

    Refuses base refs beginning with ``-`` to prevent option injection into
    git diff. Logs a warning and returns None on every failure path so the
    caller can fall back to running the full suite.

    Args:
        repository_root: The repository root for running git diff.
        base_ref: The git base ref to diff against (e.g., ``origin/main``).

    Returns:
        A list of relative file paths changed vs *base_ref*. None when
        *base_ref* is invalid or git diff fails.
    """
    if base_ref.startswith("-"):
        print(
            f"bugteam_preflight: invalid base_ref '{base_ref}' starts "
            f"with hyphen; falling back to full suite.",
            file=sys.stderr,
        )
        return None
    command = [
        "git",
        *ALL_GIT_DIFF_NAME_ONLY_SUBCOMMAND,
        f"{base_ref}...HEAD",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=str(repository_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except FileNotFoundError:
        print(
            "bugteam_preflight: git is not installed or not available on PATH.\n"
            f"bugteam_preflight: cannot determine changed files against "
            f"{base_ref}; falling back to full suite.",
            file=sys.stderr,
        )
        return None
    except OSError as os_error:
        print(
            f"bugteam_preflight: failed to run git: {os_error}\n"
            f"bugteam_preflight: cannot determine changed files against "
            f"{base_ref}; falling back to full suite.",
            file=sys.stderr,
        )
        return None
    if completed.returncode != 0:
        print(
            f"bugteam_preflight: git diff against {base_ref} failed "
            f"(exit {completed.returncode}); falling back to full suite.\n"
            f"{completed.stderr.strip()}",
            file=sys.stderr,
        )
        return None
    return [
        Path(each_line.strip())
        for each_line in completed.stdout.splitlines()
        if each_line.strip()
    ]


def _find_related_test_files(changed_path: Path, repository_root: Path) -> list[Path]:
    if changed_path.suffix != PYTHON_FILE_SUFFIX:
        return []
    stem = changed_path.stem
    test_prefix = PYTEST_TEST_FILENAME_PREFIX
    test_suffix = PYTEST_TEST_FILENAME_SUFFIX
    if (stem.startswith(test_prefix) or stem.endswith(test_suffix)) and (
        repository_root / changed_path
    ).is_file():
        return [repository_root / changed_path]
    full_path = repository_root / changed_path
    parent = full_path.parent
    adjacent_tests = parent / TESTS_DIRECTORY_NAME
    top_tests = repository_root / TESTS_DIRECTORY_NAME
    relative_parent = changed_path.parent
    python_suffix = PYTHON_FILE_SUFFIX
    all_candidates = [
        parent / f"{test_prefix}{stem}{python_suffix}",
        parent / f"{stem}{test_suffix}{python_suffix}",
        adjacent_tests / f"{test_prefix}{stem}{python_suffix}",
        adjacent_tests / f"{stem}{test_suffix}{python_suffix}",
    ]
    if relative_parent != Path("."):
        all_candidates.extend([
            top_tests / relative_parent / f"{test_prefix}{stem}{python_suffix}",
            top_tests / relative_parent / f"{stem}{test_suffix}{python_suffix}",
        ])
    return sorted({each_candidate for each_candidate in all_candidates if each_candidate.is_file()})


def discover_related_tests(
    all_changed_files: list[Path], repository_root: Path
) -> list[Path]:
    """Discover all test files related to the given changed files.

    Walks every changed path through :func:`_find_related_test_files` and
    returns the sorted, de-duplicated union.

    Args:
        all_changed_files: The list of changed source files to map to tests.
        repository_root: The repository root for resolving relative paths.

    Returns:
        Sorted list of unique related test file paths.
    """
    related: set[Path] = set()
    for each_file in all_changed_files:
        related.update(_find_related_test_files(each_file, repository_root))
    return sorted(related)


def run_pre_commit(repository_root: Path) -> int:
    """Run pre-commit on all files and return its exit code.

    Args:
        repository_root: The repository root for running pre-commit.

    Returns:
        The pre-commit exit code (0 on success, non-zero on failure).
    """
    completed = subprocess.run(
        list(ALL_PRE_COMMIT_RUN_ALL_FILES_COMMAND),
        cwd=str(repository_root),
        check=False,
    )
    return completed.returncode


def parse_arguments(all_arguments: list[str]) -> argparse.Namespace:
    """Parse command-line arguments for the preflight script.

    Args:
        all_arguments: Command-line argument list.

    Returns:
        Parsed namespace with repo_root, no_pytest, pre_commit, verbose,
        base_ref, and scope attributes.
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
        help=f"Run pre-commit when {PRE_COMMIT_CONFIG_YAML_FILENAME} exists.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Verbose pytest output.",
    )
    parser.add_argument(
        "--base-ref",
        type=str,
        default=None,
        help=(
            "Git base ref for scoped test selection (e.g., origin/main). "
            "When set, only tests related to files changed vs this ref are run."
        ),
    )
    parser.add_argument(
        "--scope",
        type=str,
        choices=list(ALL_PYTEST_SCOPE_CHOICES),
        default=None,
        help=(
            "Test selection scope. 'all' runs the full suite. "
            "'changed' runs only tests related to changed files (requires --base-ref). "
            "Defaults to 'changed' when --base-ref is provided, 'all' otherwise."
        ),
    )
    return parser.parse_args(all_arguments)


def main(all_arguments: list[str]) -> int:
    """Run the preflight checks (git-hooks path, pytest, optional pre-commit).

    Args:
        all_arguments: Command-line argument list to forward to argparse.

    Returns:
        Zero on success. Non-zero exit code on the first failing check.
        Returns :data:`EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV` when
        ``CLAUDE_REVIEWS_DISABLED`` lists the ``bugteam`` token.
    """
    arguments = parse_arguments(all_arguments)
    skip_env_var_name = BUGTEAM_PREFLIGHT_SKIP_ENV_VAR_NAME
    skip_enabled_value = BUGTEAM_PREFLIGHT_SKIP_ENABLED_VALUE
    if os.environ.get(skip_env_var_name, "").strip() == skip_enabled_value:
        print(
            f"bugteam_preflight: skipped ({skip_env_var_name}={skip_enabled_value}).",
            file=sys.stderr,
        )
        return 0
    reviews_disabled_env_var_name = CLAUDE_REVIEWS_DISABLED_ENV_VAR_NAME
    reviews_disabled_bugteam_token = CLAUDE_REVIEWS_DISABLED_BUGTEAM_TOKEN
    disabled_via_env_exit_code = EXIT_CODE_BUGTEAM_DISABLED_VIA_ENV
    if is_bugteam_disabled_via_env():
        print(
            f"bugteam_preflight: halted "
            f"({reviews_disabled_env_var_name} contains "
            f"'{reviews_disabled_bugteam_token}').",
            file=sys.stderr,
        )
        return disabled_via_env_exit_code
    start = Path.cwd()
    repository_root = (
        arguments.repo_root.resolve()
        if arguments.repo_root is not None
        else find_repository_root(start)
    )
    hooks_path_exit_code = verify_git_hooks_path(repository_root)
    if hooks_path_exit_code != 0:
        return hooks_path_exit_code
    discovery_result: bool | None = True
    if not arguments.no_pytest and has_pytest_configuration(repository_root):
        discovery_result = has_discoverable_tests(repository_root)
        if discovery_result is None:
            print(
                "bugteam_preflight: test discovery failed; running full suite anyway.",
                file=sys.stderr,
            )
        elif not discovery_result:
            print(
                "bugteam_preflight: pytest configured but no tests found; skipping pytest.",
                file=sys.stderr,
            )
        if discovery_result is not False:
            effective_scope = arguments.scope
            if discovery_result is None:
                effective_scope = PYTEST_SCOPE_ALL
            if effective_scope is None:
                effective_scope = (
                    PYTEST_SCOPE_CHANGED
                    if arguments.base_ref is not None
                    else PYTEST_SCOPE_ALL
                )
            if effective_scope == PYTEST_SCOPE_CHANGED and arguments.base_ref is None:
                print(
                    "bugteam_preflight: --scope changed requires --base-ref; "
                    "falling back to full suite.",
                    file=sys.stderr,
                )
                effective_scope = PYTEST_SCOPE_ALL
            if effective_scope == PYTEST_SCOPE_CHANGED and arguments.base_ref is not None:
                all_changed = get_changed_files(repository_root, arguments.base_ref)
                if all_changed is None:
                    exit_code = run_pytest(repository_root, arguments.verbose)
                else:
                    all_related = discover_related_tests(all_changed, repository_root)
                    if all_related:
                        print(
                            f"bugteam_preflight: running {len(all_related)} test(s) "
                            f"related to changed files (scope=changed).",
                            file=sys.stderr,
                        )
                        exit_code = run_pytest(
                            repository_root, arguments.verbose, all_related
                        )
                    else:
                        print(
                            "bugteam_preflight: no related tests found; "
                            "running full suite.",
                            file=sys.stderr,
                        )
                        exit_code = run_pytest(repository_root, arguments.verbose)
            else:
                exit_code = run_pytest(repository_root, arguments.verbose)
            if exit_code != 0:
                return exit_code
    elif not arguments.no_pytest and discovery_result is not False:
        print(
            "bugteam_preflight: no pytest configuration found; skipping pytest.",
            file=sys.stderr,
        )
    if arguments.pre_commit and (repository_root / PRE_COMMIT_CONFIG_YAML_FILENAME).is_file():
        exit_code = run_pre_commit(repository_root)
        if exit_code != 0:
            return exit_code
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
