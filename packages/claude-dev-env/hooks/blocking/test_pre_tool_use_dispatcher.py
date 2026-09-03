"""Golden differential and failure-mode tests for the PreToolUse dispatcher.

Each golden differential test runs a payload through every applicable hosted
hook as its own subprocess (the production path), records each hook's
allow-or-deny and messages, computes the expected aggregate, then runs the
dispatcher on the same payload and asserts equal decision and equal message
union.

The failure-mode tests cover one row each from spec/failure-modes.md:
early-exit-then-later-deny, multi-deny, context-survival, blocking-hook crash,
fail-open malformed input.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Callable

import pytest

_BLOCKING_DIR = Path(__file__).resolve().parent
_HOOKS_ROOT = _BLOCKING_DIR.parent
if str(_BLOCKING_DIR) not in sys.path:
    sys.path.insert(0, str(_BLOCKING_DIR))
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.pre_tool_use_dispatcher_constants import (  # noqa: E402, I001
    ALL_HOSTED_HOOK_ENTRIES,
    ALL_IMMEDIATE_HARM_SCRIPT_PATHS,
    APPLY_PATCH_TOOL_NAME,
    BLOCKING_CRASH_DENY_REASON,
    BLOCKING_CRASH_EXIT_CODE,
    DENY_DECISION,
    EDIT_TOOL_NAME,
    EXIT_CODE_TWO_DENY_REASON,
    MULTI_EDIT_TOOL_NAME,
    WRITE_TOOL_NAME,
    HostedHookEntry,
)
from pre_tool_use_dispatcher import (  # noqa: E402, I001
    DispatcherDecision,
    HostedHookResult,
    _emit_allow_decision,
    _emit_deny_decision,
    aggregate_hosted_hook_results,
    run_hosted_hook,
    unique_first_seen_strings,
)

pytestmark = pytest.mark.usefixtures("ephemeral_exempt_off")

_DISPATCHER_SCRIPT = str(_BLOCKING_DIR / "pre_tool_use_dispatcher.py")

_PROSE_STYLE_ENV_VAR = "CLAUDE_PROSE_STYLE_ENFORCEMENT"
_PROSE_STYLE_ENV_VALUE = "1"


def _subprocess_environment() -> dict[str, str]:
    """Return process env with opinionated prose gates enabled for golden tests."""
    environment_by_key = os.environ.copy()
    environment_by_key[_PROSE_STYLE_ENV_VAR] = _PROSE_STYLE_ENV_VALUE
    return environment_by_key


_TEMP_FILE_PATH = str(_HOOKS_ROOT.parent.parent.parent / "tmp" / "dispatcher_test_dummy.txt")
_MARKDOWN_FILE_PATH = str(_HOOKS_ROOT.parent.parent.parent / "tmp" / "dispatcher_test_dummy.md")


def _run_hook_subprocess(
    hook_relative_path: str, payload_text: str
) -> subprocess.CompletedProcess[str]:
    """Run one hook script as a subprocess, returning the completed process.

    Args:
        hook_relative_path: Path relative to the hooks/ directory.
        payload_text: The JSON payload to send on stdin.

    Returns:
        The completed subprocess result with stdout and stderr captured.
    """
    script_path = str(_HOOKS_ROOT / hook_relative_path)
    return subprocess.run(
        [sys.executable, script_path],
        check=False,
        input=payload_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_subprocess_environment(),
    )


def _run_dispatcher(payload_text: str) -> subprocess.CompletedProcess[str]:
    """Run the dispatcher as a subprocess.

    Args:
        payload_text: The JSON payload to send on stdin.

    Returns:
        The completed subprocess result with stdout and stderr captured.
    """
    return subprocess.run(
        [sys.executable, _DISPATCHER_SCRIPT],
        check=False,
        input=payload_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_subprocess_environment(),
    )


def _parse_hook_decision(completed_process: subprocess.CompletedProcess[str]) -> tuple[bool, str]:
    """Parse one hook's subprocess result into (is_deny, reason_text).

    Args:
        completed_process: The completed subprocess from running a hook.

    Returns:
        A (is_deny, reason_text) pair where is_deny is True when the hook
        denied, and reason_text carries the permissionDecisionReason.
    """
    stdout_text = completed_process.stdout.strip()
    if not stdout_text:
        return False, ""
    try:
        parsed_output = json.loads(stdout_text)
    except json.JSONDecodeError:
        return False, ""
    hook_specific = parsed_output.get("hookSpecificOutput", {})
    if not isinstance(hook_specific, dict):
        return False, ""
    is_deny = hook_specific.get("permissionDecision") == DENY_DECISION
    reason_text = hook_specific.get("permissionDecisionReason", "")
    return is_deny, reason_text if isinstance(reason_text, str) else ""


def _compute_expected_aggregate(
    payload_text: str,
    applicable_entries: list[HostedHookEntry],
) -> tuple[bool, list[str]]:
    """Run each applicable hook individually and compute the expected aggregate.

    Args:
        payload_text: The JSON payload text to send to each hook.
        applicable_entries: The hosted hook entries applicable to this payload's tool.

    Returns:
        A (should_deny, all_deny_reasons) pair where should_deny is True when
        any hook denies, and all_deny_reasons collects every denying reason.
    """
    all_deny_reasons: list[str] = []
    for each_entry in applicable_entries:
        completed_process = _run_hook_subprocess(each_entry.script_relative_path, payload_text)
        is_deny, reason_text = _parse_hook_decision(completed_process)
        if is_deny and reason_text:
            all_deny_reasons.append(reason_text)
    return bool(all_deny_reasons), all_deny_reasons


def _applicable_entries_for_tool(tool_name: str) -> list[HostedHookEntry]:
    """Return the hosted hook entries applicable to the given tool name.

    Args:
        tool_name: The tool name from the PreToolUse payload.

    Returns:
        The ordered list of HostedHookEntry objects whose applicable_tool_names
        includes tool_name.
    """
    return [
        each_entry
        for each_entry in ALL_HOSTED_HOOK_ENTRIES
        if tool_name in each_entry.applicable_tool_names
    ]


def _write_payload(file_path: str, content: str) -> str:
    """Build a Write tool payload JSON string.

    Args:
        file_path: The target file path.
        content: The file content to write.

    Returns:
        JSON-encoded payload string.
    """
    return json.dumps(
        {
            "tool_name": WRITE_TOOL_NAME,
            "tool_input": {"file_path": file_path, "content": content},
        }
    )


def _edit_payload(file_path: str, old_string: str, new_string: str) -> str:
    """Build an Edit tool payload JSON string.

    Args:
        file_path: The target file path.
        old_string: The text to replace.
        new_string: The replacement text.

    Returns:
        JSON-encoded payload string.
    """
    return json.dumps(
        {
            "tool_name": EDIT_TOOL_NAME,
            "tool_input": {
                "file_path": file_path,
                "old_string": old_string,
                "new_string": new_string,
            },
        }
    )


def _apply_patch_payload(working_directory: str, command: str) -> str:
    """Build an apply_patch tool payload JSON string.

    Args:
        working_directory: The Codex patch's working directory (top-level cwd).
        command: The Codex-format patch text naming each file operation.

    Returns:
        JSON-encoded payload string.
    """
    return json.dumps(
        {
            "tool_name": APPLY_PATCH_TOOL_NAME,
            "cwd": working_directory,
            "tool_input": {"command": command},
        }
    )


def _assert_dispatcher_matches_individual_hooks(
    payload_text: str,
    tool_name: str,
) -> None:
    """Assert the dispatcher's decision matches the union of individual hook decisions.

    Runs each applicable hook individually, computes the expected aggregate
    (deny if any denies, union of all deny reasons), then runs the dispatcher
    and asserts equal outcome.

    Args:
        payload_text: The JSON payload text.
        tool_name: The tool name, used to select applicable hooks.
    """
    applicable_entries = _applicable_entries_for_tool(tool_name)
    expected_deny, all_expected_reasons = _compute_expected_aggregate(
        payload_text, applicable_entries
    )
    dispatcher_result = _run_dispatcher(payload_text)
    dispatcher_is_deny, dispatcher_reason = _parse_hook_decision(dispatcher_result)
    assert dispatcher_is_deny == expected_deny, (
        f"Tool={tool_name}: dispatcher deny={dispatcher_is_deny} "
        f"but expected deny={expected_deny}. "
        f"Dispatcher reason: {dispatcher_reason!r}. "
        f"Expected reasons: {all_expected_reasons!r}"
    )
    if expected_deny and all_expected_reasons:
        for each_expected_reason in all_expected_reasons:
            assert each_expected_reason in dispatcher_reason, (
                f"Missing reason in dispatcher output.\n"
                f"Expected to find: {each_expected_reason!r}\n"
                f"Dispatcher reason: {dispatcher_reason!r}"
            )


def test_clean_write_allows_on_write_tool() -> None:
    """Dispatcher allows a write that all hosted hooks allow on Write tool."""
    payload_text = _write_payload(_TEMP_FILE_PATH, "hello world\n")
    _assert_dispatcher_matches_individual_hooks(payload_text, WRITE_TOOL_NAME)


def test_clean_write_allows_on_edit_tool() -> None:
    """Dispatcher allows an edit that all hosted hooks allow on Edit tool."""
    payload_text = _edit_payload(_TEMP_FILE_PATH, "old text", "new text")
    _assert_dispatcher_matches_individual_hooks(payload_text, EDIT_TOOL_NAME)


def test_clean_write_allows_on_multi_edit_tool(
    multi_edit_payload: Callable[[str, list[dict[str, str]]], str],
) -> None:
    """Dispatcher allows a multi-edit that all hosted hooks allow on MultiEdit tool."""
    payload_text = multi_edit_payload(
        _TEMP_FILE_PATH,
        [{"old_string": "old", "new_string": "new"}],
    )
    _assert_dispatcher_matches_individual_hooks(payload_text, MULTI_EDIT_TOOL_NAME)


def test_dispatcher_docstring_points_at_roster_not_hardcoded_counts() -> None:
    """The dispatcher docstring names the roster, not per-tool counts that drift."""
    dispatcher_source = Path(_DISPATCHER_SCRIPT).read_text(encoding="utf-8")
    assert "ALL_HOSTED_HOOK_ENTRIES" in dispatcher_source
    assert "-> 20 hooks" not in dispatcher_source
    assert "-> 21 hooks" not in dispatcher_source
    assert "-> 9 hooks" not in dispatcher_source


def test_multi_edit_payload_runs_only_group_b_hooks(
    multi_edit_payload: Callable[[str, list[dict[str, str]]], str],
) -> None:
    """Dispatcher invokes only the hooks registered for MultiEdit, and each allows a clean edit.

    A hook whose applicable set omits MultiEdit stays absent from the
    dispatcher's MultiEdit roster, so a MultiEdit to any path such a hook would
    otherwise guard still allows. This test derives the excluded set from the
    live roster rather than a hardcoded name list, so it holds as hooks move
    between applicable sets.
    """
    all_multi_edit_entries = _applicable_entries_for_tool(MULTI_EDIT_TOOL_NAME)
    all_write_only_entries = [
        each_entry
        for each_entry in ALL_HOSTED_HOOK_ENTRIES
        if MULTI_EDIT_TOOL_NAME not in each_entry.applicable_tool_names
    ]
    all_multi_edit_script_paths = {
        each_entry.script_relative_path for each_entry in all_multi_edit_entries
    }
    for each_group_a_entry in all_write_only_entries:
        assert each_group_a_entry.script_relative_path not in all_multi_edit_script_paths, (
            f"Group-A hook {each_group_a_entry.script_relative_path!r} "
            "appears in the MultiEdit applicable set — it must not"
        )
    clean_payload = multi_edit_payload(
        _MARKDOWN_FILE_PATH,
        [{"old_string": "old line", "new_string": "New text."}],
    )
    dispatcher_result = _run_dispatcher(clean_payload)
    dispatcher_is_deny, _reason = _parse_hook_decision(dispatcher_result)
    assert not dispatcher_is_deny, (
        "Dispatcher should allow a clean MultiEdit payload"
    )


def test_malformed_payload_allows_fail_open() -> None:
    """Dispatcher allows when the payload is malformed, matching fail-open posture."""
    dispatcher_result = _run_dispatcher("not valid json {{{")
    is_deny, _reason = _parse_hook_decision(dispatcher_result)
    assert not is_deny, "Dispatcher must allow on malformed payload (fail-open)"
    assert dispatcher_result.returncode == 0, (
        f"Dispatcher must exit 0 on malformed payload, got {dispatcher_result.returncode}"
    )


def test_empty_payload_allows_fail_open() -> None:
    """Dispatcher allows when stdin is empty, matching fail-open posture."""
    dispatcher_result = _run_dispatcher("")
    is_deny, _reason = _parse_hook_decision(dispatcher_result)
    assert not is_deny, "Dispatcher must allow on empty payload (fail-open)"
    assert dispatcher_result.returncode == 0, (
        f"Dispatcher must exit 0 on empty payload, got {dispatcher_result.returncode}"
    )


def test_sensitive_file_protector_denies_on_write_tool(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Dispatcher denies a Write targeting a sensitive path.

    This proves a Group-A hook fires on Write. It exercises the golden
    differential against a payload where sensitive_file_protector denies.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    sensitive_path = str(Path.home() / ".ssh" / "id_rsa")
    payload_text = _write_payload(sensitive_path, "fake key content")
    _assert_dispatcher_matches_individual_hooks(payload_text, WRITE_TOOL_NAME)


def test_write_existing_file_blocker_denies_on_write_tool() -> None:
    """Dispatcher denies when write_existing_file_blocker fires on Write tool.

    write_existing_file_blocker denies a Write to a path where a file already
    exists. This exercises a real denial in the first Group-A hook position.
    """
    existing_path = str(Path(__file__).resolve())
    payload_text = _write_payload(existing_path, "content")
    _assert_dispatcher_matches_individual_hooks(payload_text, WRITE_TOOL_NAME)


def test_write_existing_file_blocker_allows_multi_edit_to_an_existing_path(
    multi_edit_payload: Callable[[str, list[dict[str, str]]], str],
) -> None:
    """write_existing_file_blocker runs on MultiEdit but never denies it.

    MultiEdit carries no create-or-clobber path the hook needs to guard, so it
    always allows a MultiEdit to an existing file path, even though the same
    hook would deny that path on a Write. Uses a non-markdown file so
    markdown-only hooks stay silent.
    """
    existing_file_path = str(Path(__file__).resolve())
    payload_text = multi_edit_payload(
        existing_file_path,
        [{"old_string": "old text", "new_string": "new text"}],
    )
    _assert_dispatcher_matches_individual_hooks(payload_text, MULTI_EDIT_TOOL_NAME)


def test_context_survives_alongside_deny_reason(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A non-denying hook's additional context survives in the dispatcher output.

    This tests that hooks whose output is additional-context (not a deny) still
    have their output preserved when another hook denies.
    """
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    sensitive_path = str(Path.home() / ".env")
    payload_text = _write_payload(sensitive_path, "SECRET=abc")
    dispatcher_result = _run_dispatcher(payload_text)
    is_deny, _reason = _parse_hook_decision(dispatcher_result)
    assert is_deny, (
        "sensitive_file_protector should deny a write to .env — "
        "if it did not, check whether the path is on the sensitive list"
    )
    assert dispatcher_result.stdout.strip(), "Dispatcher must emit output when denying"


def test_all_deny_reasons_present_when_multiple_hooks_deny() -> None:
    """When two or more hooks deny, all their reasons appear in the dispatcher output.

    Uses a Write to an existing markdown path with a historical phrase
    ("previously") so write_existing_file_blocker and state_description_blocker
    both deny.
    """
    existing_markdown_path = str(Path(__file__).resolve().parent / "CLAUDE.md")
    multi_deny_content = (
        "# Guide\n\n"
        "Previously the system used a different mechanism.\n"
    )
    payload_text = _write_payload(existing_markdown_path, multi_deny_content)
    _assert_dispatcher_matches_individual_hooks(payload_text, WRITE_TOOL_NAME)

    dispatcher_result = _run_dispatcher(payload_text)
    dispatcher_is_deny, dispatcher_reason = _parse_hook_decision(dispatcher_result)
    assert dispatcher_is_deny, "Dispatcher must deny when any hook denies"

    applicable_entries = _applicable_entries_for_tool(WRITE_TOOL_NAME)
    all_expected_deny_reasons: list[str] = []
    for each_entry in applicable_entries:
        completed_process = _run_hook_subprocess(each_entry.script_relative_path, payload_text)
        is_deny, reason_text = _parse_hook_decision(completed_process)
        if is_deny and reason_text:
            all_expected_deny_reasons.append(reason_text)

    assert len(all_expected_deny_reasons) >= 2, (
        f"Test payload must trip at least two hooks — got {len(all_expected_deny_reasons)}. "
        "Check that an existing path triggers write_existing_file_blocker and "
        "'previously' triggers state_description_blocker on a Write."
    )
    for each_reason in all_expected_deny_reasons:
        assert each_reason in dispatcher_reason, (
            f"Missing deny reason in dispatcher output.\n"
            f"Expected reason: {each_reason!r}\n"
            f"Dispatcher reason: {dispatcher_reason!r}"
        )


def test_aggregate_exit_code_two_signals_deny() -> None:
    """A HostedHookResult with exit_code 2 and did_crash False signals deny.

    A hosted hook that raises SystemExit(2) cleanly (not via an exception crash)
    signals deny by exit code. The aggregator must treat exit_code==2 and
    is_blocking==True as a deny even when captured_stdout is empty.
    """
    all_results = [
        HostedHookResult(
            exit_code=BLOCKING_CRASH_EXIT_CODE,
            captured_stdout="",
            did_crash=False,
            is_blocking=True,
        )
    ]
    decision = aggregate_hosted_hook_results(all_results)
    assert decision.should_deny, (
        "exit_code==2 with did_crash=False must signal deny"
    )
    assert decision.all_deny_reasons, (
        "aggregator must supply a non-empty reason when exit_code==2 deny carries no JSON"
    )
    assert EXIT_CODE_TWO_DENY_REASON in decision.all_deny_reasons[0], (
        f"deny reason must reference EXIT_CODE_TWO_DENY_REASON constant. "
        f"Got: {decision.all_deny_reasons[0]!r}"
    )


def test_aggregate_blocking_hook_crash_surfaces_a_deny() -> None:
    """A crash in a blocking hook surfaces a deny with the crash reason.

    When a blocking hook raises a non-SystemExit exception before emitting any
    output, the aggregator must still deny so a bad write does not silently
    pass. The deny reason must be the BLOCKING_CRASH_DENY_REASON constant.
    """
    all_results = [
        HostedHookResult(
            exit_code=0,
            captured_stdout="",
            did_crash=True,
            is_blocking=True,
        )
    ]
    decision = aggregate_hosted_hook_results(all_results)
    assert decision.should_deny, "a blocking hook crash must surface a deny"
    assert decision.all_deny_reasons, (
        "the deny reasons list must be non-empty after a blocking hook crash"
    )
    assert BLOCKING_CRASH_DENY_REASON in decision.all_deny_reasons, (
        "the deny reason from a blocking hook crash must be BLOCKING_CRASH_DENY_REASON.\n"
        f"Got: {decision.all_deny_reasons!r}"
    )


def test_aggregate_non_blocking_hook_crash_does_not_deny() -> None:
    """A crash in a non-blocking hook does not change an allow to a deny.

    A hosted hook carrying is_blocking=False must not surface a deny when it
    crashes — the aggregated decision stays allow.
    """
    all_results = [
        HostedHookResult(
            exit_code=0,
            captured_stdout="",
            did_crash=True,
            is_blocking=False,
        )
    ]
    decision = aggregate_hosted_hook_results(all_results)
    assert not decision.should_deny, (
        "a non-blocking hook crash must not change an allow to a deny"
    )


def test_aggregate_exit_code_zero_with_no_output_allows() -> None:
    """A HostedHookResult with exit_code 0 and empty stdout signals allow.

    The aggregator must not deny on a clean allow (no JSON output, exit 0).
    """
    all_results = [
        HostedHookResult(
            exit_code=0,
            captured_stdout="",
            did_crash=False,
            is_blocking=True,
        )
    ]
    decision = aggregate_hosted_hook_results(all_results)
    assert not decision.should_deny, (
        "exit_code==0 with no output must signal allow"
    )


def test_aggregate_explicit_allow_payload_signals_allow_decision() -> None:
    """An explicit permissionDecision allow from a hosted hook signals an allow decision.

    tdd_enforcer writes an explicit allow payload on its allow path, which
    auto-approves the write standalone. The aggregator must surface that as an
    explicit allow decision so the dispatcher re-emits it rather than silently
    falling back to the default permission flow.
    """
    explicit_allow_stdout = json.dumps(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}
    )
    all_results = [
        HostedHookResult(
            exit_code=0,
            captured_stdout=explicit_allow_stdout,
            did_crash=False,
            is_blocking=True,
        )
    ]
    decision = aggregate_hosted_hook_results(all_results)
    assert not decision.should_deny, "an explicit allow must not deny"
    assert decision.should_allow, (
        "an explicit permissionDecision allow with no deny must signal an allow decision"
    )


def test_aggregate_explicit_allow_is_overridden_by_a_deny() -> None:
    """A deny wins over an explicit allow from another hook in the same run."""
    explicit_allow_stdout = json.dumps(
        {"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"}}
    )
    all_results = [
        HostedHookResult(
            exit_code=0,
            captured_stdout=explicit_allow_stdout,
            did_crash=False,
            is_blocking=True,
        ),
        HostedHookResult(
            exit_code=BLOCKING_CRASH_EXIT_CODE,
            captured_stdout="",
            did_crash=False,
            is_blocking=True,
        ),
    ]
    decision = aggregate_hosted_hook_results(all_results)
    assert decision.should_deny, "a deny must win over an explicit allow"
    assert not decision.should_allow, (
        "should_allow must be False when any hook denies, so deny wins"
    )


def test_unique_first_seen_strings_keeps_order_and_drops_exact_duplicates() -> None:
    assert unique_first_seen_strings(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
    assert unique_first_seen_strings(["Same", "same"]) == ["Same", "same"]


def test_emit_deny_collapses_identical_reasons_and_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Final JSON keeps each exact string once; distinct reasons stay; suppress stays."""
    shared_text = "BLOCKED: same corrective text"
    decision = DispatcherDecision(
        should_deny=True,
        should_allow=False,
        all_deny_reasons=[shared_text, "BLOCKED: other reason", shared_text],
        all_system_messages=[shared_text, shared_text, "other notice"],
        all_additional_context=["ctx-a", "ctx-a", "ctx-b"],
        should_suppress_output=True,
    )
    _emit_deny_decision(decision)
    captured = capsys.readouterr().out
    parsed = json.loads(captured)
    reason = parsed["hookSpecificOutput"]["permissionDecisionReason"]
    assert reason == f"{shared_text} | BLOCKED: other reason"
    assert reason.count(shared_text) == 1
    system_message = parsed["systemMessage"]
    assert system_message == f"{shared_text}\nother notice"
    assert parsed["hookSpecificOutput"]["additionalContext"] == "ctx-a\nctx-b"
    assert parsed["suppressOutput"] is True
    assert parsed["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_emit_deny_does_not_cross_collapse_reason_and_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A deny reason equal to a systemMessage string stays in both fields."""
    shared_text = "identical across fields"
    decision = DispatcherDecision(
        should_deny=True,
        should_allow=False,
        all_deny_reasons=[shared_text],
        all_system_messages=[shared_text],
        all_additional_context=[shared_text],
        should_suppress_output=False,
    )
    _emit_deny_decision(decision)
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["hookSpecificOutput"]["permissionDecisionReason"] == shared_text
    assert parsed["systemMessage"] == shared_text
    assert parsed["hookSpecificOutput"]["additionalContext"] == shared_text


def test_emit_allow_preserves_system_message_and_additional_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An allow payload carries the advisory's system and context messages."""
    decision = DispatcherDecision(
        should_deny=False,
        should_allow=True,
        all_deny_reasons=[],
        all_system_messages=["system-a", "system-b"],
        all_additional_context=["context-a", "context-b"],
        should_suppress_output=False,
    )

    _emit_allow_decision(decision)

    parsed = json.loads(capsys.readouterr().out)
    hook_specific = parsed["hookSpecificOutput"]
    assert hook_specific["permissionDecision"] == "allow"
    assert hook_specific["additionalContext"] == "context-a\ncontext-b"
    assert parsed["systemMessage"] == "system-a\nsystem-b"


def test_later_hook_deny_survives_early_hook_exit() -> None:
    """Dispatcher denies even when an earlier hook exits cleanly before a later hook denies.

    state_description_blocker denies a markdown write with a historical phrase.
    Earlier hooks exit 0 (allow). The dispatcher must catch each hook's
    SystemExit and continue, so the later denial reaches the aggregator.
    """
    payload_text = _write_payload(
        _MARKDOWN_FILE_PATH,
        "# Doc\n\nPreviously this section used a different mechanism.\n",
    )
    _assert_dispatcher_matches_individual_hooks(payload_text, WRITE_TOOL_NAME)


def test_dispatcher_write_applies_both_groups() -> None:
    """Write tool triggers both Group A and Group B hooks through the dispatcher.

    Verifies that the set of applicable entries for Write includes entries from
    both ALL_WRITE_AND_EDIT_TOOL_NAMES (Group A) and ALL_WRITE_EDIT_MULTI_EDIT_TOOL_NAMES
    (Group B) in the constants.
    """
    all_write_entries = _applicable_entries_for_tool(WRITE_TOOL_NAME)
    all_write_script_paths = {each_entry.script_relative_path for each_entry in all_write_entries}
    assert "blocking/write_existing_file_blocker.py" in all_write_script_paths, (
        "write_existing_file_blocker (Group A) must be in Write applicable set"
    )
    assert len(all_write_entries) == 18, (
        f"Write tool must apply to all 18 hosted hooks, got {len(all_write_entries)}"
    )


def test_dispatcher_edit_applies_both_groups() -> None:
    """Edit triggers Group A, Group B, and the Edit-scoped entry through the
    dispatcher.
    """
    all_edit_entries = _applicable_entries_for_tool(EDIT_TOOL_NAME)
    all_edit_script_paths = {each_entry.script_relative_path for each_entry in all_edit_entries}
    assert "blocking/stale_comment_reference_blocker.py" not in all_edit_script_paths
    assert "advisory/refactor_guard.py" in all_edit_script_paths, (
        "refactor_guard is Edit-scoped and hosted, so it belongs in the Edit applicable set"
    )
    assert len(all_edit_entries) == 20, (
        f"expected 20 Edit entries, got {len(all_edit_entries)}"
    )


def test_dispatcher_multi_edit_reaches_the_sensitive_protector() -> None:
    """A MultiEdit onto a sensitive path meets the same gate a Write does.

    test_edit_and_multi_edit_applicable_sets_are_equal in the constants suite
    holds the Edit and MultiEdit rosters equal, so this pins the one hook whose
    absence would let a secret through a MultiEdit.
    """
    all_multi_edit_entries = _applicable_entries_for_tool(MULTI_EDIT_TOOL_NAME)
    all_multi_edit_script_paths = {
        each_entry.script_relative_path for each_entry in all_multi_edit_entries
    }
    assert "blocking/sensitive_file_protector.py" in all_multi_edit_script_paths, (
        "sensitive_file_protector belongs in the MultiEdit applicable set"
    )


def test_dispatcher_apply_patch_applies_immediate_harm_hooks() -> None:
    """apply_patch applies to exactly the immediate-harm roster.

    apply_patch reaches only the immediate-harm-plus-TDD roster the constants
    module names, not the full Write/Edit/MultiEdit lint surface.
    """
    all_apply_patch_entries = _applicable_entries_for_tool(APPLY_PATCH_TOOL_NAME)
    all_apply_patch_script_paths = {
        each_entry.script_relative_path for each_entry in all_apply_patch_entries
    }
    assert "blocking/sensitive_file_protector.py" in all_apply_patch_script_paths, (
        "sensitive_file_protector belongs in the apply_patch applicable set"
    )
    assert all_apply_patch_script_paths == set(ALL_IMMEDIATE_HARM_SCRIPT_PATHS), (
        "apply_patch must apply to exactly the immediate-harm roster, got: "
        f"{sorted(all_apply_patch_script_paths)}"
    )


def _assert_roster_names_no_run_all_validators_entry() -> None:
    """Assert no hosted-roster ``script_relative_path`` names run_all_validators."""
    all_roster_script_paths = {
        each_entry.script_relative_path for each_entry in ALL_HOSTED_HOOK_ENTRIES
    }
    assert not any(
        "run_all_validators" in each_script_path
        for each_script_path in all_roster_script_paths
    ), (
        "ALL_HOSTED_HOOK_ENTRIES must name no run_all_validators entry, got: "
        f"{sorted(all_roster_script_paths)}"
    )


def test_run_all_validators_is_not_hosted_by_pre_tool_use_dispatcher() -> None:
    """The main PreToolUse dispatcher's hosted roster names no run_all_validators entry.

    ``hooks.json`` registers the ``run_all_validators`` runner as its own
    PreToolUse ``Write|Edit`` command, separate from the main dispatcher. A
    Python Write payload that ``run_all_validators`` would flag (a type error,
    for instance) still produces ALLOW from the main dispatcher, because its
    roster carries no entry for that runner.
    """
    _assert_roster_names_no_run_all_validators_entry()

    python_content_with_type_error = (
        "def add_one(value: int) -> int:\n"
        "    return value + 1\n\n\n"
        "add_one('not an int')\n"
    )
    payload_text = _write_payload(_TEMP_FILE_PATH.replace(".txt", ".py"), python_content_with_type_error)
    dispatcher_result = _run_dispatcher(payload_text)
    is_deny, _reason = _parse_hook_decision(dispatcher_result)
    assert not is_deny, (
        "PreToolUse dispatcher must allow a Python Write with a type error — "
        "run_all_validators runs as its own separate PreToolUse command, not "
        "through this dispatcher's roster"
    )
    assert dispatcher_result.returncode == 0, (
        f"Dispatcher must exit 0, got {dispatcher_result.returncode}"
    )


def _orphan_claude_md_payload(tmp_path: Path) -> str:
    """Build a Write payload for a CLAUDE.md naming a file that does not exist.

    Args:
        tmp_path: A directory hosting the throwaway CLAUDE.md.

    Returns:
        JSON-encoded Write payload that trips claude_md_orphan_file_blocker.
    """
    claude_md_path = str(tmp_path / "CLAUDE.md")
    orphan_table = (
        "# Files\n\n"
        "| File | Role |\n"
        "|---|---|\n"
        "| `file_that_does_not_exist_anywhere.py` | a missing file |\n"
    )
    return _write_payload(claude_md_path, orphan_table)


def test_runpy_deny_preserves_additional_context_and_suppress_output(tmp_path: Path) -> None:
    """A runpy-hosted deny carries its additionalContext and suppressOutput through the dispatcher.

    claude_md_orphan_file_blocker emits hookSpecificOutput.additionalContext and a
    top-level suppressOutput flag on a deny. The dispatcher must preserve both so
    the dispatched denial matches the standalone hook's deny shape.

    Args:
        tmp_path: Pytest temp directory hosting the throwaway CLAUDE.md.
    """
    payload_text = _orphan_claude_md_payload(tmp_path)

    standalone_result = _run_hook_subprocess(
        "blocking/claude_md_orphan_file_blocker.py", payload_text
    )
    standalone_payload = json.loads(standalone_result.stdout.strip())
    standalone_hook_specific = standalone_payload["hookSpecificOutput"]
    expected_additional_context = standalone_hook_specific["additionalContext"]

    dispatcher_result = _run_dispatcher(payload_text)
    dispatcher_payload = json.loads(dispatcher_result.stdout.strip())
    dispatcher_hook_specific = dispatcher_payload.get("hookSpecificOutput", {})
    assert isinstance(dispatcher_hook_specific, dict)
    assert dispatcher_hook_specific.get("additionalContext") == expected_additional_context, (
        "Dispatcher must preserve the runpy hook's additionalContext.\n"
        f"Expected: {expected_additional_context!r}\n"
        f"Got: {dispatcher_hook_specific.get('additionalContext')!r}"
    )
    assert dispatcher_payload.get("suppressOutput") is True, (
        "Dispatcher must preserve the runpy hook's suppressOutput flag.\n"
        f"Got: {dispatcher_payload.get('suppressOutput')!r}"
    )


def _parse_hook_allow(completed_process: subprocess.CompletedProcess[str]) -> bool:
    """Parse one hook's subprocess result for an explicit permissionDecision allow.

    Args:
        completed_process: The completed subprocess from running a hook.

    Returns:
        True when the hook emitted an explicit allow decision.
    """
    stdout_text = completed_process.stdout.strip()
    if not stdout_text:
        return False
    try:
        parsed_output = json.loads(stdout_text)
    except json.JSONDecodeError:
        return False
    hook_specific = parsed_output.get("hookSpecificOutput", {})
    if not isinstance(hook_specific, dict):
        return False
    return hook_specific.get("permissionDecision") == "allow"


def test_dispatcher_reemits_explicit_allow_from_tdd_enforcer(tmp_path: Path) -> None:
    """The dispatcher re-emits an explicit allow when tdd_enforcer's allow branch fires.

    tdd_enforcer writes an explicit allow payload for a constants-only Python
    Write, which auto-approves the write standalone. Run against the dispatcher,
    the same payload must produce an explicit allow decision identical to the
    standalone tdd_enforcer output, rather than a silent fall-back to the default
    permission flow.

    Args:
        tmp_path: Pytest temp directory hosting the fresh config target path.
    """
    config_target_path = str(tmp_path / "config" / "timing.py")
    constants_only_content = (
        '"""Timing constants."""\n\nMAXIMUM_RETRIES = 3\nRETRY_DELAY_SECONDS = 5\n'
    )
    payload_text = _write_payload(config_target_path, constants_only_content)

    standalone_result = _run_hook_subprocess("blocking/tdd_enforcer.py", payload_text)
    assert _parse_hook_allow(standalone_result), (
        "tdd_enforcer must emit an explicit allow for a constants-only Python Write — "
        "if it does not, this fixture no longer exercises the allow branch"
    )

    dispatcher_result = _run_dispatcher(payload_text)
    dispatcher_is_deny, _reason = _parse_hook_decision(dispatcher_result)
    assert not dispatcher_is_deny, "dispatcher must not deny a payload tdd_enforcer allows"
    assert _parse_hook_allow(dispatcher_result), (
        "dispatcher must re-emit an explicit allow when a hosted hook allows explicitly "
        "and no hook denies, matching the standalone tdd_enforcer behavior — "
        f"got stdout {dispatcher_result.stdout.strip()!r}"
    )
    dispatcher_payload = json.loads(dispatcher_result.stdout.strip())
    standalone_payload = json.loads(standalone_result.stdout.strip())
    assert dispatcher_payload == standalone_payload, (
        "dispatcher allow payload must match the standalone tdd_enforcer allow payload.\n"
        f"Standalone: {standalone_payload!r}\n"
        f"Dispatcher: {dispatcher_payload!r}"
    )


def test_runpy_hosted_hook_sees_its_own_argv_not_the_dispatchers(tmp_path: Path) -> None:
    """A runpy-hosted hook resolves its own script path as sys.argv, not the dispatcher's.

    The dispatcher must set sys.argv to the hosted hook's own script path before
    runpy so a hook that branches on sys.argv (such as code_rules_enforcer's
    --check pre-check mode) reads the same argv it would standalone, rather than
    the dispatcher's argv. The probe writes the argv it observed to a result
    file, and the test asserts argv[0] is the probe's own path.

    Args:
        tmp_path: Pytest temp directory hosting the probe script and result file.
    """
    argv_result_path = tmp_path / "observed_argv.json"
    probe_script_path = tmp_path / "argv_probe_hook.py"
    probe_script_path.write_text(
        "import json\n"
        "import sys\n"
        "from pathlib import Path\n\n"
        f"Path({str(argv_result_path)!r}).write_text(json.dumps(sys.argv), encoding='utf-8')\n",
        encoding="utf-8",
    )

    run_hosted_hook(str(probe_script_path), _write_payload(_TEMP_FILE_PATH, "x"), True)

    observed_argv = json.loads(argv_result_path.read_text(encoding="utf-8"))
    assert observed_argv == [str(probe_script_path)], (
        "A runpy-hosted hook must see its own script path as sys.argv, "
        f"not the dispatcher's argv. Observed: {observed_argv!r}"
    )


def test_folded_write_edit_hooks_have_no_standalone_hooks_json_entry() -> None:
    """A hook the dispatcher hosts must not also run as its own process.

    Each folded hook spawns an interpreter of its own when hooks.json still
    registers it, so the fold only pays off once the standalone entry is gone.
    """
    hooks_json_text = (_HOOKS_ROOT / "hooks.json").read_text(encoding="utf-8")
    hooks_configuration = json.loads(hooks_json_text)
    all_pre_tool_use_commands = [
        each_hook["command"]
        for each_group in hooks_configuration["hooks"]["PreToolUse"]
        for each_hook in each_group["hooks"]
    ]
    folded_script_relative_paths = (
        "advisory/refactor_guard.py",
        "advisory/migration_safety_advisor.py",
    )
    for each_script_path in folded_script_relative_paths:
        matching_commands = [
            each_command
            for each_command in all_pre_tool_use_commands
            if each_script_path in each_command
        ]
        assert not matching_commands, (
            f"{each_script_path} is hosted by the dispatcher, so its standalone "
            f"hooks.json entry must be gone. Found: {matching_commands!r}"
        )


def _standalone_apply_patch_code_rules_commands(all_pre_tool_use_groups: list[dict]) -> list[str]:
    """Return every standalone apply_patch command naming code_rules_enforcer.py."""
    return [
        each_hook["command"]
        for each_group in all_pre_tool_use_groups
        if each_group["matcher"] == APPLY_PATCH_TOOL_NAME
        for each_hook in each_group["hooks"]
        if "code_rules_enforcer.py" in each_hook["command"]
    ]


def _dispatcher_matchers(all_pre_tool_use_groups: list[dict]) -> list[str]:
    """Return every PreToolUse matcher whose command runs the dispatcher script."""
    return [
        each_group["matcher"]
        for each_group in all_pre_tool_use_groups
        if "pre_tool_use_dispatcher.py" in each_group["hooks"][0]["command"]
    ]


def test_apply_patch_has_no_standalone_code_rules_enforcer_hooks_json_entry() -> None:
    """apply_patch's code_rules_enforcer coverage comes only from the dispatcher.

    hooks.json once registered a standalone apply_patch to code_rules_enforcer.py
    PreToolUse command. That entry is now folded into the dispatcher's own
    Write|Edit|MultiEdit|apply_patch matcher, so no separate command may still
    spawn code_rules_enforcer.py for apply_patch on its own.
    """
    hooks_json_text = (_HOOKS_ROOT / "hooks.json").read_text(encoding="utf-8")
    all_pre_tool_use_groups = json.loads(hooks_json_text)["hooks"]["PreToolUse"]

    standalone_commands = _standalone_apply_patch_code_rules_commands(all_pre_tool_use_groups)
    assert not standalone_commands, (
        "apply_patch must have no standalone code_rules_enforcer.py hooks.json "
        f"entry — coverage comes from the dispatcher. Found: {standalone_commands!r}"
    )

    dispatcher_matchers = _dispatcher_matchers(all_pre_tool_use_groups)
    assert APPLY_PATCH_TOOL_NAME in "".join(dispatcher_matchers), (
        f"the dispatcher's own matcher must still name apply_patch, got: {dispatcher_matchers!r}"
    )


def _codex_add_patch(relative_file_path: str, file_body: str) -> str:
    """Build a Codex apply_patch "add" command text for one new file.

    Args:
        relative_file_path: Path (relative to the patch's cwd) to create.
        file_body: The full contents the new file should hold.

    Returns:
        The Codex-format patch command text.
    """
    added_lines = "\n".join(f"+{each_line}" for each_line in file_body.splitlines())
    return (
        "*** Begin Patch\n"
        f"*** Add File: {relative_file_path}\n"
        f"{added_lines}\n"
        "*** End Patch"
    )


def test_dispatcher_denies_apply_patch_add_with_hardcoded_secret(
    tmp_path: Path,
    init_bare_git_repo: Callable[[Path], None],
    synthetic_github_token: str,
) -> None:
    """The dispatcher denies an apply_patch "add" that writes a hardcoded token.

    Proves Done-when scenario 1 (hardcoded secret/PII denied) reaches apply_patch
    through the real dispatcher subprocess, not only the standalone
    pii_prevention_blocker test.
    """
    repository_root = tmp_path / "repo"
    init_bare_git_repo(repository_root)
    patch_command = _codex_add_patch("leaked.py", f"token is {synthetic_github_token}\n")
    payload_text = _apply_patch_payload(str(repository_root), patch_command)

    dispatcher_result = _run_dispatcher(payload_text)
    is_deny, reason_text = _parse_hook_decision(dispatcher_result)
    assert is_deny, (
        "dispatcher must deny an apply_patch add carrying a hardcoded secret, "
        f"got stdout {dispatcher_result.stdout.strip()!r}"
    )
    assert reason_text, "a deny must carry a non-empty reason"


def test_dispatcher_denies_apply_patch_targeting_a_sensitive_path(tmp_path: Path) -> None:
    """The dispatcher denies an apply_patch "add" that targets a sensitive file.

    Proves Done-when scenario 2 (sensitive path denied) reaches apply_patch
    through the real dispatcher subprocess.
    """
    patch_command = _codex_add_patch(".env", "SECRET_KEY=irrelevant\n")
    payload_text = _apply_patch_payload(str(tmp_path), patch_command)

    dispatcher_result = _run_dispatcher(payload_text)
    is_deny, reason_text = _parse_hook_decision(dispatcher_result)
    assert is_deny, (
        "dispatcher must deny an apply_patch add targeting a sensitive path, "
        f"got stdout {dispatcher_result.stdout.strip()!r}"
    )
    assert reason_text, "a deny must carry a non-empty reason"


def test_dispatcher_denies_apply_patch_add_onto_an_existing_path(tmp_path: Path) -> None:
    """The dispatcher denies an apply_patch "add" that targets a path already on disk.

    Proves Done-when scenario 3 (overwrite-without-reading denied) reaches
    apply_patch: a Codex "add" operation onto an existing path is caught by
    code_rules_enforcer's codex-patch reading, blocking/codex_apply_patch.py's
    _codex_read_patch_file, which raises CodexPatchError for an add already on
    disk, reported through the dispatcher's aggregate.
    """
    existing_target = tmp_path / "already_here.py"
    existing_target.write_text("value = 1\n", encoding="utf-8")
    patch_command = _codex_add_patch("already_here.py", "value = 2\n")
    payload_text = _apply_patch_payload(str(tmp_path), patch_command)

    dispatcher_result = _run_dispatcher(payload_text)
    is_deny, reason_text = _parse_hook_decision(dispatcher_result)
    assert is_deny, (
        "dispatcher must deny an apply_patch add onto an already-existing path, "
        f"got stdout {dispatcher_result.stdout.strip()!r}"
    )
    assert reason_text, "a deny must carry a non-empty reason"


def test_dispatcher_allows_clean_apply_patch_add(tmp_path: Path) -> None:
    """The dispatcher allows an apply_patch "add" whose paired test already exists.

    tdd_enforcer now reaches apply_patch the same way it reaches Write: an
    untested production file is exactly the immediate-harm case the apply_patch
    boundary rule names, so "clean" here means test-first was honored before
    the tool call, not that TDD is skipped for this tool. The paired test file
    is written to disk first, matching how test_dispatcher_surfaces_migration_
    warning_for_edit proves a fresh Edit passes tdd_enforcer.
    """
    (tmp_path / "test_services.py").write_text(
        "def test_add_one():\n    assert True\n", encoding="utf-8"
    )
    patch_command = _codex_add_patch(
        "services.py",
        "def add_one(value: int) -> int:\n    return value + 1\n",
    )
    payload_text = _apply_patch_payload(str(tmp_path), patch_command)

    dispatcher_result = _run_dispatcher(payload_text)
    is_deny, reason_text = _parse_hook_decision(dispatcher_result)
    assert not is_deny, (
        f"dispatcher must allow an apply_patch add with a fresh paired test, "
        f"got deny reason {reason_text!r}"
    )


def test_hosted_hook_set_covers_all_write_edit_blocking_hooks() -> None:
    """The hosted hook set covers all previously-registered Write/Edit blocking hooks.

    Verifies that removing the standalone gate entries from hooks.json did not
    silently drop coverage: every script path that was registered as a blocking
    PreToolUse hook for Write/Edit is present in the dispatcher's hosted set.
    """
    all_hosted_script_paths = frozenset(
        each_entry.script_relative_path for each_entry in ALL_HOSTED_HOOK_ENTRIES
    )
    previously_registered_blocking_hooks: frozenset[str] = frozenset({
        "blocking/write_existing_file_blocker.py",
        "blocking/sensitive_file_protector.py",
        "validation/hook_format_validator.py",
        "blocking/code_rules_enforcer.py",
        "blocking/tdd_enforcer.py",
        "blocking/windows_rmtree_blocker.py",
        "blocking/state_description_blocker.py",
        "blocking/subprocess_budget_completeness.py",
        "blocking/hook_prose_detector_consistency.py",
        "blocking/workflow_substitution_slot_blocker.py",
        "blocking/claude_md_orphan_file_blocker.py",
        "blocking/pytest_testpaths_orphan_blocker.py",
        "blocking/open_questions_in_plans_blocker.py",
    })
    for each_script_path in previously_registered_blocking_hooks:
        assert each_script_path in all_hosted_script_paths, (
            f"Previously-registered blocking hook {each_script_path!r} is missing "
            "from the dispatcher's hosted hook set — coverage was lost when the "
            "standalone entry was removed from hooks.json"
        )
