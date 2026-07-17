"""Behavioral tests for the verified-commit gate's deny-payload shape."""

from verified_commit_gate_parts.deny_payload import build_deny_payload


def test_build_deny_payload_carries_the_deny_decision_and_reason() -> None:
    deny_payload = build_deny_payload("BLOCKED: needs a verdict")
    hook_specific_output = deny_payload["hookSpecificOutput"]
    assert hook_specific_output["hookEventName"] == "PreToolUse"
    assert hook_specific_output["permissionDecision"] == "deny"
    assert hook_specific_output["permissionDecisionReason"] == "BLOCKED: needs a verdict"


def test_build_deny_payload_carries_the_verify_skip_additional_context() -> None:
    deny_payload = build_deny_payload("BLOCKED: needs a verdict")
    additional_context = deny_payload["hookSpecificOutput"]["additionalContext"]
    assert "# verify-skip" in additional_context
