"""Behavior tests for the Stop-hook dispatcher."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS_DIR = str(Path(__file__).resolve().parent.parent)
_BLOCKING_DIR = Path(__file__).resolve().parent
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)
_blocking_dir_text = str(_BLOCKING_DIR)
if _blocking_dir_text not in sys.path:
    sys.path.insert(0, _blocking_dir_text)

from hooks_constants.hosted_hook_runner import HostedHookRun  # noqa: E402
from stop_dispatcher import dispatch, select_first_block_stdout  # noqa: E402

_DISPATCHER_SCRIPT = str(_BLOCKING_DIR / "stop_dispatcher.py")


def _block_json(
    reason: str, *, system_message: str = "", suppress_output: bool = False
) -> str:
    """Build a Stop block stdout string with optional supplementary fields."""
    payload: dict[str, object] = {"decision": "block", "reason": reason}
    if system_message:
        payload["systemMessage"] = system_message
    if suppress_output:
        payload["suppressOutput"] = True
    return json.dumps(payload)


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


def test_select_preserves_system_message_and_suppress_output() -> None:
    """select_first_block_stdout keeps supplementary fields on the winning block."""
    all_runs = [
        HostedHookRun(captured_stdout="", did_crash=True),
        HostedHookRun(
            captured_stdout=_block_json(
                "keep fields",
                system_message="rewrite the ending",
                suppress_output=True,
            ),
            did_crash=False,
        ),
    ]
    selected = json.loads(select_first_block_stdout(all_runs))
    assert selected["reason"] == "keep fields"
    assert selected["systemMessage"] == "rewrite the ending"
    assert selected["suppressOutput"] is True


def test_dispatch_re_emits_first_block_with_system_message_and_suppress(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """dispatch re-emits the first block's full JSON including supplementary fields."""
    all_responses = [
        HostedHookRun(captured_stdout="", did_crash=False),
        HostedHookRun(
            captured_stdout=_block_json(
                "hedging blocked",
                system_message="rewrite the ending",
                suppress_output=True,
            ),
            did_crash=False,
        ),
        HostedHookRun(captured_stdout=_block_json("later block"), did_crash=False),
    ]
    response_iterator = iter(all_responses)

    def _fake_run_hook(script_path: str, payload_text: str) -> HostedHookRun:
        del script_path, payload_text
        return next(response_iterator)

    monkeypatch.setattr("stop_dispatcher.run_hook_capturing_output", _fake_run_hook)
    monkeypatch.setattr(
        "stop_dispatcher.ALL_STOP_HOSTED_HOOK_PATHS",
        (
            "blocking/hedging_language_blocker.py",
            "blocking/question_to_user_enforcer.py",
            "diagnostic/hook_log_stop_wrapper.py",
        ),
    )
    dispatch('{"session_id": "test"}')
    emitted_payload = json.loads(capsys.readouterr().out.strip())
    assert emitted_payload["decision"] == "block"
    assert emitted_payload["reason"] == "hedging blocked"
    assert emitted_payload["systemMessage"] == "rewrite the ending"
    assert emitted_payload["suppressOutput"] is True


def test_dispatch_writes_nothing_when_no_hook_blocks(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """dispatch leaves stdout empty when every hosted hook is silent or allows."""
    monkeypatch.setattr(
        "stop_dispatcher.run_hook_capturing_output",
        lambda script_path, payload_text: HostedHookRun(captured_stdout="", did_crash=False),
    )
    monkeypatch.setattr(
        "stop_dispatcher.ALL_STOP_HOSTED_HOOK_PATHS",
        ("blocking/hedging_language_blocker.py",),
    )
    dispatch('{"session_id": "test"}')
    assert capsys.readouterr().out == ""


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
