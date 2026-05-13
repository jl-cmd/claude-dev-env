from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

for each_cached_module_name in [
    each_module_key
    for each_module_key in list(sys.modules)
    if each_module_key == "config" or each_module_key.startswith("config.")
]:
    sys.modules.pop(each_cached_module_name, None)
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.bugteam_fix_hookspath_constants import (
    ALL_CANONICAL_HOOKS_DIRECTORY_COMPONENTS,
    ALL_GLOBAL_HOOKS_PATH_ARGUMENTS,
    ALL_HOME_ENV_VAR_NAMES,
    GIT_DIRECTORY_NAME,
    HOOKS_PATH_SUFFIX,
    PREFLIGHT_NO_PYTEST_FLAG,
    PREFLIGHT_REPO_ROOT_FLAG,
)


def _expected_hooks_path_suffix() -> str:
    return HOOKS_PATH_SUFFIX


def _canonical_hooks_directory_components() -> tuple[str, str, str]:
    return ALL_CANONICAL_HOOKS_DIRECTORY_COMPONENTS


def _home_env_var_names() -> tuple[str, str]:
    return ALL_HOME_ENV_VAR_NAMES


def resolve_canonical_hooks_directory(
    all_environment_overrides: dict[str, str] | None,
) -> Path:
    """Resolve the canonical hooks directory under the user's home directory.

    When environment overrides are provided, checks HOME/USERPROFILE overrides
    first before falling back to pathlib.Path.home().

    Args:
        all_environment_overrides: Optional dict of environment variable
            overrides for resolving the home directory.

    Returns:
        The resolved Path to the canonical hooks directory.
    """
    components = _canonical_hooks_directory_components()
    if all_environment_overrides is not None:
        for each_env_var_name in _home_env_var_names():
            home_value = all_environment_overrides.get(each_env_var_name)
            if home_value:
                return Path(home_value).joinpath(*components)
    return Path.home().joinpath(*components)


def list_local_core_hooks_path_values(
    repository_root: Path,
    all_environment_overrides: dict[str, str] | None,
) -> list[str]:
    """Retrieve the local core.hooksPath values for a given repository.

    Args:
        repository_root: The repository root for running git config.
        all_environment_overrides: Optional env overrides for git.

    Returns:
        List of local core.hooksPath strings, or empty list when unset.

    Raises:
        RuntimeError: When git emits a non-zero exit with non-empty stderr;
            distinguishes a real git failure from the expected "key unset"
            case (exit 1 with empty stderr).
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
        if completed_process.stderr.strip():
            raise RuntimeError(
                f"git config --local --get-all core.hooksPath failed on "
                f"{repository_root} (exit {completed_process.returncode}): "
                f"{completed_process.stderr.strip()}"
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
    """Read the global core.hooksPath git configuration value.

    Args:
        all_environment_overrides: Optional env overrides for git.

    Returns:
        The global core.hooksPath value, or empty string when unset.

    Raises:
        RuntimeError: When git emits a non-zero exit with non-empty stderr;
            distinguishes a real git failure from the expected "key unset"
            case (exit 1 with empty stderr).
    """
    completed_process = subprocess.run(
        list(ALL_GLOBAL_HOOKS_PATH_ARGUMENTS),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=all_environment_overrides,
    )
    if completed_process.returncode != 0:
        if completed_process.stderr.strip():
            raise RuntimeError(
                f"git config --global --get core.hooksPath failed "
                f"(exit {completed_process.returncode}): "
                f"{completed_process.stderr.strip()}"
            )
        return ""
    return completed_process.stdout.strip()


def unset_local_core_hooks_path(
    repository_root: Path,
    all_environment_overrides: dict[str, str] | None,
) -> int:
    """Remove the local core.hooksPath configuration for a repository.

    Args:
        repository_root: The repository root for running git config.
        all_environment_overrides: Optional env overrides for git.

    Returns:
        The git exit code (0 on success, non-zero on failure).
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
    """Set the global core.hooksPath git configuration value.

    Args:
        target_value: The hooks path value to set globally.
        all_environment_overrides: Optional env overrides for git.

    Returns:
        The git exit code (0 on success, non-zero on failure).
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
    return normalize_hooks_path(raw_value).endswith(_expected_hooks_path_suffix())


def find_repository_root(start: Path) -> Path:
    """Find the repository root by walking up from the starting directory.

    Searches for a ``.git`` directory or file in parent directories.

    Args:
        start: The directory to start searching from.

    Returns:
        The repository root path, or *start* when no repository is found.
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
    """Re-run bugteam_preflight.py after fixing core.hooksPath.

    Args:
        repository_root: The repository root to pass to preflight.
        all_environment_overrides: Optional env overrides for the subprocess.

    Returns:
        The preflight exit code (0 on success, non-zero on failure).
    """
    preflight_script_path = Path(__file__).resolve().parent / "bugteam_preflight.py"
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


def parse_arguments(all_argv: list[str] | None) -> argparse.Namespace:
    """Parse command-line arguments for the hooks-path fix script.

    Args:
        all_argv: Command-line argument list (pass None for defaults).

    Returns:
        Parsed namespace with the repo_root attribute.
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
    return parser.parse_args(all_argv)


def main(
    all_argv: list[str] | None,
    *,
    all_environment_overrides: dict[str, str] | None,
) -> int:
    """Fix core.hooksPath and rerun bugteam preflight.

    Resolves the canonical hooks directory, checks for stale local overrides,
    removes them if found, ensures global core.hooksPath is correct, then
    reruns bugteam_preflight to verify.

    Args:
        all_argv: Command-line arguments to parse.
        all_environment_overrides: Optional environment overrides for git.

    Returns:
        Zero on success, non-zero on failure.
    """
    arguments = parse_arguments(all_argv)
    start_directory = Path.cwd()
    repository_root = (
        arguments.repo_root.resolve()
        if arguments.repo_root is not None
        else find_repository_root(start_directory)
    )
    canonical_hooks_directory = resolve_canonical_hooks_directory(all_environment_overrides)
    expected_suffix = _expected_hooks_path_suffix()
    if not canonical_hooks_directory.is_dir():
        print(
            "bugteam_fix_hookspath: canonical hooks directory does not exist: "
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
                "bugteam_fix_hookspath: failed to unset local core.hooksPath on "
                f"{repository_root} (git exit {unset_local_returncode}).",
                file=sys.stderr,
            )
            return 1
        print(
            "bugteam_fix_hookspath: removed stale local core.hooksPath override on "
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
                "bugteam_fix_hookspath: failed to set global core.hooksPath to "
                f"{canonical_target_value} (git exit {global_set_exit_code}).",
                file=sys.stderr,
            )
            return 1
        print(
            "bugteam_fix_hookspath: set global core.hooksPath to "
            f"{canonical_target_value}",
            file=sys.stderr,
        )
    return rerun_preflight(repository_root, all_environment_overrides)


if __name__ == "__main__":
    raise SystemExit(main(None, all_environment_overrides=None))
