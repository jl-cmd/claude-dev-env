"""Unit tests for Zoekt redirector PreToolUse deny payload (build_block_payload)."""

import json
import pathlib
import sys
import unittest
from typing import Any

HOOK_DIRECTORY = pathlib.Path(__file__).resolve().parent
if str(HOOK_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(HOOK_DIRECTORY))

from content_search_zoekt_block_payload import build_block_payload
from content_search_zoekt_redirect_guidance import get_zoekt_redirect_guidance


class BuildBlockPayloadTests(unittest.TestCase):
    def test_payload_matches_pretooluse_contract(self) -> None:
        destructive_gate_label_prefix = "[destructive-gate]"
        payload: dict[str, Any] = build_block_payload("demo", "body")
        prefix_with_space = f"{destructive_gate_label_prefix} "
        self.assertTrue(payload["systemMessage"].startswith(prefix_with_space))
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecisionReason"],
            "body",
        )
        self.assertEqual(payload["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(
            payload["hookSpecificOutput"]["hookEventName"],
            "PreToolUse",
        )
        self.assertEqual(payload["suppressOutput"], True)
        self.assertNotIn("decision", payload)
        self.assertNotIn("reason", payload)

    def test_serialized_payload_under_documented_context_cap(self) -> None:
        cap_characters = 10_000
        payload = build_block_payload(
            brief_label="blocked Bash(grep); use Zoekt MCP",
            permission_decision_reason=get_zoekt_redirect_guidance(),
        )
        serialized = json.dumps(payload)
        self.assertLessEqual(
            len(serialized),
            cap_characters,
            msg="Hooks doc caps additionalContext/systemMessage/plain stdout injection at 10,000 characters",
        )


if __name__ == "__main__":
    unittest.main()
