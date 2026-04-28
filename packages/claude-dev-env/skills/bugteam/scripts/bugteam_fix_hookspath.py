from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.bugteam_fix_hookspath_constants import (
    ALL_CANONICAL_HOOKS_DIRECTORY_COMPONENTS,
    ALL_HOME_ENV_VAR_NAMES,
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
    environment_overrides: dict[str, str] | None,
) -> Path:
    components = _canonical_hooks_directory_components()
    if environment_overrides is not None:
        for each_env_var_name in _home_env_var_names():
            home_value = environment_overrides.get(each_env_var_name)
            if home_value:
                return Path(home_value).joinpath(*components)
    return Path.home().joinpath(*components)


def list_local_core_hooks_path_values(
    repository_root: Path,
    environment_overrides: dict[str, str] | None,
) -> list[str]:
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
        env=environment_overrides,
    )
    if completed_process.returncode != 0:
        return []
    return [
        each_line.strip()
        for each_line in completed_process.stdout.splitlines()
        if each_line.strip()
    ]


def read_global_core_hooks_path(
    environment_overrides: dict[str, str] | None,
) -> str:
    git_command = ["git", "config", "--global", "--get", "core.hooksPath"]
    completed_process = subprocess.run(
        git_command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=environment_overrides,
    )
    if completed_process.returncode != 0:
        return ""
    return completed_process.stdout.strip()


def unset_local_core_hooks_path(
    repository_root: Path,
    environment_overrides: dict[str, str] | None,
) -> int:
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
        env=environment_overrides,
    )
    return completed_process.returncode


def set_global_core_hooks_path(
    target_value: str,
    environment_overrides: dict[str, str] | None,
) -> int:
    git_command = ["git", "config", "--global", "core.hooksPath", target_value]
    completed_process = subprocess.run(
        git_command,
        capture_output=True,
        text=True,
        check=False,
        env=environment_overrides,
    )
    return completed_process.returncode


def normalize_hooks_path(raw_value: str) -> str:
    return raw_value.replace("\\", "/").rstrip("/")


def is_canonical_hooks_path(raw_value: str) -> bool:
    if not raw_value:
        return False
    return normalize_hooks_path(raw_value).endswith(_expected_hooks_path_suffix())


def find_repository_root(start: Path) -> Path:
    resolved_start = start.resolve()
    candidate_paths = [resolved_start, *resolved_start.parents]
    for each_candidate in candidate_paths:
        marker = each_candidate / ".git"
        if marker.is_dir() or marker.is_file():
            return each_candidate
    return resolved_start


def rerun_preflight(
    repository_root: Path,
    environment_overrides: dict[str, str] | None,
) -> int:
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
        env=environment_overrides,
    )
    return completed_process.returncode


def parse_arguments(argv: list[str] | None) -> argparse.Namespace:
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
    return parser.parse_args(argv)


def main(
    argv: list[str] | None = None,
    *,
    environment_overrides: dict[str, str] | None = None,
) -> int:
    arguments = parse_arguments(argv)
    start_directory = Path.cwd()
    repository_root = (
        arguments.repo_root.resolve()
        if arguments.repo_root is not None
        else find_repository_root(start_directory)
    )
    canonical_hooks_directory = resolve_canonical_hooks_directory(environment_overrides)
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
        environment_overrides,
    )
    has_non_canonical_local_override = any(
        not is_canonical_hooks_path(each_value)
        for each_value in local_hooks_path_values
    )
    if has_non_canonical_local_override:
        unset_local_returncode = unset_local_core_hooks_path(
            repository_root, environment_overrides
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
    current_global_value = read_global_core_hooks_path(environment_overrides)
    if not is_canonical_hooks_path(current_global_value):
        canonical_target_value = str(canonical_hooks_directory).replace("\\", "/")
        global_set_exit_code = set_global_core_hooks_path(
            canonical_target_value,
            environment_overrides,
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
    return rerun_preflight(repository_root, environment_overrides)


if __name__ == "__main__":
    raise SystemExit(main())
