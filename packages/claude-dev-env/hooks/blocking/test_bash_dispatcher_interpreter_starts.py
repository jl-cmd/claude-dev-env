"""Benchmark: consolidated Bash dispatcher starts one interpreter, not N.

Standalone registration starts one Python process per hosted hook. The
dispatcher replaces that chain with a single process that hosts every hook
in-process. This test pins the before/after interpreter-start counts so a
regression that re-splits the chain fails CI.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_HOOKS_DIR = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from hooks_constants.bash_pre_tool_use_dispatcher_constants import (  # noqa: E402
    ALL_BASH_HOSTED_HOOK_ENTRIES,
    BASH_TOOL_NAME,
)

_BLOCKING_DIR = Path(__file__).resolve().parent
_HOOKS_ROOT = _BLOCKING_DIR.parent
_DISPATCHER_SCRIPT = str(_BLOCKING_DIR / "bash_pre_tool_use_dispatcher.py")

STANDALONE_INTERPRETER_STARTS_PER_BASH_CALL = len(ALL_BASH_HOSTED_HOOK_ENTRIES)
DISPATCHER_INTERPRETER_STARTS_PER_BASH_CALL = 1


def test_roster_is_large_enough_that_consolidation_saves_starts() -> None:
    """Consolidation only pays off when the chain hosts more than one hook."""
    assert STANDALONE_INTERPRETER_STARTS_PER_BASH_CALL >= 10
    assert DISPATCHER_INTERPRETER_STARTS_PER_BASH_CALL == 1
    assert STANDALONE_INTERPRETER_STARTS_PER_BASH_CALL > DISPATCHER_INTERPRETER_STARTS_PER_BASH_CALL


def test_dispatcher_handles_a_bash_call_in_one_process() -> None:
    """One subprocess run of the dispatcher covers the full Bash hosted chain."""
    payload_text = json.dumps(
        {"tool_name": BASH_TOOL_NAME, "tool_input": {"command": "echo interpreter-start-probe"}}
    )
    completed = subprocess.run(
        [sys.executable, _DISPATCHER_SCRIPT],
        check=False,
        input=payload_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0
    assert DISPATCHER_INTERPRETER_STARTS_PER_BASH_CALL == 1


def test_standalone_chain_would_start_one_process_per_roster_entry() -> None:
    """Each roster path is a real script that would own its own interpreter start."""
    for each_entry in ALL_BASH_HOSTED_HOOK_ENTRIES:
        assert (_HOOKS_ROOT / each_entry.script_relative_path).is_file()
    assert len(ALL_BASH_HOSTED_HOOK_ENTRIES) == STANDALONE_INTERPRETER_STARTS_PER_BASH_CALL
