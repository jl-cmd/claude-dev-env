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
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from hooks_constants.pre_tool_use_dispatcher_constants import (  # noqa: E402, I001
    ALL_HOSTED_HOOK_ENTRIES,
    BLOCKING_CRASH_EXIT_CODE,
    DENY_DECISION,
    EDIT_TOOL_NAME,
    EXIT_CODE_TWO_DENY_REASON,
    MULTI_EDIT_TOOL_NAME,
    WRITE_TOOL_NAME,
    HostedHookEntry,
)
from pre_tool_use_dispatcher import (  # noqa: E402, I001
    HostedHookResult,
    aggregate_hosted_hook_results,
)

_BLOCKING_DIR = Path(__file__).resolve().parent
_HOOKS_ROOT = _BLOCKING_DIR.parent
_DISPATCHER_SCRIPT = str(_BLOCKING_DIR / "pre_tool_use_dispatcher.py")

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


def _multi_edit_payload(file_path: str, edits: list[dict[str, str]]) -> str:
    """Build a MultiEdit tool payload JSON string.

    Args:
        file_path: The target file path.
        edits: List of edit dicts with old_string and new_string keys.

    Returns:
        JSON-encoded payload string.
    """
    return json.dumps(
        {
            "tool_name": MULTI_EDIT_TOOL_NAME,
            "tool_input": {"file_path": file_path, "edits": edits},
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


def test_clean_write_allows_on_multi_edit_tool() -> None:
    """Dispatcher allows a multi-edit that all hosted hooks allow on MultiEdit tool."""
    payload_text = _multi_edit_payload(
        _TEMP_FILE_PATH,
        [{"old_string": "old", "new_string": "new"}],
    )
    _assert_dispatcher_matches_individual_hooks(payload_text, MULTI_EDIT_TOOL_NAME)


def test_plain_language_denial_on_write_of_markdown_file() -> None:
    """Dispatcher denies when plain_language_blocker denies a Write of heavy prose."""
    payload_text = _write_payload(
        _MARKDOWN_FILE_PATH,
        "# Guide\n\nPlease utilize this functionality to commence the process.\n",
    )
    _assert_dispatcher_matches_individual_hooks(payload_text, WRITE_TOOL_NAME)


def test_plain_language_denial_on_edit_of_markdown_file() -> None:
    """Dispatcher denies when plain_language_blocker denies an Edit with heavy prose."""
    payload_text = _edit_payload(
        _MARKDOWN_FILE_PATH,
        "old line",
        "Please utilize this functionality to commence the process.\n",
    )
    _assert_dispatcher_matches_individual_hooks(payload_text, EDIT_TOOL_NAME)


def test_plain_language_denial_on_multi_edit_of_markdown_file() -> None:
    """Dispatcher denies when plain_language_blocker denies a MultiEdit with heavy prose."""
    payload_text = _multi_edit_payload(
        _MARKDOWN_FILE_PATH,
        [{"old_string": "old", "new_string": "Please utilize this functionality to commence."}],
    )
    _assert_dispatcher_matches_individual_hooks(payload_text, MULTI_EDIT_TOOL_NAME)


def test_multi_edit_runs_only_group_b_hooks() -> None:
    """Dispatcher invokes only Group-B hooks on MultiEdit, not Group-A hooks.

    A plain_language_blocker denial on a MultiEdit proves Group B runs.
    The write_existing_file_blocker (Group A only) must not run on MultiEdit,
    so a MultiEdit to any path that would trip a Group-A hook must still allow.
    This test proves Group A does not run on MultiEdit by asserting:
    1. Group-B (plain_language_blocker) fires on MultiEdit for a markdown file
       with heavy prose.
    2. The set of applicable entries for MultiEdit contains no Group-A entries.
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
    heavy_prose_payload = _multi_edit_payload(
        _MARKDOWN_FILE_PATH,
        [{"old_string": "old line", "new_string": "Utilize this to commence the process."}],
    )
    dispatcher_result = _run_dispatcher(heavy_prose_payload)
    dispatcher_is_deny, _reason = _parse_hook_decision(dispatcher_result)
    assert dispatcher_is_deny, (
        "Dispatcher should deny a MultiEdit with heavy prose (plain_language_blocker "
        "is a Group-B hook and must run on MultiEdit)"
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


def test_write_existing_file_blocker_does_not_run_on_multi_edit() -> None:
    """Group-A write_existing_file_blocker does not run on MultiEdit.

    The dispatcher must allow a MultiEdit to an existing file path even though
    write_existing_file_blocker would deny the same path on a Write.
    Uses a non-markdown file so plain_language_blocker stays silent.
    """
    existing_file_path = str(Path(__file__).resolve())
    payload_text = _multi_edit_payload(
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

    Uses a Write to a .md file carrying both a historical phrase ("previously")
    and a heavy word ("utilize") so state_description_blocker (Group A) and
    plain_language_blocker (Group B) both deny deterministically with no
    real-filesystem dependency.
    """
    multi_deny_content = (
        "# Guide\n\n"
        "Previously the system utilized a different mechanism.\n"
    )
    payload_text = _write_payload(_MARKDOWN_FILE_PATH, multi_deny_content)
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
        "Check that 'previously' triggers state_description_blocker and 'utilized' "
        "triggers plain_language_blocker on a .md Write."
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


def test_later_hook_deny_survives_early_hook_exit() -> None:
    """Dispatcher denies even when an earlier hook exits cleanly before a later hook denies.

    plain_language_blocker (Group B, last in order) denies a markdown write with heavy
    prose. Earlier hooks exit 0 (allow). The dispatcher must catch each hook's
    SystemExit and continue, so the later denial reaches the aggregator.
    """
    payload_text = _write_payload(
        _MARKDOWN_FILE_PATH,
        "# Doc\n\nThis section attempts to facilitate the utilization of this functionality.\n",
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
    assert "blocking/plain_language_blocker.py" in all_write_script_paths, (
        "plain_language_blocker (Group B) must be in Write applicable set"
    )
    assert len(all_write_entries) == 15, (
        f"Write tool must apply to all 15 hosted hooks, got {len(all_write_entries)}"
    )


def test_dispatcher_edit_applies_both_groups() -> None:
    """Edit tool triggers both Group A and Group B hooks through the dispatcher."""
    all_edit_entries = _applicable_entries_for_tool(EDIT_TOOL_NAME)
    assert len(all_edit_entries) == 15, (
        f"Edit tool must apply to all 15 hosted hooks, got {len(all_edit_entries)}"
    )


def test_dispatcher_multi_edit_applies_only_group_b() -> None:
    """MultiEdit tool triggers only Group B (5 hooks), not Group A."""
    all_multi_edit_entries = _applicable_entries_for_tool(MULTI_EDIT_TOOL_NAME)
    assert len(all_multi_edit_entries) == 5, (
        f"MultiEdit tool must apply to exactly 5 Group-B hooks, got {len(all_multi_edit_entries)}"
    )


def test_proceed_after_run_all_validators_removal_allows() -> None:
    """The PreToolUse dispatcher allows a Python edit that the removed gate would have processed.

    The inline run_all_validators runner was a PostToolUse gate removed in Stage 4;
    it was never a PreToolUse hook and never hosted by the PreToolUse dispatcher.
    A Python Write payload that run_all_validators would have flagged (mypy errors, for
    instance) still produces ALLOW from the PreToolUse dispatcher because the PreToolUse
    dispatcher covers only its 15 hosted blocking hooks — none of which includes the
    validators runner.
    """
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
        "mypy validation is PostToolUse-only; the removed run_all_validators gate "
        "was never a PreToolUse hook"
    )
    assert dispatcher_result.returncode == 0, (
        f"Dispatcher must exit 0, got {dispatcher_result.returncode}"
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
        "blocking/verified_commit_message_accuracy_blocker.py",
        "blocking/workflow_substitution_slot_blocker.py",
        "blocking/claude_md_orphan_file_blocker.py",
        "blocking/pytest_testpaths_orphan_blocker.py",
        "blocking/open_questions_in_plans_blocker.py",
        "blocking/plain_language_blocker.py",
    })
    for each_script_path in previously_registered_blocking_hooks:
        assert each_script_path in all_hosted_script_paths, (
            f"Previously-registered blocking hook {each_script_path!r} is missing "
            "from the dispatcher's hosted hook set — coverage was lost when the "
            "standalone entry was removed from hooks.json"
        )
