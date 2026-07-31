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

    def test_emitted_prompt_carries_ledger_and_scope_lines(self) -> None:
        emitted = json.loads(_run_main())
        prompt_text = emitted["additionalContext"]
        assert "scratch txt file you'll keep running as you go; ledger, if you will." in prompt_text
        assert "Deliver what was asked, at the scope intended." in prompt_text
        assert 'answer "what happened" or "what did you find,"' in prompt_text

    def test_build_session_directive_returns_the_shared_constant(self) -> None:
        assert starter.build_session_directive() == WORKING_STYLE_PROMPT
