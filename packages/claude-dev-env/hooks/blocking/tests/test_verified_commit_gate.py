"""Entry-boundary behavior of the verified_commit_gate hook process.

Runs the hook as a subprocess the way Claude Code does and pins the two
silent paths: a tool the gate does not cover, and a gated command carrying
the bypass marker.
"""

import json
import pathlib
import subprocess
import sys

_BLOCKING_DIRECTORY = pathlib.Path(__file__).resolve().parent.parent
_GATE_SCRIPT_PATH = _BLOCKING_DIRECTORY / "verified_commit_gate.py"


def _run_gate_process(tool_name: str, command_text: str) -> str:
    payload_text = json.dumps(
        {
            "tool_name": tool_name,
            "tool_input": {"command": command_text},
            "cwd": str(_BLOCKING_DIRECTORY),
            "transcript_path": "",
        }
    )
    completed_process = subprocess.run(
        [sys.executable, str(_GATE_SCRIPT_PATH)],
        input=payload_text,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed_process.stdout


def test_uncovered_tool_name_stays_silent() -> None:
    assert _run_gate_process("Read", "git commit -m x") == ""


def test_bypass_marker_stays_silent_at_the_process_boundary() -> None:
    assert _run_gate_process("Bash", "git commit -m x # verify-skip") == ""
