"""Subprocess integration tests for content-search-to-zoekt-redirector PreToolUse hook."""

import json
import pathlib
import subprocess
import sys
import unittest
from typing import Any


class ContentSearchHookIntegrationTests(unittest.TestCase):
    def test_bash_grep_command_emits_stdout_json_deny(self) -> None:
        hook_directory = pathlib.Path(__file__).resolve().parent
        if str(hook_directory) not in sys.path:
            sys.path.insert(0, str(hook_directory))
        from content_search_zoekt_redirect_guidance import (
            get_zoekt_redirect_guidance,
            get_zoekt_redirect_reason_brief,
        )

        hook_path = hook_directory / "content_search_to_zoekt_redirector.py"
        destructive_gate_label_prefix = "[destructive-gate]"
        destructive_gate_label_prefix_value = f"{destructive_gate_label_prefix} "
        expected_decision = "deny"
        hook_stdin_payload = json.dumps(
            {"tool_name": "Bash", "tool_input": {"command": "grep foo bar"}},
        )

        completed = subprocess.run(
            [sys.executable, str(hook_path)],
            input=hook_stdin_payload,
            capture_output=True,
            text=True,
            cwd=str(hook_directory),
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(completed.stderr, "")
        payload: dict[str, Any] = json.loads(completed.stdout)
        self.assertTrue(
            payload["systemMessage"].startswith(destructive_gate_label_prefix_value),
        )
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecisionReason"],
            get_zoekt_redirect_reason_brief(),
        )
        self.assertEqual(
            payload["hookSpecificOutput"]["additionalContext"],
            get_zoekt_redirect_guidance(),
        )
        self.assertEqual(
            payload["hookSpecificOutput"]["permissionDecision"],
            expected_decision,
        )
        self.assertEqual(
            payload["hookSpecificOutput"]["hookEventName"],
            "PreToolUse",
        )


if __name__ == "__main__":
    unittest.main()
