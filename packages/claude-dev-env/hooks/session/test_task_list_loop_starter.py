"""Tests for task_list_loop_starter — SessionStart hook that starts a task-list loop."""

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

import task_list_loop_starter as starter

from hooks_constants.task_list_loop_starter_constants import (
    TASK_LIST_LOOP_DIRECTIVE,
    TASK_LIST_MAINTENANCE_INSTRUCTION,
)


def _run_main() -> str:
    """Return stdout produced by running the hook's main()."""
    captured_stdout = StringIO()
    with patch("sys.stdout", captured_stdout):
        starter.main()
    return captured_stdout.getvalue()


class TestSessionDirective:
    def test_main_emits_additional_context(self) -> None:
        emitted = json.loads(_run_main())
        assert "additionalContext" in emitted

    def test_directive_carries_the_one_line_instruction(self) -> None:
        emitted = json.loads(_run_main())
        assert TASK_LIST_MAINTENANCE_INSTRUCTION in emitted["additionalContext"]

    def test_directive_names_the_ten_minute_cadence(self) -> None:
        emitted = json.loads(_run_main())
        assert "10-minute" in emitted["additionalContext"]

    def test_directive_directs_starting_the_loop_skill(self) -> None:
        emitted = json.loads(_run_main())
        assert "loop skill" in emitted["additionalContext"]

    def test_directive_is_idempotent_about_an_existing_loop(self) -> None:
        emitted = json.loads(_run_main())
        assert "not already running" in emitted["additionalContext"]

    def test_build_session_directive_returns_the_shared_constant(self) -> None:
        assert starter.build_session_directive() == TASK_LIST_LOOP_DIRECTIVE
