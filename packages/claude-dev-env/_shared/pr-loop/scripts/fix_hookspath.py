import argparse
import subprocess
import sys
from pathlib import Path

parent_directory = str(Path(__file__).resolve().parent)
if parent_directory not in sys.path:
    sys.path.insert(0, parent_directory)

from pr_loop_shared_constants.fix_hookspath_constants import (  # noqa: E402
    ALL_CANONICAL_HOOKS_DIRECTORY_COMPONENTS,
    ALL_GIT_GLOBAL_GET_CORE_HOOKS_PATH_COMMAND,
    ALL_HOME_ENV_VAR_NAMES,
    HOOKS_PATH_SUFFIX,
    PREFLIGHT_NO_PYTEST_FLAG,
    PREFLIGHT_REPO_ROOT_FLAG,
)
from pr_loop_shared_constants.preflight_constants import GIT_DIRECTORY_NAME  # noqa: E402


def resolve_canonical_hooks_directory(
    all_environment_overrides: dict[str, str] | None,
) -> Path:
    """Return the canonical claude-dev-env git hooks directory path.

    Args:
        all_environment_overrides: Optional environment variable mapping used
            to discover the user's home directory (HOME / USERPROFILE).

    Returns:
        The absolute path to the canonical hooks directory beneath the
        resolved home location.
    """
    if all_environment_overrides is not None:
        for each_env_var_name in ALL_HOME_ENV_VAR_NAMES:
            home_value = all_environment_overrides.get(each_env_var_name)
            if home_value:
                return Path(home_value).joinpath(*ALL_CANONICAL_HOOKS_DIRECTORY_COMPONENTS)
    return Path.home().joinpath(*ALL_CANONICAL_HOOKS_DIRECTORY_COMPONENTS)


def list_local_core_hooks_path_values(
    repository_root: Path,
    all_environment_overrides: dict[str, str] | None,
) -> list[str]:
    """Return all repo-local ``core.hooksPath`` values configured on the repo.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        all_environment_overrides: Optional environment variable mapping
            forwarded to ``subprocess.run``.

    Returns:
        Non-empty stripped values from ``git config --local --get-all``, or
        an empty list when no values are configured.
    """
    git_command = [
        "git",
        "-C",
        str(repository_root),
        "config",
        "--local",
        "--get-all",
        "core.hooksPath",
    ]
    completed_process = subprocess.run(
        git_command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=all_environment_overrides,
    )
    if completed_process.returncode != 0:
        diagnostic_stderr = completed_process.stderr.strip()
        if diagnostic_stderr:
            print(
                "fix_hookspath: git read of local core.hooksPath on "
                f"{repository_root} exited {completed_process.returncode}: "
                f"{diagnostic_stderr}",
                file=sys.stderr,
            )
        return []
    return [
        each_line.strip()
        for each_line in completed_process.stdout.splitlines()
        if each_line.strip()
    ]


def read_global_core_hooks_path(
    all_environment_overrides: dict[str, str] | None,
) -> str:
    """Return the global-scope ``core.hooksPath`` value from git config.

    Args:
        all_environment_overrides: Optional environment variable mapping
            forwarded to ``subprocess.run``.

    Returns:
        The stripped global value, or an empty string when unset or when git
        returns non-zero.
    """
    git_command = list(ALL_GIT_GLOBAL_GET_CORE_HOOKS_PATH_COMMAND)
    completed_process = subprocess.run(
        git_command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=all_environment_overrides,
    )
    if completed_process.returncode != 0:
        diagnostic_stderr = completed_process.stderr.strip()
        if diagnostic_stderr:
            print(
                "fix_hookspath: git read of global core.hooksPath exited "
                f"{completed_process.returncode}: {diagnostic_stderr}",
                file=sys.stderr,
            )
        return ""
    return completed_process.stdout.strip()


def unset_local_core_hooks_path(
    repository_root: Path,
    all_environment_overrides: dict[str, str] | None,
) -> int:
    """Remove every repo-local ``core.hooksPath`` entry from the repo config.

    Args:
        repository_root: Repository root used as the ``git -C`` target.
        all_environment_overrides: Optional environment variable mapping
            forwarded to ``subprocess.run``.

    Returns:
        The ``git config --unset-all`` exit code (zero on success).
    """
    git_command = [
        "git",
        "-C",
        str(repository_root),
        "config",
        "--local",
        "--unset-all",
        "core.hooksPath",
    ]
    completed_process = subprocess.run(
        git_command,
        capture_output=True,
        text=True,
        check=False,
        env=all_environment_overrides,
    )
    return completed_process.returncode


def set_global_core_hooks_path(
    target_value: str,
    all_environment_overrides: dict[str, str] | None,
) -> int:
    """Write the global-scope ``core.hooksPath`` value into git config.

    Args:
        target_value: Path value to install at global scope.
        all_environment_overrides: Optional environment variable mapping
            forwarded to ``subprocess.run``.

    Returns:
        The ``git config --global`` exit code (zero on success).
    """
    git_command = ["git", "config", "--global", "core.hooksPath", target_value]
    completed_process = subprocess.run(
        git_command,
        capture_output=True,
        text=True,
        check=False,
        env=all_environment_overrides,
    )
    return completed_process.returncode


def normalize_hooks_path(raw_value: str) -> str:
    return raw_value.replace("\\", "/").rstrip("/")


def is_canonical_hooks_path(raw_value: str) -> bool:
    if not raw_value:
        return False
    return normalize_hooks_path(raw_value).endswith(HOOKS_PATH_SUFFIX)


def find_repository_root(start: Path) -> Path:
    """Walk up from *start* to the nearest directory containing a git marker.

    Args:
        start: The directory to start the upward search from.

    Returns:
        The resolved ancestor that contains a ``.git`` directory or file, or
        the resolved *start* path when no git marker is found.
    """
    resolved_start = start.resolve()
    candidate_paths = [resolved_start, *resolved_start.parents]
    for each_candidate in candidate_paths:
        marker = each_candidate / GIT_DIRECTORY_NAME
        if marker.is_dir() or marker.is_file():
            return each_candidate
    return resolved_start


def rerun_preflight(
    repository_root: Path,
    all_environment_overrides: dict[str, str] | None,
) -> int:
    """Re-invoke ``preflight.py`` after the hooks path has been repaired.

    Args:
        repository_root: Repository root passed through to preflight as
            ``--repo-root``.
        all_environment_overrides: Optional environment variable mapping
            forwarded to ``subprocess.run``.

    Returns:
        The preflight subprocess exit code.
    """
    preflight_script_path = Path(__file__).resolve().parent / "preflight.py"
    rerun_command = [
        sys.executable,
        str(preflight_script_path),
        PREFLIGHT_NO_PYTEST_FLAG,
        PREFLIGHT_REPO_ROOT_FLAG,
        str(repository_root),
    ]
    completed_process = subprocess.run(
        rerun_command,
        check=False,
        env=all_environment_overrides,
    )
    return completed_process.returncode


def parse_arguments(all_arguments: list[str] | None) -> argparse.Namespace:
    """Parse the command-line arguments for the fix_hookspath script.

    Args:
        all_arguments: Command-line argument list, or None to read from
            ``sys.argv``.

    Returns:
        The parsed argparse namespace with a ``repo_root`` attribute.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Auto-fix core.hooksPath when bugteam preflight detects a stale override. "
            "Removes a local-scope override and ensures global core.hooksPath points "
            "at the canonical claude-dev-env git-hooks directory."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root (default: discover from cwd).",
    )
    return parser.parse_args(all_arguments)


def main(
    all_arguments: list[str],
    all_environment_overrides: dict[str, str] | None,
) -> int:
    """Run the fix_hookspath repair routine and re-invoke preflight.

    Args:
        all_arguments: Command-line argument list forwarded to argparse.
        all_environment_overrides: Optional environment variable mapping
            forwarded to every git invocation and to the preflight rerun.

    Returns:
        Zero on success. Non-zero on the first failing git command or on a
        non-zero preflight rerun exit code.
    """
    arguments = parse_arguments(all_arguments)
    start_directory = Path.cwd()
    repository_root = (
        arguments.repo_root.resolve()
        if arguments.repo_root is not None
        else find_repository_root(start_directory)
    )
    canonical_hooks_directory = resolve_canonical_hooks_directory(all_environment_overrides)
    expected_suffix = HOOKS_PATH_SUFFIX
    if not canonical_hooks_directory.is_dir():
        print(
            "fix_hookspath: canonical hooks directory does not exist: "
            f"{canonical_hooks_directory}\n"
            "Run: npx claude-dev-env .\n"
            "Then re-run /bugteam. The directory must end in "
            f"'{expected_suffix}' and contain the claude-dev-env git hook shims.",
            file=sys.stderr,
        )
        return 1
    local_hooks_path_values = list_local_core_hooks_path_values(
        repository_root,
        all_environment_overrides,
    )
    has_non_canonical_local_override = any(
        not is_canonical_hooks_path(each_value)
        for each_value in local_hooks_path_values
    )
    if has_non_canonical_local_override:
        unset_local_returncode = unset_local_core_hooks_path(
            repository_root, all_environment_overrides
        )
        if unset_local_returncode != 0:
            print(
                "fix_hookspath: failed to unset local core.hooksPath on "
                f"{repository_root} (git exit {unset_local_returncode}).",
                file=sys.stderr,
            )
            return 1
        print(
            "fix_hookspath: removed stale local core.hooksPath override on "
            f"{repository_root}",
            file=sys.stderr,
        )
    current_global_value = read_global_core_hooks_path(all_environment_overrides)
    if not is_canonical_hooks_path(current_global_value):
        canonical_target_value = str(canonical_hooks_directory).replace("\\", "/")
        global_set_exit_code = set_global_core_hooks_path(
            canonical_target_value,
            all_environment_overrides,
        )
        if global_set_exit_code != 0:
            print(
                "fix_hookspath: failed to set global core.hooksPath to "
                f"{canonical_target_value} (git exit {global_set_exit_code}).",
                file=sys.stderr,
            )
            return 1
        print(
            f"fix_hookspath: set global core.hooksPath to {canonical_target_value}",
            file=sys.stderr,
        )
    return rerun_preflight(repository_root, all_environment_overrides)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:], None))
