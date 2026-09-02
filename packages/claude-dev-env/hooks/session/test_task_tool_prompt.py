"""Tests for task_tool_prompt — SessionStart hook that directs task-tool tracking."""

import importlib
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

prompt = importlib.import_module("task_tool_prompt")
task_tool_prompt_constants = importlib.import_module("hooks_constants.task_tool_prompt_constants")
TASK_TOOL_DIRECTIVE = task_tool_prompt_constants.TASK_TOOL_DIRECTIVE


def _run_main() -> str:
    """Return stdout produced by running the hook's main()."""
    captured_stdout = StringIO()
    with patch("sys.stdout", captured_stdout):
        prompt.main()
    return captured_stdout.getvalue()


class TestSessionDirective:
    def test_main_emits_additional_context(self) -> None:
        emitted = json.loads(_run_main())
        hook_output = emitted["hookSpecificOutput"]
        assert hook_output["hookEventName"] == "SessionStart"
        assert "additionalContext" in hook_output

    def test_directive_names_the_tracking_tool(self) -> None:
        emitted = json.loads(_run_main())
        assert "task or todo tracking tool" in emitted["hookSpecificOutput"]["additionalContext"]

    def test_directive_names_no_vendor_or_host_product(self) -> None:
        emitted = json.loads(_run_main())
        additional_context = emitted["hookSpecificOutput"]["additionalContext"]
        for each_forbidden_term in ("Claude", "Cursor", "Codex", "TaskCreate", "TodoWrite"):
            assert each_forbidden_term not in additional_context

    def test_directive_says_create_tasks_at_session_start(self) -> None:
        emitted = json.loads(_run_main())
        additional_context = emitted["hookSpecificOutput"]["additionalContext"]
        assert "start of the session" in additional_context

    def test_directive_says_update_as_work_proceeds(self) -> None:
        emitted = json.loads(_run_main())
        additional_context = emitted["hookSpecificOutput"]["additionalContext"]
        assert "update" in additional_context
        assert "as work proceeds" in additional_context

    def test_directive_names_no_loop_cadence(self) -> None:
        emitted = json.loads(_run_main())
        additional_context = emitted["hookSpecificOutput"]["additionalContext"]
        assert "/loop" not in additional_context
        assert "cadence" not in additional_context
        assert "minute" not in additional_context

    def test_build_session_directive_returns_the_shared_constant(self) -> None:
        assert prompt.build_session_directive() == TASK_TOOL_DIRECTIVE
