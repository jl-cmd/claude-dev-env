"""Behavior tests for find_filesystem_walk_blocker PreToolUse hook."""

from __future__ import annotations

import importlib.util
import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

_GUARDS_DIR = Path(__file__).resolve().parent
_HOOKS_ROOT = _GUARDS_DIR.parent.parent
for each_sys_path_entry in (str(_GUARDS_DIR), str(_HOOKS_ROOT)):
    if each_sys_path_entry not in sys.path:
        sys.path.insert(0, each_sys_path_entry)

_HOOK_SPEC = importlib.util.spec_from_file_location(
    "find_filesystem_walk_blocker",
    _GUARDS_DIR / "find_filesystem_walk_blocker.py",
)
assert _HOOK_SPEC is not None
assert _HOOK_SPEC.loader is not None
blocker = importlib.util.module_from_spec(_HOOK_SPEC)
sys.modules["find_filesystem_walk_blocker"] = blocker
_HOOK_SPEC.loader.exec_module(blocker)


def _run_main(hook_input: dict) -> tuple[str, int]:
    captured_stdout = StringIO()
    exit_code = 0
    try:
        with (
            patch("sys.stdin", StringIO(json.dumps(hook_input))),
            patch("sys.stdout", captured_stdout),
            patch.object(blocker, "log_hook_block"),
        ):
            blocker.main()
    except SystemExit as system_exit:
        exit_code = int(system_exit.code or 0)
    return captured_stdout.getvalue(), exit_code


def _bash_payload(command: str) -> dict:
    return {
        "tool_name": "Bash",
        "tool_input": {"command": command, "description": "search"},
    }


class TestCommandInvokesFilesystemFind:
    def test_matches_bare_find_name(self) -> None:
        assert blocker.command_invokes_filesystem_find(
            "find / -name nest_asyncio.py"
        )

    def test_matches_iname_flag(self) -> None:
        assert blocker.command_invokes_filesystem_find(
            "find / -maxdepth 6 -iname *pr-fix-protocol* -type d"
        )

    def test_matches_git_find_exe_full_path(self) -> None:
        assert blocker.command_invokes_filesystem_find(
            r'"C:\Program Files\Git\usr\bin\find.exe" / -name nest_asyncio.py'
        )

    def test_matches_find_exe_basename(self) -> None:
        assert blocker.command_invokes_filesystem_find("find.exe . -name '*.py'")

    def test_matches_find_after_shell_separator(self) -> None:
        assert blocker.command_invokes_filesystem_find(
            "cd /tmp && find . -name config.py"
        )

    def test_allows_findstr(self) -> None:
        assert not blocker.command_invokes_filesystem_find(
            "findstr /s /i nest_asyncio *"
        )

    def test_allows_es_exe(self) -> None:
        assert not blocker.command_invokes_filesystem_find(
            r'"C:\Program Files\Everything\es.exe" nest_asyncio.py'
        )

    def test_allows_git_find_object_flag(self) -> None:
        assert not blocker.command_invokes_filesystem_find(
            "git rev-list --find-object=HEAD"
        )

    def test_allows_empty_command(self) -> None:
        assert not blocker.command_invokes_filesystem_find("")


class TestExtractNameSearchTerm:
    def test_extracts_name_literal(self) -> None:
        assert (
            blocker.extract_name_search_term("find / -name nest_asyncio.py")
            == "nest_asyncio.py"
        )

    def test_strips_wildcards_from_iname(self) -> None:
        assert (
            blocker.extract_name_search_term(
                "find / -iname *pr-fix-protocol* -type d"
            )
            == "pr-fix-protocol"
        )

    def test_strips_quotes(self) -> None:
        assert (
            blocker.extract_name_search_term("find . -name '*.py'")
            == ".py"
        )


class TestMainDenyAndAllow:
    def test_denies_find_name_walk_with_es_rewrite(self) -> None:
        stdout_text, exit_code = _run_main(
            _bash_payload("find / -name nest_asyncio.py")
        )
        assert exit_code == 0
        payload = json.loads(stdout_text)
        reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "es.exe" in reason
        assert "nest_asyncio.py" in reason
        assert "everything-search" in reason
        assert "Get-ChildItem -Recurse" in reason

    def test_denies_iname_and_full_path_git_find(self) -> None:
        command = (
            r'"C:\Program Files\Git\usr\bin\find.exe" / '
            r"-maxdepth 6 -iname *pr-fix-protocol* -type d"
        )
        stdout_text, exit_code = _run_main(_bash_payload(command))
        assert exit_code == 0
        payload = json.loads(stdout_text)
        reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
        assert "pr-fix-protocol" in reason

    def test_allows_es_exe_command(self) -> None:
        stdout_text, exit_code = _run_main(
            _bash_payload(r'"C:\Program Files\Everything\es.exe" nest_asyncio.py')
        )
        assert exit_code == 0
        assert stdout_text.strip() == ""

    def test_allows_findstr(self) -> None:
        stdout_text, exit_code = _run_main(
            _bash_payload("findstr /s nest_asyncio *")
        )
        assert exit_code == 0
        assert stdout_text.strip() == ""

    def test_denies_on_powershell_tool(self) -> None:
        stdout_text, exit_code = _run_main(
            {
                "tool_name": "PowerShell",
                "tool_input": {
                    "command": r"& 'C:\Program Files\Git\usr\bin\find.exe' / -name foo"
                },
            }
        )
        assert exit_code == 0
        payload = json.loads(stdout_text)
        assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"

    def test_ignores_non_shell_tools(self) -> None:
        stdout_text, exit_code = _run_main(
            {
                "tool_name": "Write",
                "tool_input": {"command": "find / -name foo"},
            }
        )
        assert exit_code == 0
        assert stdout_text.strip() == ""


def test_build_es_rewrite_command_uses_windows_path_by_default() -> None:
    rewrite = blocker.build_es_rewrite_command(
        "find / -name nest_asyncio.py",
        "nest_asyncio.py",
    )
    assert r"C:\Program Files\Everything\es.exe" in rewrite
    assert "nest_asyncio.py" in rewrite


def test_build_es_rewrite_command_uses_wsl_path_for_bash_wrapper() -> None:
    rewrite = blocker.build_es_rewrite_command(
        "bash -c 'find / -name nest_asyncio.py'",
        "nest_asyncio.py",
    )
    assert "/mnt/c/Program" in rewrite
