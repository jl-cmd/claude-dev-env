"""Tests for working_style_prompt — SessionStart hook that injects working-style text."""

import json
import sys
from io import StringIO
from pathlib import Path
from unittest.mock import patch

_SESSION_DIR = Path(__file__).resolve().parent
_HOOKS_ROOT = _SESSION_DIR.parent
for each_sys_path_entry in (str(_SESSION_DIR), str(_HOOKS_ROOT)):
    if each_sys_path_entry not in sys.path:
        sys.path.insert(0, each_sys_path_entry)

import working_style_prompt as starter

from hooks_constants.working_style_prompt_constants import (
    WORKING_STYLE_PROMPT,
)


def _run_main() -> str:
    """Return stdout produced by running the hook's main()."""
    captured_stdout = StringIO()
    with patch("sys.stdout", captured_stdout):
        starter.main()
    return captured_stdout.getvalue()


class TestWorkingStylePrompt:
    def test_main_emits_additional_context(self) -> None:
        emitted = json.loads(_run_main())
        assert "additionalContext" in emitted

    def test_additional_context_matches_prompt_exactly(self) -> None:
        emitted = json.loads(_run_main())
        assert emitted["additionalContext"] == WORKING_STYLE_PROMPT

    def test_emitted_prompt_contains_canonical_policy_and_scope_guidance(self) -> None:
        emitted = json.loads(_run_main())
        prompt_text = emitted["additionalContext"]
        assert "Document each task in a location that remains easy to find later." in prompt_text
        assert "Deliver the requested work at its intended scope." in prompt_text
        assert "Use ELI5 for beginner framing, large visuals, minimal text" in prompt_text
        assert "one stable self-contained HTML artifact" in prompt_text
        assert "update-in-place continuity, and sharing" in prompt_text
        assert "Apply ~/.claude/rules/asd-ste100-language.md for user-facing word choice" in prompt_text
        assert "Use current, immediately relevant context." in prompt_text
        assert "Name each action, fact, reason, and outcome." in prompt_text
        assert "Use full terms and specific names for repository work." in prompt_text
        assert "When a request has multiple reasonable interpretations" in prompt_text
        assert "Ask one focused clarification question" in prompt_text
        assert "Pause for the user's choice before making a high-impact decision." in prompt_text

    def test_build_session_directive_returns_the_shared_constant(self) -> None:
        assert starter.build_session_directive() == WORKING_STYLE_PROMPT
