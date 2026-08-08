"""Reinstall claude-dev-env when a cloud session boots from a stale cache.

A cloud environment runs its setup script (`npx -y claude-dev-env@latest`)
once and caches the filesystem; a later session boots from that cache and
skips the script. A release published after the cache was built never lands,
so the session is missing the commands, rules, and hooks that release ships.

This SessionStart hook closes that gap: it reads the installed version from
`~/.claude/.claude-dev-env-manifest.json`, asks the npm registry for the
current version, and reinstalls when the two differ. Both npm calls run from
the home directory: hooks start in the project directory, and inside the
repository that develops this very package, npx resolves the package name to
the local workspace instead of the registry. Local sessions exit at the
remote guard. Every failure path — registry outage, probe timeout, missing
npm — exits 0, so the hook never blocks a session from starting.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from config.session_start_refresh_constants import (
    CLAUDE_HOME_DIRECTORY_NAME,
    INSTALL_TIMEOUT_SECONDS,
    MANIFEST_FILE_NAME,
    PACKAGE_NAME,
    REGISTRY_PROBE_TIMEOUT_SECONDS,
    REMOTE_SESSION_ACTIVE_VALUE,
    REMOTE_SESSION_VARIABLE_NAME,
)


def read_installed_version() -> str:
    manifest_path = Path.home() / CLAUDE_HOME_DIRECTORY_NAME / MANIFEST_FILE_NAME
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    version = manifest.get("version", "")
    return version if isinstance(version, str) else ""


def read_registry_version() -> str:
    npm_path = shutil.which("npm")
    if npm_path is None:
        return ""
    try:
        completed = subprocess.run(
            [npm_path, "view", PACKAGE_NAME, "version"],
            capture_output=True,
            text=True,
            timeout=REGISTRY_PROBE_TIMEOUT_SECONDS,
            check=False,
            cwd=Path.home(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    if completed.returncode != 0:
        return ""
    return completed.stdout.strip()


def reinstall(registry_version: str) -> None:
    npx_path = shutil.which("npx")
    if npx_path is None:
        return
    try:
        subprocess.run(
            [npx_path, "-y", PACKAGE_NAME + "@" + registry_version],
            timeout=INSTALL_TIMEOUT_SECONDS,
            check=False,
            cwd=Path.home(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return


def main() -> int:
    remote_flag = os.environ.get(REMOTE_SESSION_VARIABLE_NAME, "")
    if remote_flag != REMOTE_SESSION_ACTIVE_VALUE:
        return 0
    registry_version = read_registry_version()
    if not registry_version:
        return 0
    installed_version = read_installed_version()
    if installed_version == registry_version:
        return 0
    reinstall(registry_version)
    return 0


if __name__ == "__main__":
    sys.exit(main())
