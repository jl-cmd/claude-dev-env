"""Unit tests for gh-pr-author-restore PostToolUse hook."""

from __future__ import annotations

import importlib.util
import io
import json
import os
import pathlib
import stat
import sys
from typing import Iterator
from unittest import mock

import pytest

from hooks_constants.gh_pr_author_swap_constants import STATE_FILE_PERMISSION_MODE

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_module_spec = importlib.util.spec_from_file_location(
    "gh_pr_author_restore",
    _HOOK_DIR / "gh_pr_author_restore.py",
)
assert hook_module_spec is not None
assert hook_module_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_module_spec)
hook_module_spec.loader.exec_module(hook_module)

import _gh_pr_author_swap_utils as swap_utils_module  # noqa: E402


def _make_stdin_payload(
    command: str,
    session_id: str = "test-session-001",
    tool_name: str = "Bash",
) -> str:
    return json.dumps(
        {
            "tool_name": tool_name,
            "tool_input": {"command": command},
            "session_id": session_id,
        }
    )


def _write_state_file(state_file: pathlib.Path, original_account: str) -> None:
    state_file.write_text(
        json.dumps(
            {
                "original_account": original_account,
                "primary_account": "JonEcho",
            }
        ),
        encoding="utf-8",
    )


@pytest.fixture
def isolated_state_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> Iterator[pathlib.Path]:
    monkeypatch.setattr(swap_utils_module.tempfile, "gettempdir", lambda: str(tmp_path))
    yield tmp_path


def _run_hook_with(
    stdin_text: str,
    monkeypatch: pytest.MonkeyPatch,
    switch_succeeds: bool,
) -> tuple[int, str, list[str]]:
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    captured_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_stdout)
    switch_invocations: list[str] = []

    def _fake_switch(to_account: str) -> bool:
        switch_invocations.append(to_account)
        return switch_succeeds

    monkeypatch.setattr(hook_module, "_switch_gh_account", _fake_switch)
    with pytest.raises(SystemExit) as exit_info:
        hook_module.main()
    exit_code = exit_info.value.code if isinstance(exit_info.value.code, int) else 0
    return exit_code, captured_stdout.getvalue(), switch_invocations


def test_command_invokes_gh_pr_create_matches_basic_form() -> None:
    assert hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching("gh pr create --title T")
    )


def test_command_invokes_gh_pr_create_rejects_pr_edit() -> None:
    assert not hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching("gh pr edit 10")
    )


def test_state_file_path_uses_session_id(
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file = hook_module._state_file_path("abc-123")
    assert state_file.parent == isolated_state_directory
    assert state_file.name == "gh_pr_author_swap_abc-123.json"


def test_state_file_path_falls_back_to_default_when_session_id_empty(
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file = hook_module._state_file_path("")
    assert state_file.name == "gh_pr_author_swap_default.json"


def test_main_no_op_when_tool_name_not_bash(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file = hook_module._state_file_path("test-session-001")
    _write_state_file(state_file, original_account="jl-cmd")

    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T", tool_name="Write"),
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []
    assert state_file.exists()


def test_main_no_op_when_command_does_not_match_pr_create(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file = hook_module._state_file_path("test-session-001")
    _write_state_file(state_file, original_account="jl-cmd")

    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("git status"),
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []
    assert state_file.exists()


def test_main_no_op_when_state_file_absent(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T"),
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_switches_back_and_deletes_state_file(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file = hook_module._state_file_path("test-session-001")
    _write_state_file(state_file, original_account="jl-cmd")

    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T"),
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == ["jl-cmd"]
    assert not state_file.exists()


def test_main_preserves_state_file_when_switch_fails(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file = hook_module._state_file_path("test-session-001")
    _write_state_file(state_file, original_account="jl-cmd")

    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T"),
        monkeypatch=monkeypatch,
        switch_succeeds=False,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == ["jl-cmd"]
    assert state_file.exists()


def test_main_no_op_on_invalid_stdin_json(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        "not-json",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_no_op_on_malformed_state_file(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file = hook_module._state_file_path("test-session-001")
    state_file.write_text("{not valid json", encoding="utf-8")

    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T"),
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []
    assert not state_file.exists()


def test_main_no_op_when_state_file_missing_original_account(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file = hook_module._state_file_path("test-session-001")
    state_file.write_text(
        json.dumps({"primary_account": "JonEcho"}),
        encoding="utf-8",
    )

    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T"),
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []
    assert not state_file.exists()


def test_main_deletes_state_file_when_original_account_wrong_type(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file = hook_module._state_file_path("test-session-001")
    state_file.write_text(
        json.dumps({"original_account": 42, "primary_account": "JonEcho"}),
        encoding="utf-8",
    )

    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T"),
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []
    assert not state_file.exists()


def test_main_deletes_state_file_when_original_account_blank(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file = hook_module._state_file_path("test-session-001")
    state_file.write_text(
        json.dumps({"original_account": "   ", "primary_account": "JonEcho"}),
        encoding="utf-8",
    )

    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T"),
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []
    assert not state_file.exists()


def test_main_no_op_does_not_create_state_file_when_absent(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file = hook_module._state_file_path("test-session-001")
    assert not state_file.exists()

    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T"),
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []
    assert not state_file.exists()


def test_main_per_session_key_isolation(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file_a = hook_module._state_file_path("session-A")
    state_file_b = hook_module._state_file_path("session-B")
    _write_state_file(state_file_a, original_account="jl-cmd")
    _write_state_file(state_file_b, original_account="other-user")

    exit_code, _stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T", session_id="session-A"),
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert switch_invocations == ["jl-cmd"]
    assert not state_file_a.exists()
    assert state_file_b.exists()


def test_read_original_account_returns_none_for_missing_file(
    isolated_state_directory: pathlib.Path,
) -> None:
    missing_file = isolated_state_directory / "does_not_exist.json"
    assert hook_module._read_original_account(missing_file) is None


def test_read_original_account_returns_none_for_non_dict_payload(
    isolated_state_directory: pathlib.Path,
) -> None:
    list_payload_file = isolated_state_directory / "list_payload.json"
    list_payload_file.write_text(json.dumps(["jl-cmd"]), encoding="utf-8")
    assert hook_module._read_original_account(list_payload_file) is None


def test_read_original_account_returns_none_for_non_string_value(
    isolated_state_directory: pathlib.Path,
) -> None:
    bad_type_file = isolated_state_directory / "bad_type.json"
    bad_type_file.write_text(json.dumps({"original_account": 42}), encoding="utf-8")
    assert hook_module._read_original_account(bad_type_file) is None


def test_read_original_account_returns_none_for_blank_value(
    isolated_state_directory: pathlib.Path,
) -> None:
    blank_value_file = isolated_state_directory / "blank.json"
    blank_value_file.write_text(json.dumps({"original_account": "   "}), encoding="utf-8")
    assert hook_module._read_original_account(blank_value_file) is None


def test_switch_gh_account_returns_true_on_success() -> None:
    completed = mock.Mock(returncode=0, stdout="", stderr="")
    with mock.patch.object(swap_utils_module.subprocess, "run", return_value=completed):
        assert hook_module._switch_gh_account("jl-cmd") is True


def test_switch_gh_account_returns_false_on_nonzero_exit() -> None:
    completed = mock.Mock(returncode=1, stdout="", stderr="boom")
    with mock.patch.object(swap_utils_module.subprocess, "run", return_value=completed):
        assert hook_module._switch_gh_account("jl-cmd") is False


def test_switch_gh_account_returns_false_when_gh_missing() -> None:
    with mock.patch.object(swap_utils_module.subprocess, "run", side_effect=FileNotFoundError):
        assert hook_module._switch_gh_account("jl-cmd") is False


def test_switch_gh_account_returns_false_on_timeout() -> None:
    with mock.patch.object(
        swap_utils_module.subprocess,
        "run",
        side_effect=swap_utils_module.subprocess.TimeoutExpired(cmd="gh", timeout=10),
    ):
        assert hook_module._switch_gh_account("jl-cmd") is False


def test_delete_state_file_is_silent_when_already_absent(
    isolated_state_directory: pathlib.Path,
) -> None:
    missing_file = isolated_state_directory / "does_not_exist.json"
    hook_module._delete_state_file(missing_file)
    assert not missing_file.exists()


def test_main_logs_high_level_failure_when_restore_switch_fails(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    isolated_state_directory: pathlib.Path,
) -> None:
    state_file = hook_module._state_file_path("test-session-001")
    _write_state_file(state_file, original_account="jl-cmd")

    monkeypatch.setattr(sys, "stdin", io.StringIO(_make_stdin_payload("gh pr create --title T")))

    def _fake_switch(to_account: str) -> bool:
        return False

    monkeypatch.setattr(hook_module, "_switch_gh_account", _fake_switch)

    with pytest.raises(SystemExit) as exit_info:
        hook_module.main()

    exit_code = exit_info.value.code if isinstance(exit_info.value.code, int) else 0
    captured_streams = capsys.readouterr()

    assert exit_code == 0
    assert state_file.exists()
    assert "[gh-pr-author-restore] failed to restore" in captured_streams.err
    assert "'jl-cmd'" in captured_streams.err
    assert str(state_file) in captured_streams.err


def test_main_skips_switch_and_preserves_state_file_when_planted_with_wrong_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    isolated_state_directory: pathlib.Path,
) -> None:
    """A state file with mode 0o644 must not drive a gh-account switch.

    Regression guard: an attacker on the same workstation could plant a
    state file at the predictable swap-state path with an
    attacker-controlled ``original_account`` value. The restore hook
    must validate the file's mode and owner before reading the
    payload — a divergent mode signals the file was not written by the
    enforcer running as this user. The hook must skip the switch, leave
    the file on disk for inspection, and log a rejection line to
    stderr.
    """
    if not hasattr(os, "getuid"):
        return
    state_file = hook_module._state_file_path("test-session-001")
    _write_state_file(state_file, original_account="attacker")
    os.chmod(state_file, 0o644)

    monkeypatch.setattr(
        sys, "stdin", io.StringIO(_make_stdin_payload("gh pr create --title T"))
    )
    switch_invocations: list[str] = []

    def _fake_switch(to_account: str) -> bool:
        switch_invocations.append(to_account)
        return True

    monkeypatch.setattr(hook_module, "_switch_gh_account", _fake_switch)

    with pytest.raises(SystemExit) as exit_info:
        hook_module.main()

    exit_code = exit_info.value.code if isinstance(exit_info.value.code, int) else 0
    captured_streams = capsys.readouterr()

    assert exit_code == 0
    assert switch_invocations == []
    assert state_file.exists()
    expected_mode_bits = stat.S_IMODE(state_file.stat().st_mode)
    assert expected_mode_bits == 0o644
    assert "[gh-pr-author-restore]" in captured_streams.err
    assert "unexpected mode" in captured_streams.err or "unexpected" in captured_streams.err
    assert str(state_file) in captured_streams.err


def test_module_imports_and_main_runs_under_production_sys_path_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Module imports cleanly AND main() executes a no-op path when only blocking/ is on sys.path.

    pytest's ``pythonpath = packages/claude-dev-env/hooks`` lets the
    in-test import work even without the sys.path shim. The Claude Code
    hook runner does NOT set that path — it invokes
    ``python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/gh_pr_author_restore.py``,
    so only ``blocking/`` lands on sys.path. This test reproduces that
    layout, imports the module via its own sys.path shim, then exercises
    ``main()`` against a non-Bash tool_name so the no-op path runs end to
    end — proving the module not only imports without
    ``ModuleNotFoundError`` but also executes correctly under the
    production layout.
    """
    blocking_dir = pathlib.Path(__file__).resolve().parent
    monkeypatch.setattr(sys, "path", [str(blocking_dir)])
    spec = importlib.util.spec_from_file_location(
        "gh_pr_author_restore_production_path_check",
        blocking_dir / "gh_pr_author_restore.py",
    )
    assert spec is not None
    assert spec.loader is not None
    fresh_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fresh_module)
    non_bash_hook_payload = json.dumps({"tool_name": "Read", "tool_input": {}})
    monkeypatch.setattr(sys, "stdin", io.StringIO(non_bash_hook_payload))
    captured_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_stdout)
    with pytest.raises(SystemExit) as exit_info:
        fresh_module.main()
    assert exit_info.value.code == 0
    assert captured_stdout.getvalue() == ""
