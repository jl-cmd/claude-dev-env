"""Unit tests for gh-pr-author-enforcer PreToolUse hook (auto-switch behavior)."""

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

_HOOK_DIR = pathlib.Path(__file__).parent
if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

hook_module_spec = importlib.util.spec_from_file_location(
    "gh_pr_author_enforcer",
    _HOOK_DIR / "gh_pr_author_enforcer.py",
)
assert hook_module_spec is not None
assert hook_module_spec.loader is not None
hook_module = importlib.util.module_from_spec(hook_module_spec)
hook_module_spec.loader.exec_module(hook_module)

import _gh_pr_author_swap_utils as swap_utils_module  # noqa: E402

from config.gh_pr_author_swap_constants import STATE_FILE_PERMISSION_MODE  # noqa: E402


def _make_stdin_payload(command: str, session_id: str = "test-session-001") -> str:
    return json.dumps(
        {
            "tool_name": "Bash",
            "tool_input": {"command": command},
            "session_id": session_id,
        }
    )


@pytest.fixture
def required_account_jonecho(monkeypatch: pytest.MonkeyPatch) -> Iterator[str]:
    monkeypatch.setenv("GITHUB_DEFAULT_ACCOUNT", "JonEcho")
    yield "JonEcho"


@pytest.fixture
def isolated_state_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> Iterator[pathlib.Path]:
    monkeypatch.setattr(swap_utils_module.tempfile, "gettempdir", lambda: str(tmp_path))
    yield tmp_path


def _run_hook_with(
    stdin_text: str,
    active_account_or_none: str | None,
    monkeypatch: pytest.MonkeyPatch,
    switch_succeeds: bool,
) -> tuple[int, str, list[str]]:
    monkeypatch.setattr(sys, "stdin", io.StringIO(stdin_text))
    captured_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_stdout)
    monkeypatch.setattr(hook_module, "_active_gh_account", lambda: active_account_or_none)
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


def test_command_invokes_gh_pr_create_matches_chained_form() -> None:
    assert hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching("git push && gh pr create")
    )


def test_command_invokes_gh_pr_create_rejects_pr_edit() -> None:
    assert not hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching("gh pr edit 10 --title X")
    )


def test_command_invokes_gh_pr_create_rejects_substring() -> None:
    assert not hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching("some-gh pr created-by")
    )


def test_command_uses_web_flag_matches_long_form() -> None:
    assert hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching("gh pr create --web")
    )


def test_command_uses_web_flag_matches_short_form() -> None:
    assert hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching("gh pr create -w")
    )


def test_command_uses_web_flag_rejects_webhook_substring() -> None:
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching("gh pr create --webhook=foo")
    )


def test_command_uses_web_flag_ignores_curl_w_flag_before_gh() -> None:
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            "curl -w '%{http_code}' url && gh pr create --title T"
        )
    )


def test_command_uses_web_flag_ignores_w_after_separator() -> None:
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            "gh pr create --title T && other-cmd -w"
        )
    )


def test_command_uses_web_flag_detects_web_inside_gh_pr_create() -> None:
    assert hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching("gh pr create --web --title T")
    )


def test_command_uses_web_flag_detects_short_w_inside_gh_pr_create() -> None:
    assert hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching("gh pr create -w --title T")
    )


def test_command_uses_web_flag_handles_gh_pr_create_without_web() -> None:
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            "gh pr create --title T --body-file B"
        )
    )


def test_command_uses_web_flag_returns_false_when_gh_pr_create_absent() -> None:
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching("curl -w '%{http_code}' url")
    )


def test_command_uses_web_flag_ignores_w_after_pipe_separator() -> None:
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            "gh pr create --title T | tee -w log"
        )
    )


def test_command_uses_web_flag_ignores_w_after_semicolon_separator() -> None:
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            "gh pr create --title T ; other-cmd -w"
        )
    )


def test_command_uses_web_flag_ignores_w_after_or_separator() -> None:
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            "gh pr create --title T || fallback -w"
        )
    )


def test_command_uses_web_flag_ignores_w_after_background_separator() -> None:
    """`gh pr create & other-cmd -w` does not pick up the trailing -w."""
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            "gh pr create --title T & other-cmd -w"
        )
    )


def test_main_auto_switches_when_active_account_mismatches(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T --body-file B"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == ["JonEcho"]
    state_file = hook_module._state_file_path("test-session-001")
    assert state_file.exists()
    persisted_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert persisted_state == {
        "original_account": "jl-cmd",
        "primary_account": "JonEcho",
    }


def test_main_denies_when_auto_switch_fails(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T --body-file B"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=False,
    )
    assert exit_code == 0
    assert switch_invocations == ["JonEcho"]
    payload = json.loads(stdout_text)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    deny_reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert "JonEcho" in deny_reason
    assert "jl-cmd" in deny_reason
    assert "gh auth switch --user JonEcho" in deny_reason
    state_file = hook_module._state_file_path("test-session-001")
    assert not state_file.exists()


def test_main_no_op_when_active_account_matches(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T --body-file B"),
        active_account_or_none="JonEcho",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []
    state_file = hook_module._state_file_path("test-session-001")
    assert not state_file.exists()


def test_main_allows_when_active_account_matches_case_insensitively(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    """GitHub usernames are case-insensitive; ``jonecho`` env value matches ``JonEcho`` canonical login."""
    monkeypatch.setenv("GITHUB_DEFAULT_ACCOUNT", "jonecho")
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T --body-file B"),
        active_account_or_none="JonEcho",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []
    state_file = hook_module._state_file_path("test-session-001")
    assert not state_file.exists()


def test_main_allows_when_active_account_matches_canonical_case(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    """Symmetric to the previous test: canonical-case env value matches lower-case login response."""
    monkeypatch.setenv("GITHUB_DEFAULT_ACCOUNT", "JonEcho")
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T --body-file B"),
        active_account_or_none="jonecho",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []
    state_file = hook_module._state_file_path("test-session-001")
    assert not state_file.exists()


def test_main_allows_when_required_account_unset(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    monkeypatch.delenv("GITHUB_DEFAULT_ACCOUNT", raising=False)
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T --body-file B"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_allows_web_flow_even_when_mismatched(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --web --title T"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_allows_short_web_flag_even_when_mismatched(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create -w --title T"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_allows_non_bash_tool(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    stdin_text = json.dumps(
        {
            "tool_name": "Write",
            "tool_input": {"file_path": "x", "content": "y"},
            "session_id": "test-session-001",
        }
    )
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        stdin_text,
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_allows_unrelated_bash_command(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("git status"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_allows_gh_pr_edit(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr edit 10 --title X"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_allows_when_active_account_undetermined(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T"),
        active_account_or_none=None,
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


def test_main_allows_invalid_stdin_json(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        "not-json",
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert stdout_text == ""
    assert switch_invocations == []


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


def test_active_gh_account_returns_login_on_success() -> None:
    completed = mock.Mock(returncode=0, stdout="JonEcho\n")
    with mock.patch.object(hook_module.subprocess, "run", return_value=completed):
        assert hook_module._active_gh_account() == "JonEcho"


def test_active_gh_account_returns_none_on_nonzero_exit() -> None:
    completed = mock.Mock(returncode=1, stdout="")
    with mock.patch.object(hook_module.subprocess, "run", return_value=completed):
        assert hook_module._active_gh_account() is None


def test_active_gh_account_returns_none_when_gh_missing() -> None:
    with mock.patch.object(hook_module.subprocess, "run", side_effect=FileNotFoundError):
        assert hook_module._active_gh_account() is None


def test_active_gh_account_returns_none_on_timeout() -> None:
    with mock.patch.object(
        hook_module.subprocess,
        "run",
        side_effect=hook_module.subprocess.TimeoutExpired(cmd="gh", timeout=5),
    ):
        assert hook_module._active_gh_account() is None


def test_switch_gh_account_returns_true_on_success() -> None:
    completed = mock.Mock(returncode=0, stdout="", stderr="")
    with mock.patch.object(hook_module.subprocess, "run", return_value=completed):
        assert hook_module._switch_gh_account("JonEcho") is True


def test_switch_gh_account_returns_false_on_nonzero_exit() -> None:
    completed = mock.Mock(returncode=1, stdout="", stderr="auth failed")
    with mock.patch.object(hook_module.subprocess, "run", return_value=completed):
        assert hook_module._switch_gh_account("JonEcho") is False


def test_switch_gh_account_returns_false_when_gh_missing() -> None:
    with mock.patch.object(hook_module.subprocess, "run", side_effect=FileNotFoundError):
        assert hook_module._switch_gh_account("JonEcho") is False


def test_switch_gh_account_returns_false_on_timeout() -> None:
    with mock.patch.object(
        hook_module.subprocess,
        "run",
        side_effect=hook_module.subprocess.TimeoutExpired(cmd="gh", timeout=10),
    ):
        assert hook_module._switch_gh_account("JonEcho") is False


def test_main_denies_and_reverses_switch_when_state_write_fails(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    monkeypatch.setattr(
        hook_module,
        "_write_swap_state",
        lambda state_file, original_account, primary_account: False,
    )
    exit_code, stdout_text, switch_invocations = _run_hook_with(
        _make_stdin_payload("gh pr create --title T --body-file B"),
        active_account_or_none="jl-cmd",
        monkeypatch=monkeypatch,
        switch_succeeds=True,
    )
    assert exit_code == 0
    assert switch_invocations == ["JonEcho", "jl-cmd"]
    payload = json.loads(stdout_text)
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    deny_reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert "state file" in deny_reason.lower()
    assert "JonEcho" in deny_reason
    assert "jl-cmd" in deny_reason


def test_main_emits_deny_even_when_reverse_switch_also_fails(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(_make_stdin_payload("gh pr create --title T")))
    captured_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_stdout)
    monkeypatch.setattr(hook_module, "_active_gh_account", lambda: "jl-cmd")
    monkeypatch.setattr(
        hook_module,
        "_write_swap_state",
        lambda state_file, original_account, primary_account: False,
    )

    switch_invocations: list[str] = []

    def _fake_switch_first_succeeds_second_fails(to_account: str) -> bool:
        switch_invocations.append(to_account)
        return len(switch_invocations) == 1

    monkeypatch.setattr(hook_module, "_switch_gh_account", _fake_switch_first_succeeds_second_fails)

    with pytest.raises(SystemExit) as exit_info:
        hook_module.main()
    exit_code = exit_info.value.code if isinstance(exit_info.value.code, int) else 0

    assert exit_code == 0
    assert switch_invocations == ["JonEcho", "jl-cmd"]
    payload = json.loads(captured_stdout.getvalue())
    assert payload["hookSpecificOutput"]["permissionDecision"] == "deny"
    deny_reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert "state file" in deny_reason.lower()


def test_strip_quoted_regions_preserves_offsets_for_double_quotes() -> None:
    original_command = "gh pr create --body \"some text\" --title T"
    stripped_command = hook_module._preprocess_command_for_matching(original_command)
    assert len(stripped_command) == len(original_command)
    assert "some text" not in stripped_command
    assert "gh pr create" in stripped_command
    assert "--title T" in stripped_command


def test_strip_quoted_regions_preserves_offsets_for_single_quotes() -> None:
    original_command = "gh pr create --body 'single quoted body' --title T"
    stripped_command = hook_module._preprocess_command_for_matching(original_command)
    assert len(stripped_command) == len(original_command)
    assert "single quoted body" not in stripped_command


def test_strip_quoted_regions_preserves_backtick_substitution_body() -> None:
    """Backticks delimit command substitution, which executes — the body must remain scannable."""
    original_command = "echo `inner cmd` && gh pr create --title T"
    stripped_command = hook_module._preprocess_command_for_matching(original_command)
    assert len(stripped_command) == len(original_command)
    assert "inner cmd" in stripped_command
    assert "gh pr create" in stripped_command


def test_strip_quoted_regions_preserves_dollar_paren_substitution_body() -> None:
    """``$(...)`` substitution body must remain scannable for the same reason as backticks."""
    original_command = "echo $(inner cmd) && gh pr create --title T"
    stripped_command = hook_module._preprocess_command_for_matching(original_command)
    assert len(stripped_command) == len(original_command)
    assert "inner cmd" in stripped_command
    assert "gh pr create" in stripped_command


def test_strip_quoted_regions_preserves_dollar_paren_inside_double_quotes() -> None:
    """``"$(...)"`` substitution body remains scannable even when wrapped in double quotes."""
    original_command = 'echo "$(inner cmd)" && gh pr create --title T'
    stripped_command = hook_module._preprocess_command_for_matching(original_command)
    assert len(stripped_command) == len(original_command)
    assert "inner cmd" in stripped_command
    assert "gh pr create" in stripped_command


def test_strip_quoted_regions_handles_escaped_quote_inside_double_quotes() -> None:
    original_command = "gh pr create --body \"escaped \\\" quote\" --title T"
    stripped_command = hook_module._preprocess_command_for_matching(original_command)
    assert len(stripped_command) == len(original_command)
    assert "escaped" not in stripped_command
    assert "--title T" in stripped_command


def test_command_invokes_gh_pr_create_ignores_literal_inside_quotes() -> None:
    assert not hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching("echo \"gh pr create docs\"")
    )


def test_command_invokes_gh_pr_create_ignores_literal_inside_single_quotes() -> None:
    assert not hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching("echo 'gh pr create docs'")
    )


def test_command_invokes_gh_pr_create_still_matches_unquoted_invocation() -> None:
    assert hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching(
            "gh pr create --body \"see docs about gh pr create\""
        )
    )


def test_command_uses_web_flag_ignores_dash_w_inside_body_string() -> None:
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            "gh pr create --title T --body \"see -w for web\""
        )
    )


def test_command_uses_web_flag_handles_separator_inside_quoted_body() -> None:
    assert hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            "gh pr create --title \"T | foo\" --web"
        )
    )


def test_command_uses_web_flag_ignores_long_web_inside_quoted_body() -> None:
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            "gh pr create --title T --body \"docs --web link\""
        )
    )


def test_write_swap_state_uses_owner_only_permissions(
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    """On POSIX the state file is chmod'd to 0o600 after write."""
    if sys.platform.startswith("win"):
        return
    state_file = hook_module._state_file_path("perm-test-session")
    has_written_state = hook_module._write_swap_state(
        state_file,
        original_account="jl-cmd",
        primary_account="JonEcho",
    )
    assert has_written_state is True
    file_mode_bits = stat.S_IMODE(os.stat(state_file).st_mode)
    assert file_mode_bits == STATE_FILE_PERMISSION_MODE


def test_write_swap_state_unlinks_file_when_chmod_fails(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    """A chmod failure after write unlinks the file so it cannot leak."""
    def _fake_chmod(*_args: object, **_kwargs: object) -> None:
        raise OSError("chmod failed")

    monkeypatch.setattr(hook_module.os, "chmod", _fake_chmod)
    state_file = hook_module._state_file_path("chmod-fail-session")
    has_written_state = hook_module._write_swap_state(
        state_file,
        original_account="jl-cmd",
        primary_account="JonEcho",
    )
    assert has_written_state is False
    assert not state_file.exists()


def test_module_imports_and_main_runs_under_production_sys_path_layout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Module imports cleanly AND main() executes a no-op path when only blocking/ is on sys.path.

    pytest's ``pythonpath = packages/claude-dev-env/hooks`` lets the
    in-test import work even without the sys.path shim. The Claude Code
    hook runner does NOT set that path — it invokes
    ``python3 ${CLAUDE_PLUGIN_ROOT}/hooks/blocking/gh_pr_author_enforcer.py``,
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
        "gh_pr_author_enforcer_production_path_check",
        blocking_dir / "gh_pr_author_enforcer.py",
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


def test_command_uses_web_flag_false_when_one_of_two_gh_pr_create_lacks_web() -> None:
    """Chained ``gh pr create --web && gh pr create --title T`` must trigger the enforcer.

    The first segment's ``--web`` does not exempt the second segment.
    A short-circuiting ``all()`` over every segment returns False when
    any segment lacks the flag, so ``_command_uses_web_flag_in_stripped``
    returns False here and the enforcer proceeds to its swap path.
    """
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            "gh pr create --web && gh pr create --title T"
        )
    )


def test_command_uses_web_flag_true_when_both_gh_pr_create_have_web() -> None:
    """Two chained ``gh pr create`` invocations both carrying ``--web`` are still browser-flow."""
    assert hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            "gh pr create --web && gh pr create --web --title T"
        )
    )


def test_command_uses_web_flag_ignores_w_after_newline_separator() -> None:
    """Newline counts as a command separator; ``-w`` on the next line does not bind to gh pr create."""
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            "gh pr create --title T\ncurl -w '%{http_code}'"
        )
    )


def test_command_substitution_with_gh_pr_create_inside_is_still_detected() -> None:
    """``$(...)`` substitution body executes, so an inner ``gh pr create`` is real."""
    assert hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching('echo "$(gh pr create --title T)"')
    )


def test_backtick_substitution_with_gh_pr_create_inside_is_still_detected() -> None:
    """Backtick substitution body executes, so an inner ``gh pr create`` is real."""
    assert hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching("echo `gh pr create --title T`")
    )


def test_write_swap_state_does_not_overwrite_symlink_target(
    isolated_state_directory: pathlib.Path,
) -> None:
    """A symlink at the predictable state path must never let the enforcer overwrite the target.

    On POSIX ``O_NOFOLLOW`` causes the atomic ``os.open`` to fail
    immediately, so ``_write_swap_state`` returns False and the
    attacker's target file is untouched. On Windows ``O_NOFOLLOW`` is
    not exposed, but ``O_EXCL`` still rejects the create against the
    existing symlink — the retry then unlinks the symlink (not the
    target) and writes a fresh state file at the predictable path,
    again leaving the attacker's target untouched.

    The security guarantee being tested is "the attacker file is not
    written to," which holds on both platforms.
    """
    if not hasattr(os, "symlink"):
        return
    state_file = hook_module._state_file_path("symlink-attack-session")
    attacker_target_file = isolated_state_directory / "attacker_target.txt"
    untouched_marker_text = "untouched-by-attack"
    attacker_target_file.write_text(untouched_marker_text, encoding="utf-8")
    try:
        os.symlink(attacker_target_file, state_file)
    except (OSError, NotImplementedError):
        return
    hook_module._write_swap_state(
        state_file,
        original_account="jl-cmd",
        primary_account="JonEcho",
    )
    assert attacker_target_file.read_text(encoding="utf-8") == untouched_marker_text


def test_write_swap_state_recovers_after_stale_file_collision(
    isolated_state_directory: pathlib.Path,
) -> None:
    """A stale file at the predictable path is unlinked and the create retried once."""
    state_file = hook_module._state_file_path("stale-collision-session")
    state_file.write_text("stale-prior-session-contents", encoding="utf-8")
    has_written_state = hook_module._write_swap_state(
        state_file,
        original_account="jl-cmd",
        primary_account="JonEcho",
    )
    assert has_written_state is True
    persisted_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert persisted_state == {
        "original_account": "jl-cmd",
        "primary_account": "JonEcho",
    }


def test_write_swap_state_loops_through_short_writes(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    """Regression for finding 1: short os.write returns must not truncate the JSON state file.

    The fake ``os.write`` writes at most three bytes per call, simulating
    a kernel that signals partial writes. The helper must loop until
    every byte lands on disk so the resulting file holds the complete
    JSON payload and the restore hook can parse it successfully.
    """
    real_os_write = hook_module.os.write

    def _short_writer(file_descriptor: int, payload: bytes) -> int:
        return real_os_write(file_descriptor, payload[:3])

    monkeypatch.setattr(hook_module.os, "write", _short_writer)
    state_file = hook_module._state_file_path("short-write-session")
    has_written_state = hook_module._write_swap_state(
        state_file,
        original_account="jl-cmd",
        primary_account="JonEcho",
    )
    assert has_written_state is True
    persisted_state = json.loads(state_file.read_text(encoding="utf-8"))
    assert persisted_state == {
        "original_account": "jl-cmd",
        "primary_account": "JonEcho",
    }


def test_write_swap_state_returns_false_when_os_write_keeps_returning_zero(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    """Regression for finding 1 guard: ``os.write`` returning 0 must terminate as a failure.

    A descriptor that cannot accept any more bytes signals zero from
    ``os.write``. The helper must treat that as a write failure and
    unlink the partially-written file, rather than spinning forever or
    leaving a truncated file on disk.
    """
    monkeypatch.setattr(hook_module.os, "write", lambda *_args, **_kwargs: 0)
    state_file = hook_module._state_file_path("zero-write-session")
    has_written_state = hook_module._write_swap_state(
        state_file,
        original_account="jl-cmd",
        primary_account="JonEcho",
    )
    assert has_written_state is False
    assert not state_file.exists()


def test_command_uses_web_flag_ignores_web_inside_substitution_body() -> None:
    """Regression for finding 4: ``$(echo --web)`` body must not flip the enforcer into browser-flow.

    ``--web`` inside a substitution is an argument to the subshell
    command (``echo``), not a flag on the outer ``gh pr create``. The
    web-flag detector blanks substitution bodies before searching, so
    this command continues to trigger the account swap.
    """
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            'gh pr create --title "$(echo --web)" --body-file B'
        )
    )


def test_command_uses_web_flag_ignores_web_after_inline_bash_comment() -> None:
    """Regression for findings 3 & 4: ``# --web`` is a comment and must not match the web flag."""
    assert not hook_module._command_uses_web_flag_in_stripped(
        hook_module._preprocess_command_for_matching(
            "gh pr create --title T # --web"
        )
    )


def test_active_gh_account_returns_none_on_permission_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression for finding 6: ``PermissionError`` from subprocess.run must not crash the hook."""
    monkeypatch.setattr(
        hook_module.subprocess,
        "run",
        mock.Mock(side_effect=PermissionError("not executable")),
    )
    assert hook_module._active_gh_account() is None


def test_active_gh_account_returns_none_on_generic_os_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Any ``OSError`` subclass from subprocess.run must follow the documented skip path."""
    monkeypatch.setattr(
        hook_module.subprocess,
        "run",
        mock.Mock(side_effect=OSError("spawn refused")),
    )
    assert hook_module._active_gh_account() is None


def test_write_swap_state_unlinks_file_when_os_close_raises_after_successful_write(
    monkeypatch: pytest.MonkeyPatch,
    isolated_state_directory: pathlib.Path,
) -> None:
    """An ``OSError`` from ``os.close`` after a successful write rolls back the state file.

    Delayed-writeback filesystems (NFS, FUSE) can surface a write error
    at close time rather than at write time. The helper must treat
    that as a write failure: unlink the partially-written file and
    return False so the caller reverses the gh auth switch.
    """
    real_os_close = hook_module.os.close
    real_os_write = hook_module.os.write
    write_invocation_counter = {"value": 0}

    def _counting_os_write(file_descriptor: int, payload: bytes) -> int:
        write_invocation_counter["value"] += 1
        return real_os_write(file_descriptor, payload)

    def _close_raises_after_successful_write(file_descriptor: int) -> None:
        real_os_close(file_descriptor)
        if write_invocation_counter["value"] > 0:
            raise OSError("delayed writeback failure on close")

    monkeypatch.setattr(hook_module.os, "write", _counting_os_write)
    monkeypatch.setattr(hook_module.os, "close", _close_raises_after_successful_write)
    state_file = hook_module._state_file_path("close-fail-session")
    has_written_state = hook_module._write_swap_state(
        state_file,
        original_account="jl-cmd",
        primary_account="JonEcho",
    )
    assert has_written_state is False
    assert not state_file.exists()


def test_command_invokes_gh_pr_create_matches_if_keyword_prefix() -> None:
    """Regression for finding 1: ``if gh pr create ...; then`` must trigger the enforcer."""
    assert hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching(
            "if gh pr create --title T; then echo ok; fi"
        )
    )


def test_command_invokes_gh_pr_create_matches_then_keyword_prefix() -> None:
    """Regression for finding 1: ``if foo; then gh pr create`` slipping past needs catching."""
    assert hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching(
            "if foo; then gh pr create --title T; fi"
        )
    )


def test_command_invokes_gh_pr_create_matches_else_keyword_prefix() -> None:
    """Regression for finding 1: ``else gh pr create`` after an if branch must match."""
    assert hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching(
            "if foo; then bar; else gh pr create --title T; fi"
        )
    )


def test_command_invokes_gh_pr_create_matches_elif_keyword_prefix() -> None:
    """Regression for finding 1: ``elif`` precedes a real ``gh pr create`` in the same shape."""
    assert hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching(
            "if foo; then bar; elif gh pr create --title T; then ok; fi"
        )
    )


def test_command_invokes_gh_pr_create_matches_while_keyword_prefix() -> None:
    """Regression for finding 1: ``while gh pr create`` loop guard is a real invocation."""
    assert hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching(
            "while gh pr create --title T; do echo loop; done"
        )
    )


def test_command_invokes_gh_pr_create_matches_until_keyword_prefix() -> None:
    """Regression for finding 1: ``until gh pr create`` loop guard is a real invocation."""
    assert hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching(
            "until gh pr create --title T; do sleep 1; done"
        )
    )


def test_command_invokes_gh_pr_create_matches_do_keyword_prefix() -> None:
    """Regression for finding 1: ``for ...; do gh pr create`` body must match."""
    assert hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching(
            "for tag in T1 T2; do gh pr create --title $tag; done"
        )
    )


def test_command_invokes_gh_pr_create_matches_bang_negation_prefix() -> None:
    """Regression for finding 1: ``! gh pr create`` (negate exit status) is a real invocation."""
    assert hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching(
            "! gh pr create --title T"
        )
    )


def test_command_invokes_gh_pr_create_still_rejects_keyword_substring() -> None:
    """A bash keyword substring inside a longer identifier must not flip the matcher.

    ``notify_then gh pr create`` is a single hyphenated/underscored
    identifier followed by text; the regex must not detect ``then`` as
    a real keyword prefix here.
    """
    assert not hook_module._command_invokes_gh_pr_create_in_stripped(
        hook_module._preprocess_command_for_matching("notify_then gh pr create")
    )


def test_build_state_write_failure_message_describes_rollback_success(
    isolated_state_directory: pathlib.Path,
) -> None:
    """Regression for finding 6: the deny text on rollback success names the original account.

    When the reverse ``gh auth switch`` succeeds the message must
    describe the swap as reversed and tell the user the original
    account is back in place.
    """
    deny_text = hook_module._build_state_write_failure_message(
        required_account="JonEcho",
        current_account="jl-cmd",
        state_file=isolated_state_directory / "stub_state.json",
        has_rollback_succeeded=True,
    )
    assert "swap was reversed" in deny_text
    assert "JonEcho" in deny_text
    assert "jl-cmd" in deny_text


def test_build_state_write_failure_message_describes_rollback_failure(
    isolated_state_directory: pathlib.Path,
) -> None:
    """Regression for finding 6: the deny text on rollback failure flags the still-swapped state.

    When the reverse switch ALSO fails the message must surface that
    the user is still on the required account so the user knows the
    rollback did not succeed and recovery is required.
    """
    deny_text = hook_module._build_state_write_failure_message(
        required_account="JonEcho",
        current_account="jl-cmd",
        state_file=isolated_state_directory / "stub_state.json",
        has_rollback_succeeded=False,
    )
    assert "reverse" in deny_text.lower()
    assert "ALSO failed" in deny_text
    assert "still" in deny_text.lower()
    assert "JonEcho" in deny_text
    assert "jl-cmd" in deny_text


def test_main_deny_message_names_rollback_failure_when_reverse_switch_fails(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    """Regression for finding 6: end-to-end check that the deny message branch wires up correctly.

    When state-write fails AND the rollback switch also fails, the
    deny payload must include the "ALSO failed" language so the user
    is told the gh CLI is still on ``required_account``.
    """
    monkeypatch.setattr(sys, "stdin", io.StringIO(_make_stdin_payload("gh pr create --title T")))
    captured_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_stdout)
    monkeypatch.setattr(hook_module, "_active_gh_account", lambda: "jl-cmd")
    monkeypatch.setattr(
        hook_module,
        "_write_swap_state",
        lambda state_file, original_account, primary_account: False,
    )

    switch_invocations: list[str] = []

    def _fake_switch_first_succeeds_second_fails(to_account: str) -> bool:
        switch_invocations.append(to_account)
        return len(switch_invocations) == 1

    monkeypatch.setattr(hook_module, "_switch_gh_account", _fake_switch_first_succeeds_second_fails)

    with pytest.raises(SystemExit):
        hook_module.main()

    assert switch_invocations == ["JonEcho", "jl-cmd"]
    payload = json.loads(captured_stdout.getvalue())
    deny_reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert "ALSO failed" in deny_reason
    assert "still" in deny_reason.lower()


def test_main_deny_message_keeps_reversal_language_when_rollback_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    required_account_jonecho: str,
    isolated_state_directory: pathlib.Path,
) -> None:
    """Regression for finding 6 guard: rollback-success path must NOT carry the failure language."""
    monkeypatch.setattr(sys, "stdin", io.StringIO(_make_stdin_payload("gh pr create --title T")))
    captured_stdout = io.StringIO()
    monkeypatch.setattr(sys, "stdout", captured_stdout)
    monkeypatch.setattr(hook_module, "_active_gh_account", lambda: "jl-cmd")
    monkeypatch.setattr(
        hook_module,
        "_write_swap_state",
        lambda state_file, original_account, primary_account: False,
    )

    switch_invocations: list[str] = []

    def _fake_switch_always_succeeds(to_account: str) -> bool:
        switch_invocations.append(to_account)
        return True

    monkeypatch.setattr(hook_module, "_switch_gh_account", _fake_switch_always_succeeds)

    with pytest.raises(SystemExit):
        hook_module.main()

    assert switch_invocations == ["JonEcho", "jl-cmd"]
    payload = json.loads(captured_stdout.getvalue())
    deny_reason = payload["hookSpecificOutput"]["permissionDecisionReason"]
    assert "swap was reversed" in deny_reason
    assert "ALSO failed" not in deny_reason
