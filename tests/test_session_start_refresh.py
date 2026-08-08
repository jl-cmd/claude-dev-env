"""Behavior checks for the cloud SessionStart refresh hook.

Six checks run `.claude/hooks/session_start_refresh.py` as a real subprocess
against a sandbox home directory, with fake `npm` and `npx` executables on
`PATH` that record their arguments to a log file. The assertions read that log:
a refresh run shows an `npx -y claude-dev-env@<version>` line, a quiet run
shows none. Two static checks bind the `.claude/settings.json` registration to
the hook: the registered command names the script on disk, and the probe and
install budgets stay inside the registered timeout.
"""

import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from types import ModuleType

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
HOOK_SCRIPT = REPOSITORY_ROOT / ".claude" / "hooks" / "session_start_refresh.py"


def _refresh_constants() -> ModuleType:
    constants_path = (
        REPOSITORY_ROOT
        / ".claude"
        / "hooks"
        / "config"
        / "session_start_refresh_constants.py"
    )
    spec = importlib.util.spec_from_file_location(
        "session_start_refresh_constants", constants_path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REFRESH_CONSTANTS = _refresh_constants()
MANIFEST_FILE_NAME: str = REFRESH_CONSTANTS.MANIFEST_FILE_NAME


def _session_start_registration() -> dict[str, object]:
    settings = json.loads(
        (REPOSITORY_ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
    )
    [group] = settings["hooks"]["SessionStart"]
    [entry] = group["hooks"]
    return entry


SESSION_START_REGISTRATION = _session_start_registration()


def should_register_a_hook_command_that_names_the_existing_script() -> None:
    command = SESSION_START_REGISTRATION["command"]
    assert isinstance(command, str)
    assert HOOK_SCRIPT.name in command
    assert HOOK_SCRIPT.is_file()


def should_keep_the_subprocess_budgets_inside_the_registered_timeout() -> None:
    registered_timeout = SESSION_START_REGISTRATION["timeout"]
    assert isinstance(registered_timeout, int)
    subprocess_budget = (
        REFRESH_CONSTANTS.REGISTRY_PROBE_TIMEOUT_SECONDS
        + REFRESH_CONSTANTS.INSTALL_TIMEOUT_SECONDS
    )
    assert subprocess_budget < registered_timeout

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


def _write_manifest(directory: Path, version: str) -> None:
    (directory / MANIFEST_FILE_NAME).write_text(
        json.dumps({"version": version}), encoding="utf-8"
    )


def _seed_sandbox(
    sandbox: Path,
    installed_version: str | None,
    config_dir_version: str | None,
) -> None:
    shim_directory = sandbox / "bin"
    shim_directory.mkdir()
    _write_probe_shims(shim_directory)
    (sandbox / "tool-log.txt").write_text("", encoding="utf-8")
    (sandbox / "home" / ".claude").mkdir(parents=True)
    if installed_version is not None:
        _write_manifest(sandbox / "home" / ".claude", installed_version)
    if config_dir_version is not None:
        (sandbox / "config-override").mkdir()
        _write_manifest(sandbox / "config-override", config_dir_version)


def _hook_environment(
    sandbox: Path,
    *,
    remote: bool,
    registry_version: str,
    registry_failure: bool,
    config_dir_version: str | None,
) -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("CLAUDE_CODE_REMOTE", None)
    environment.pop("CLAUDE_CONFIG_DIR", None)
    if remote:
        environment["CLAUDE_CODE_REMOTE"] = "true"
    if config_dir_version is not None:
        environment["CLAUDE_CONFIG_DIR"] = str(sandbox / "config-override")
    environment["PATH"] = os.pathsep.join(
        [str(sandbox / "bin"), environment.get("PATH", "")]
    )
    environment["HOME"] = str(sandbox / "home")
    environment["USERPROFILE"] = str(sandbox / "home")
    environment["FAKE_TOOL_LOG"] = str(sandbox / "tool-log.txt")
    environment["FAKE_NPM_VERSION"] = registry_version
    if registry_failure:
        environment["FAKE_NPM_FAILURE"] = "1"
    return environment


def run_hook(
    sandbox: Path,
    *,
    remote: bool,
    installed_version: str | None,
    registry_version: str,
    registry_failure: bool = False,
    config_dir_version: str | None = None,
) -> str:
    _seed_sandbox(sandbox, installed_version, config_dir_version)
    environment = _hook_environment(
        sandbox,
        remote=remote,
        registry_version=registry_version,
        registry_failure=registry_failure,
        config_dir_version=config_dir_version,
    )
    completed = subprocess.run(
        [sys.executable, str(HOOK_SCRIPT)],
        env=environment, capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    return (sandbox / "tool-log.txt").read_text(encoding="utf-8")


def should_stay_quiet_when_the_remote_flag_is_absent(tmp_path: Path) -> None:
    tool_log = run_hook(
        tmp_path, remote=False, installed_version="2.9.0", registry_version="2.12.0"
    )
    assert tool_log == ""


def should_reinstall_from_the_home_directory_when_the_registry_is_ahead(
    tmp_path: Path,
) -> None:
    tool_log = run_hook(
        tmp_path, remote=True, installed_version="2.9.0", registry_version="2.12.0"
    )
    assert "npm view claude-dev-env version" in tool_log
    assert "npx -y claude-dev-env@2.12.0" in tool_log
    logged_lines = tool_log.strip().splitlines()
    assert len(logged_lines) == 2, tool_log
    for logged_line in logged_lines:
        assert logged_line.rstrip().endswith("cwd=" + str(tmp_path / "home")), (
            logged_line
        )


def should_leave_a_current_install_in_place(tmp_path: Path) -> None:
    tool_log = run_hook(
        tmp_path, remote=True, installed_version="2.12.0", registry_version="2.12.0"
    )
    assert "npm view claude-dev-env version" in tool_log
    assert "npx" not in tool_log


def should_fail_open_when_the_registry_probe_fails(tmp_path: Path) -> None:
    tool_log = run_hook(
        tmp_path,
        remote=True,
        installed_version="2.9.0",
        registry_version="2.12.0",
        registry_failure=True,
    )
    assert "npx" not in tool_log


def should_reinstall_when_no_manifest_is_present(tmp_path: Path) -> None:
    tool_log = run_hook(
        tmp_path, remote=True, installed_version=None, registry_version="2.12.0"
    )
    assert "npx -y claude-dev-env@2.12.0" in tool_log


def should_read_the_manifest_from_a_config_dir_override(tmp_path: Path) -> None:
    tool_log = run_hook(
        tmp_path,
        remote=True,
        installed_version=None,
        registry_version="2.12.0",
        config_dir_version="2.12.0",
    )
    assert "npm view claude-dev-env version" in tool_log
    assert "npx" not in tool_log
