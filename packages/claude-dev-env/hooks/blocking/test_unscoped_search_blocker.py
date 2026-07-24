"""Unit tests for the unscoped-search PreToolUse Bash/PowerShell blocker."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from io import StringIO
from unittest.mock import patch

import pytest

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))
if str(_HOOK_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR.parent))

_hook_spec = importlib.util.spec_from_file_location(
    "unscoped_search_blocker",
    _HOOK_DIR / "unscoped_search_blocker.py",
)
assert _hook_spec is not None
assert _hook_spec.loader is not None
_hook_module = importlib.util.module_from_spec(_hook_spec)
_hook_spec.loader.exec_module(_hook_module)

find_unscoped_search_violation = _hook_module.find_unscoped_search_violation
is_unscoped_search_root = _hook_module.is_unscoped_search_root
main = _hook_module.main

from hooks_constants.unscoped_search_blocker_constants import (  # noqa: E402
    CORRECTIVE_MESSAGE,
)


@pytest.mark.parametrize(
    "path_token",
    [
        "/",
        "/c",
        "/c/",
        "/D",
        "/d/",
        "C:\\",
        "C:/",
        "C:",
        "c:\\",
        "~",
        "~/",
        "$HOME",
        "$HOME/",
        "${HOME}",
        "%USERPROFILE%",
        "%USERPROFILE%\\",
        "%USERPROFILE%/",
        "$env:USERPROFILE",
    ],
)
def test_is_unscoped_search_root_flags_roots_and_bare_home(path_token: str) -> None:
    assert is_unscoped_search_root(path_token) is True


@pytest.mark.parametrize(
    "path_token",
    [
        ".",
        "./src",
        "packages/claude-dev-env",
        "/c/Users/jon/project",
        r"C:\Users\jon\project",
        "C:/dev/repo",
        "~/Projects/app",
        "$HOME/code",
        "${HOME}/work",
        r"%USERPROFILE%\dev",
        "/tmp/scratch",
        "C:/Users/jon",
    ],
)
def test_is_unscoped_search_root_allows_scoped_paths(path_token: str) -> None:
    assert is_unscoped_search_root(path_token) is False


@pytest.mark.parametrize(
    "command",
    [
        "find / -iname code_rules_gate.py",
        "find / -iname SKILL.md -path '*redlib*'",
        r'find /c -name "*.py"',
        r"find C:\ -name foo",
        "find ~ -name README.md",
        "find $HOME -type f",
        "timeout 30 find / -name x",
        "cd /tmp && find / -name x",
        "find -L / -type d",
        r"/usr/bin/find.exe / -name y",
    ],
)
def test_find_unscoped_search_violation_denies_unscoped_root(command: str) -> None:
    assert find_unscoped_search_violation(command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize(
    "command",
    [
        "find . -iname code_rules_gate.py",
        "find packages/claude-dev-env -name '*.py'",
        "find /c/Users/jon/repo -iname SKILL.md",
        r"find C:\Users\jon\repo -name foo",
        "find ~/Projects/app -type f",
        "find $HOME/code -name x",
        "echo find / -name x",
        "git log --find-renames",
        "ls /",
        "cat /etc/hosts",
        "es.exe code_rules_gate.py",
        "rg 'shell contention' packages",
    ],
)
def test_scoped_or_non_find_commands_are_allowed(command: str) -> None:
    assert find_unscoped_search_violation(command) is None


@pytest.mark.parametrize(
    "command",
    [
        "Get-ChildItem -Path C:\\ -Recurse",
        "Get-ChildItem C:\\ -Recurse -Filter *.py",
        "gci -Recurse /",
        "dir -Recurse C:\\",
        "Get-ChildItem -LiteralPath $HOME -Recurse",
        "Get-ChildItem -Recurse:$true C:\\",
        "Get-ChildItem -Path C:\\ -Recurse:$true",
        "dir /s C:\\",
    ],
)
def test_recursive_get_child_item_on_root_is_denied(command: str) -> None:
    assert find_unscoped_search_violation(command) == CORRECTIVE_MESSAGE


@pytest.mark.parametrize(
    "command",
    [
        r"Get-ChildItem -Path C:\Users\jon\repo -Recurse",
        "Get-ChildItem . -Recurse",
        "gci packages -Recurse",
        "Get-ChildItem C:\\",
        "Get-ChildItem -Path / -Force",
    ],
)
def test_scoped_or_non_recursive_get_child_item_is_allowed(command: str) -> None:
    assert find_unscoped_search_violation(command) is None


def test_main_denies_unscoped_find_on_bash_tool() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "find / -iname code_rules_gate.py"},
    }
    stdin = StringIO(json.dumps(payload))
    stdout = StringIO()
    with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
        with patch.object(_hook_module, "log_hook_block"):
            with pytest.raises(SystemExit) as exit_info:
                main()
    assert exit_info.value.code == 0
    result = json.loads(stdout.getvalue())
    assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert (
        result["hookSpecificOutput"]["permissionDecisionReason"] == CORRECTIVE_MESSAGE
    )


def test_main_allows_scoped_find() -> None:
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "find . -name '*.py'"},
    }
    stdin = StringIO(json.dumps(payload))
    stdout = StringIO()
    with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
        with pytest.raises(SystemExit) as exit_info:
            main()
    assert exit_info.value.code == 0
    assert stdout.getvalue() == ""


def test_main_ignores_non_shell_tools() -> None:
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "x.py", "content": "find /"},
    }
    stdin = StringIO(json.dumps(payload))
    stdout = StringIO()
    with patch.object(sys, "stdin", stdin), patch.object(sys, "stdout", stdout):
        with pytest.raises(SystemExit) as exit_info:
            main()
    assert exit_info.value.code == 0
    assert stdout.getvalue() == ""
