"""Behavior tests for the Stop-hook dispatcher."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_HOOKS_DIR = str(Path(__file__).resolve().parent.parent)
_BLOCKING_DIR = Path(__file__).resolve().parent
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
_blocking_dir_text = str(_BLOCKING_DIR)
if _blocking_dir_text not in sys.path:
    sys.path.insert(0, _blocking_dir_text)

from hooks_constants.hosted_hook_runner import HostedHookRun  # noqa: E402
from stop_dispatcher import select_first_block_stdout  # noqa: E402

_DISPATCHER_SCRIPT = str(_BLOCKING_DIR / "stop_dispatcher.py")


def _block_json(reason: str) -> str:
    """Build a Stop block stdout string."""
    return json.dumps({"decision": "block", "reason": reason})


def test_first_block_wins_among_non_crashed_runs() -> None:
    """The first non-crashed block decision is the one the dispatcher emits."""
    all_runs = [
        HostedHookRun(captured_stdout="", did_crash=False),
        HostedHookRun(captured_stdout=_block_json("first"), did_crash=False),
        HostedHookRun(captured_stdout=_block_json("second"), did_crash=False),
    ]
    selected = select_first_block_stdout(all_runs)
    assert json.loads(selected)["reason"] == "first"


def test_crashed_hook_before_block_is_skipped() -> None:
    """A crash before a block fails open so a later block still surfaces."""
    all_runs = [
        HostedHookRun(captured_stdout="", did_crash=True),
        HostedHookRun(captured_stdout=_block_json("later"), did_crash=False),
    ]
    selected = select_first_block_stdout(all_runs)
    assert json.loads(selected)["reason"] == "later"


def test_no_block_when_every_hook_is_silent() -> None:
    """A silent chain produces no block stdout."""
    assert select_first_block_stdout([HostedHookRun("", False), HostedHookRun("", False)]) == ""


def test_dispatcher_exits_zero_on_empty_payload() -> None:
    """The dispatcher exits zero when stdin is empty."""
    completed = subprocess.run(
        [sys.executable, _DISPATCHER_SCRIPT],
        check=False,
        input="",
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == ""


def test_dispatcher_blocks_hedging_message_matching_standalone() -> None:
    """A hedging last_assistant_message blocks through the dispatcher."""
    payload_text = json.dumps(
        {
            "stop_hook_active": False,
            "last_assistant_message": "This is probably correct without a source.",
        }
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
    parsed = json.loads(completed.stdout)
    assert parsed["decision"] == "block"
    assert "probably" in parsed["reason"].lower() or "hedging" in parsed["reason"].lower()


def test_dispatcher_imports_standalone_with_only_blocking_on_the_path() -> None:
    """The dispatcher's bootstrap resolves hooks_constants without hooks/ on PYTHONPATH."""
    subprocess_environment = {**os.environ, "PYTHONPATH": str(_BLOCKING_DIR)}
    completed = subprocess.run(
        [sys.executable, "-c", "import stop_dispatcher; print('ok')"],
        check=False,
        capture_output=True,
        text=True,
        env=subprocess_environment,
    )
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "ok"
