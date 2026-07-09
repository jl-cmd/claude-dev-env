"""Golden-differential and unit tests for the Bash/PowerShell PreToolUse dispatcher.

The golden-differential tests run a payload through every applicable hook as its
own subprocess (the standalone path), compute the precedence decision the chain
produced, then run the dispatcher on the same payload and assert an equal
decision. The unit tests pin the deny>ask>allow precedence, the es_exe
updatedInput passthrough, and the fail-open posture on a crashed hook.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = str(Path(__file__).resolve().parent.parent)
_BLOCKING_DIR = Path(__file__).resolve().parent
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
_blocking_dir_text = str(_BLOCKING_DIR)
if _blocking_dir_text not in sys.path:
    sys.path.insert(0, _blocking_dir_text)

from bash_pre_tool_use_dispatcher import (  # noqa: E402
    BashDispatcherDecision,
    _emit_decision,
    aggregate_bash_hook_results,
    dispatch,
    select_applicable_entries,
)
from hooks_constants.bash_pre_tool_use_dispatcher_constants import (  # noqa: E402
    BASH_TOOL_NAME,
    POWERSHELL_TOOL_NAME,
)
from hooks_constants.hosted_hook_runner import HostedHookRun  # noqa: E402

_HOOKS_ROOT = _BLOCKING_DIR.parent
_DISPATCHER_SCRIPT = str(_BLOCKING_DIR / "bash_pre_tool_use_dispatcher.py")


def _bash_payload(command: str) -> str:
    """Build a Bash tool payload JSON string carrying command."""
    return json.dumps({"tool_name": BASH_TOOL_NAME, "tool_input": {"command": command}})


def _decision_from_stdout(stdout_text: str) -> tuple[str, str]:
    """Parse a hook or dispatcher stdout into (permissionDecision, reason)."""
    stripped = stdout_text.strip()
    if not stripped:
        return "", ""
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        return "", ""
    hook_specific = parsed.get("hookSpecificOutput", {})
    if not isinstance(hook_specific, dict):
        return "", ""
    decision = hook_specific.get("permissionDecision", "")
    reason = hook_specific.get("permissionDecisionReason", "")
    decision_text = decision if isinstance(decision, str) else ""
    return decision_text, (reason if isinstance(reason, str) else "")


def _run_process(script_or_hook_path: str, payload_text: str) -> subprocess.CompletedProcess[str]:
    """Run a hook or the dispatcher as a subprocess with the current environment."""
    return subprocess.run(
        [sys.executable, script_or_hook_path],
        check=False,
        input=payload_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _expected_precedence(payload_text: str, tool_name: str) -> str:
    """Return the decision the standalone chain yields for payload by precedence."""
    all_decisions = []
    for each_entry in select_applicable_entries(tool_name):
        hook_path = str(_HOOKS_ROOT / each_entry.script_relative_path)
        decision, _reason = _decision_from_stdout(_run_process(hook_path, payload_text).stdout)
        all_decisions.append(decision)
    for each_winning in ("deny", "ask", "allow"):
        if each_winning in all_decisions:
            return each_winning
    return ""


def test_clean_command_yields_no_decision_matching_the_standalone_chain() -> None:
    """A benign command produces no decision from the chain and from the dispatcher."""
    payload_text = _bash_payload("echo hello world")
    expected_decision = _expected_precedence(payload_text, BASH_TOOL_NAME)
    dispatcher_decision, _reason = _decision_from_stdout(
        _run_process(_DISPATCHER_SCRIPT, payload_text).stdout
    )
    assert dispatcher_decision == expected_decision


def test_destructive_command_asks_matching_the_standalone_chain() -> None:
    """A destructive command the chain asks on makes the dispatcher ask too."""
    payload_text = _bash_payload("rm -rf /")
    expected_decision = _expected_precedence(payload_text, BASH_TOOL_NAME)
    dispatcher_decision, _reason = _decision_from_stdout(
        _run_process(_DISPATCHER_SCRIPT, payload_text).stdout
    )
    assert dispatcher_decision == expected_decision
    assert expected_decision == "ask"


def test_dispatcher_exits_zero_on_a_clean_command() -> None:
    """The dispatcher exits zero for a command no hook decides on."""
    completed = _run_process(_DISPATCHER_SCRIPT, _bash_payload("echo hi"))
    assert completed.returncode == 0


def _run(stdout: str) -> HostedHookRun:
    """Build a HostedHookRun carrying stdout with no crash."""
    return HostedHookRun(captured_stdout=stdout, did_crash=False)


def _decision_json(decision: str, reason: str) -> str:
    """Build a hook stdout string carrying one permission decision."""
    return json.dumps(
        {"hookSpecificOutput": {"permissionDecision": decision, "permissionDecisionReason": reason}}
    )


def test_deny_wins_over_ask_and_allow() -> None:
    """A deny from any hook overrides an ask and an allow from others."""
    all_runs = [
        _run(_decision_json("allow", "")),
        _run(_decision_json("ask", "please confirm")),
        _run(_decision_json("deny", "blocked hard")),
    ]
    aggregated = aggregate_bash_hook_results(all_runs)
    assert aggregated.decision == "deny"
    assert "blocked hard" in aggregated.reasons


def test_ask_wins_over_allow() -> None:
    """An ask overrides an allow when no hook denies."""
    all_runs = [_run(_decision_json("allow", "")), _run(_decision_json("ask", "confirm this"))]
    aggregated = aggregate_bash_hook_results(all_runs)
    assert aggregated.decision == "ask"
    assert "confirm this" in aggregated.reasons


def test_allow_with_updated_input_is_carried_through() -> None:
    """An allow carrying updatedInput surfaces that rewrite when no hook denies or asks."""
    rewritten = json.dumps(
        {
            "hookSpecificOutput": {
                "permissionDecision": "allow",
                "updatedInput": {"command": "es.exe rewritten"},
            }
        }
    )
    aggregated = aggregate_bash_hook_results([_run(rewritten)])
    assert aggregated.decision == "allow"
    assert aggregated.updated_input == {"command": "es.exe rewritten"}


def test_no_decision_when_every_hook_is_silent() -> None:
    """A chain where every hook emits nothing produces no dispatcher decision."""
    aggregated = aggregate_bash_hook_results([_run(""), _run("")])
    assert aggregated.decision == ""


def test_a_crashed_hook_contributes_no_decision() -> None:
    """A crashed hook fails open: its empty output adds no deny, ask, or allow."""
    crashed_run = HostedHookRun(captured_stdout="", did_crash=True)
    aggregated = aggregate_bash_hook_results([crashed_run])
    assert aggregated.decision == ""
    assert isinstance(aggregated, BashDispatcherDecision)


def test_deny_preserves_system_message_and_suppress_output() -> None:
    """A silent-deny shape carries systemMessage and suppressOutput through aggregation."""
    silent_deny = json.dumps(
        {
            "hookSpecificOutput": {
                "permissionDecision": "deny",
                "permissionDecisionReason": "GH-REDIRECT GATE: duplicate blocked",
            },
            "suppressOutput": True,
            "systemMessage": "[gh-gate] blocked redirected gh pr create",
        }
    )
    aggregated = aggregate_bash_hook_results([_run(silent_deny)])
    assert aggregated.decision == "deny"
    assert aggregated.should_suppress_output is True
    assert aggregated.all_system_messages == ["[gh-gate] blocked redirected gh pr create"]
    assert "GH-REDIRECT GATE" in aggregated.reasons[0]


def test_additional_context_is_collected_from_deciding_hooks() -> None:
    """additionalContext from hosted hooks is retained for the emitted payload."""
    deny_with_context = json.dumps(
        {
            "hookSpecificOutput": {
                "permissionDecision": "deny",
                "permissionDecisionReason": "blocked",
                "additionalContext": "see docs/runbook.md",
            }
        }
    )
    aggregated = aggregate_bash_hook_results([_run(deny_with_context)])
    assert aggregated.all_additional_context == ["see docs/runbook.md"]


def test_powershell_selects_only_the_verified_commit_pair() -> None:
    """Selecting for PowerShell yields the two shared hooks in registration order."""
    powershell_paths = [
        each_entry.script_relative_path
        for each_entry in select_applicable_entries(POWERSHELL_TOOL_NAME)
    ]
    assert powershell_paths == [
        "blocking/verified_commit_gate.py",
        "blocking/verdict_directory_write_blocker.py",
    ]


def test_dispatcher_imports_standalone_with_only_blocking_on_the_path() -> None:
    """The dispatcher's bootstrap resolves hooks_constants without hooks/ on PYTHONPATH."""
    subprocess_environment = {**os.environ, "PYTHONPATH": str(_BLOCKING_DIR)}
    completed = subprocess.run(
        [sys.executable, "-c", "import bash_pre_tool_use_dispatcher; print('ok')"],
        check=False,
        capture_output=True,
        text=True,
        env=subprocess_environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"


def test_emit_decision_re_emits_silent_deny_fields(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """_emit_decision writes systemMessage, suppressOutput, and additionalContext."""
    silent_deny = BashDispatcherDecision(
        decision="deny",
        reasons=["GH-REDIRECT GATE: duplicate blocked"],
        all_system_messages=["[gh-gate] blocked redirected gh pr create"],
        all_additional_context=["see docs/runbook.md"],
        should_suppress_output=True,
    )
    _emit_decision(silent_deny)
    captured = capsys.readouterr()
    emitted_payload = json.loads(captured.out.strip())
    hook_specific = emitted_payload["hookSpecificOutput"]
    assert hook_specific["permissionDecision"] == "deny"
    assert "GH-REDIRECT GATE" in hook_specific["permissionDecisionReason"]
    assert hook_specific["additionalContext"] == "see docs/runbook.md"
    assert emitted_payload["systemMessage"] == "[gh-gate] blocked redirected gh pr create"
    assert emitted_payload["suppressOutput"] is True


def test_dispatch_emits_deny_immediately_and_skips_later_hooks(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A mid-chain deny emits at once and does not invoke later hosted hooks."""
    all_call_paths: list[str] = []

    def _fake_run_hook(script_path: str, payload_text: str) -> HostedHookRun:
        del payload_text
        all_call_paths.append(script_path)
        script_name = Path(script_path).name
        if script_name == "destructive_command_blocker.py":
            return HostedHookRun(
                captured_stdout=_decision_json("deny", "blocked early"),
                did_crash=False,
            )
        if script_name == "precommit_code_rules_gate.py":
            raise AssertionError("later hooks must not run after an early deny")
        return HostedHookRun(captured_stdout="", did_crash=False)

    monkeypatch.setattr(
        "bash_pre_tool_use_dispatcher.run_hook_capturing_output",
        _fake_run_hook,
    )
    dispatch(_bash_payload("rm -rf /"), BASH_TOOL_NAME)
    captured = capsys.readouterr()
    decision, reason = _decision_from_stdout(captured.out)
    assert decision == "deny"
    assert "blocked early" in reason
    assert any(path.endswith("destructive_command_blocker.py") for path in all_call_paths)
    assert not any(path.endswith("precommit_code_rules_gate.py") for path in all_call_paths)
