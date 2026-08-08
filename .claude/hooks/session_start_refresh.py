"""Reinstall claude-dev-env when a cloud session boots from a stale cache.

A cloud environment runs its setup script (`npx -y claude-dev-env@latest`)
once and caches the filesystem; a later session boots from that cache and
skips the script. A release published after the cache was built never lands,
so the session is missing the commands, rules, and hooks that release ships.

This SessionStart hook closes that gap: it reads the installed version from
the manifest in the Claude config directory (`CLAUDE_CONFIG_DIR` when set,
`~/.claude` otherwise), asks the npm registry for the current version, and
reinstalls when the two differ. Both npm calls run from the home directory:
hooks start in the project directory, and inside the repository that develops
this very package, npx resolves the package name to the local workspace
instead of the registry. Local sessions exit at the remote guard. Every
failure path — registry outage, probe timeout, missing npm — exits 0, so the
hook never blocks a session from starting.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

from config.session_start_refresh_constants import (
    CLAUDE_HOME_DIRECTORY_NAME,
    CONFIG_DIR_OVERRIDE_VARIABLE_NAME,
    INSTALL_TIMEOUT_SECONDS,
    MANIFEST_FILE_NAME,
    PACKAGE_NAME,
    REGISTRY_PROBE_TIMEOUT_SECONDS,
    REMOTE_SESSION_ACTIVE_VALUE,
    REMOTE_SESSION_VARIABLE_NAME,
)


def claude_config_directory() -> Path:
    override = os.environ.get(CONFIG_DIR_OVERRIDE_VARIABLE_NAME, "").strip()
    if override:
        return Path(override).expanduser()
    return Path.home() / CLAUDE_HOME_DIRECTORY_NAME


def read_installed_version() -> str:
    manifest_path = claude_config_directory() / MANIFEST_FILE_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    version = manifest.get("version")
    return version if isinstance(version, str) else ""


def _run_tool_from_home(
    tool_name: str, all_arguments: list[str], timeout_seconds: int
) -> subprocess.CompletedProcess[str] | None:
    tool_path = shutil.which(tool_name)
    if tool_path is None:
        return None
    try:
        return subprocess.run(
            [tool_path, *all_arguments],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
            cwd=Path.home(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def read_registry_version() -> str:
    completed = _run_tool_from_home(
        "npm", ["view", PACKAGE_NAME, "version"], REGISTRY_PROBE_TIMEOUT_SECONDS
    )
    if completed is None or completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def reinstall(registry_version: str) -> None:
    _run_tool_from_home(
        "npx", ["-y", PACKAGE_NAME + "@" + registry_version], INSTALL_TIMEOUT_SECONDS
    )


def main() -> None:
    if os.environ.get(REMOTE_SESSION_VARIABLE_NAME, "") != REMOTE_SESSION_ACTIVE_VALUE:
        return
    registry_version = read_registry_version()
    if not registry_version:
        return
    if read_installed_version() == registry_version:
        return
    reinstall(registry_version)


if __name__ == "__main__":
    main()
