"""JSON shape for Claude Code PreToolUse deny: hookSpecificOutput plus short systemMessage."""


def build_block_payload(
    brief_label: str,
    permission_decision_reason: str,
) -> dict:
    destructive_gate_label_prefix = "[destructive-gate]"
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": permission_decision_reason,
        },
        "systemMessage": f"{destructive_gate_label_prefix} {brief_label}",
        "suppressOutput": True,
    }
