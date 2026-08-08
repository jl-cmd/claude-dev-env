"""Behavior checks for the cloud SessionStart refresh hook.

Each check runs `.claude/hooks/session_start_refresh.py` as a real subprocess
against a sandbox home directory, with fake `npm` and `npx` executables on
`PATH` that record their arguments to a log file. The assertions read that log:
a refresh run shows an `npx -y claude-dev-env@<version>` line, a quiet run
shows none.
"""

import os
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = REPOSITORY_ROOT / ".claude" / "hooks" / "session_start_refresh.py"

POSIX_NPM_SHIM = """#!/bin/bash
printf 'npm %s cwd=%s\\n' "$*" "$PWD" >> "$FAKE_TOOL_LOG"
if [ -n "${FAKE_NPM_FAILURE:-}" ]; then
  exit 1
fi
printf '%s\\n' "$FAKE_NPM_VERSION"
"""

POSIX_NPX_SHIM = """#!/bin/bash
printf 'npx %s cwd=%s\\n' "$*" "$PWD" >> "$FAKE_TOOL_LOG"
"""

WINDOWS_NPM_SHIM = """@echo off
echo npm %* cwd=%CD% >> "%FAKE_TOOL_LOG%"
if defined FAKE_NPM_FAILURE exit /b 1
echo %FAKE_NPM_VERSION%
"""

WINDOWS_NPX_SHIM = """@echo off
echo npx %* cwd=%CD% >> "%FAKE_TOOL_LOG%"
"""


def _write_probe_shims(shim_directory: Path) -> None:
    if os.name == "nt":
        (shim_directory / "npm.cmd").write_text(WINDOWS_NPM_SHIM, encoding="utf-8")
        (shim_directory / "npx.cmd").write_text(WINDOWS_NPX_SHIM, encoding="utf-8")
        return
    for shim_name, shim_body in (("npm", POSIX_NPM_SHIM), ("npx", POSIX_NPX_SHIM)):
        shim_path = shim_directory / shim_name
        shim_path.write_text(shim_body, encoding="utf-8")
        shim_path.chmod(shim_path.stat().st_mode | stat.S_IXUSR)


def _seed_sandbox(sandbox: Path, installed_version: str | None) -> Path:
    shim_directory = sandbox / "bin"
    shim_directory.mkdir()
    _write_probe_shims(shim_directory)
    (sandbox / "tool-log.txt").write_text("", encoding="utf-8")
    home_directory = sandbox / "home"
    (home_directory / ".claude").mkdir(parents=True)
    if installed_version is not None:
        manifest_path = home_directory / ".claude" / ".claude-dev-env-manifest.json"
        manifest_body = (
            '{"package": "claude-dev-env", "version": "' + installed_version + '"}'
        )
        manifest_path.write_text(manifest_body, encoding="utf-8")
    return home_directory


def _hook_environment(
    sandbox: Path,
    home_directory: Path,
    *,
    remote: bool,
    registry_version: str,
    registry_failure: bool,
) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("CLAUDE_CODE_REMOTE", None)
    if remote:
        environment["CLAUDE_CODE_REMOTE"] = "true"
    environment["PATH"] = os.pathsep.join(
        [str(sandbox / "bin"), environment.get("PATH", "")]
    )
    environment["HOME"] = str(home_directory)
    environment["USERPROFILE"] = str(home_directory)
    environment["FAKE_TOOL_LOG"] = str(sandbox / "tool-log.txt")
    environment["FAKE_NPM_VERSION"] = registry_version
    if registry_failure:
        environment["FAKE_NPM_FAILURE"] = "1"
    return environment


def run_hook(
    *,
    remote: bool,
    installed_version: str | None,
    registry_version: str,
    registry_failure: bool = False,
) -> tuple[subprocess.CompletedProcess[str], str, str]:
    with tempfile.TemporaryDirectory() as sandbox_name:
        sandbox = Path(sandbox_name)
        home_directory = _seed_sandbox(sandbox, installed_version)
        environment = _hook_environment(
            sandbox,
            home_directory,
            remote=remote,
            registry_version=registry_version,
            registry_failure=registry_failure,
        )
        completed = subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        tool_log = (sandbox / "tool-log.txt").read_text(encoding="utf-8")
        return completed, tool_log, str(home_directory)


def should_stay_quiet_when_the_remote_flag_is_absent() -> None:
    completed, tool_log, _home_directory = run_hook(
        remote=False, installed_version="2.9.0", registry_version="2.12.0"
    )
    assert completed.returncode == 0, completed.stderr
    assert tool_log == ""


def should_reinstall_when_the_registry_is_ahead() -> None:
    completed, tool_log, _home_directory = run_hook(
        remote=True, installed_version="2.9.0", registry_version="2.12.0"
    )
    assert completed.returncode == 0, completed.stderr
    assert "npm view claude-dev-env version" in tool_log
    assert "npx -y claude-dev-env@2.12.0" in tool_log


def should_run_npm_and_npx_from_the_home_directory() -> None:
    completed, tool_log, home_directory = run_hook(
        remote=True, installed_version="2.9.0", registry_version="2.12.0"
    )
    assert completed.returncode == 0, completed.stderr
    logged_lines = tool_log.strip().splitlines()
    assert len(logged_lines) == 2, tool_log
    for logged_line in logged_lines:
        assert "cwd=" + home_directory in logged_line, logged_line


def should_leave_a_current_install_in_place() -> None:
    completed, tool_log, _home_directory = run_hook(
        remote=True, installed_version="2.12.0", registry_version="2.12.0"
    )
    assert completed.returncode == 0, completed.stderr
    assert "npm view claude-dev-env version" in tool_log
    assert "npx" not in tool_log


def should_fail_open_when_the_registry_probe_fails() -> None:
    completed, tool_log, _home_directory = run_hook(
        remote=True,
        installed_version="2.9.0",
        registry_version="2.12.0",
        registry_failure=True,
    )
    assert completed.returncode == 0, completed.stderr
    assert "npx" not in tool_log


def should_reinstall_when_no_manifest_is_present() -> None:
    completed, tool_log, _home_directory = run_hook(
        remote=True, installed_version=None, registry_version="2.12.0"
    )
    assert completed.returncode == 0, completed.stderr
    assert "npx -y claude-dev-env@2.12.0" in tool_log
