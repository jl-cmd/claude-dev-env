"""JSON shape for Claude Code PreToolUse deny: hookSpecificOutput plus short systemMessage."""


def build_block_payload(
    brief_label: str,
    permission_decision_reason: str,
    additional_context: str | None = None,
) -> dict:
    destructive_gate_label_prefix = "[destructive-gate]"
    hook_specific_output: dict = {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": permission_decision_reason,
    }
    if additional_context is not None:
        hook_specific_output["additionalContext"] = additional_context
    return {
        "hookSpecificOutput": hook_specific_output,
        "systemMessage": f"{destructive_gate_label_prefix} {brief_label}",
        "suppressOutput": True,
    }
