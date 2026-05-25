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
from content_search_zoekt_redirect_guidance import (
    get_zoekt_redirect_guidance,
    get_zoekt_redirect_reason_brief,
    worktree_path_display_fragment,
    worktree_path_filter_fragment,
)


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
        self.assertNotIn("additionalContext", payload["hookSpecificOutput"])

    def test_serialized_payload_under_documented_context_cap(self) -> None:
        cap_characters = 10_000
        payload = build_block_payload(
            brief_label="blocked Bash(grep); use Zoekt MCP",
            permission_decision_reason=get_zoekt_redirect_reason_brief(),
            additional_context=get_zoekt_redirect_guidance(),
        )
        serialized = json.dumps(payload)
        self.assertLessEqual(
            len(serialized),
            cap_characters,
            msg="Hooks doc caps additionalContext/systemMessage/plain stdout injection at 10,000 characters",
        )


class RedirectGuidanceWorktreeTests(unittest.TestCase):
    def test_guidance_defaults_to_excluding_worktrees(self) -> None:
        guidance = get_zoekt_redirect_guidance()
        expected_default_exclusion = f"-file:{worktree_path_filter_fragment()}"
        self.assertIn(expected_default_exclusion, guidance)

    def test_guidance_explains_how_to_search_a_worktree(self) -> None:
        guidance = get_zoekt_redirect_guidance()
        positive_filter_example = (
            f'query="your pattern file:{worktree_path_filter_fragment()}<branch>/'
        )
        self.assertIn(positive_filter_example, guidance)
        self.assertIn("worktree", guidance.lower())

    def test_worktree_filter_fragment_is_a_regex_escaped_path(self) -> None:
        self.assertEqual(worktree_path_filter_fragment(), "\\.claude/worktrees/")

    def test_guidance_describes_worktree_path_unescaped_in_prose(self) -> None:
        guidance = get_zoekt_redirect_guidance()
        prose_substring = (
            f"git worktrees under {worktree_path_display_fragment()} that"
        )
        self.assertIn(prose_substring, guidance)

    def test_worktree_display_fragment_is_the_unescaped_path(self) -> None:
        self.assertEqual(worktree_path_display_fragment(), ".claude/worktrees/")

    def test_guidance_documents_index_freshness_escape_hatch(self) -> None:
        guidance = get_zoekt_redirect_guidance()
        self.assertIn("INDEX FRESHNESS:", guidance)
        self.assertIn("exempt from this redirect", guidance)
        self.assertIn("read the file directly", guidance)


if __name__ == "__main__":
    unittest.main()
