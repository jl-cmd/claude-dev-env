"""Tests for the write-byte hygiene PostToolUse hook."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.post_tool_use_dispatcher_constants import (  # noqa: E402
    BLOCK_DECISION,
)
from hooks_constants.write_byte_hygiene_constants import (  # noqa: E402
    CRLF_ERROR_MESSAGE,
    HYGIENE_EXIT_CODE,
    NUL_ERROR_MESSAGE,
)
from blocking.write_byte_hygiene import classify_file_bytes  # noqa: E402

_HOOK_SCRIPT = _HOOKS_ROOT / "blocking" / "write_byte_hygiene.py"
_DISPATCHER_SCRIPT = _HOOKS_ROOT / "validation" / "post_tool_use_dispatcher.py"
_PLUGIN_ROOT = _HOOKS_ROOT.parent


def _environment_without_git_hook_variables() -> dict[str, str]:
    return {
        each_name: each_value
        for each_name, each_value in os.environ.items()
        if not each_name.startswith("GIT_")
    }


def _payload(tool_name: str, file_path: Path) -> str:
    return json.dumps({"tool_name": tool_name, "tool_input": {"file_path": str(file_path)}})


def _run_hook(tool_name: str, file_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_HOOK_SCRIPT)],
        check=False,
        input=_payload(tool_name, file_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_environment_without_git_hook_variables(),
    )


def _run_dispatcher(tool_name: str, file_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_DISPATCHER_SCRIPT), str(_PLUGIN_ROOT)],
        check=False,
        input=_payload(tool_name, file_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_environment_without_git_hook_variables(),
    )


def test_classify_prefers_crlf_when_both_present() -> None:
    assert classify_file_bytes(b"a\r\x00b") == "crlf"


def test_classify_detects_nul_without_cr() -> None:
    assert classify_file_bytes(b"a\x00b") == "nul"


def test_classify_accepts_lf_only() -> None:
    assert classify_file_bytes(b"a\nb\n") == "ok"


def test_write_with_crlf_blocks(tmp_path: Path) -> None:
    target = tmp_path / "crlf.py"
    target.write_bytes(b"x=1\r\n")
    completed = _run_hook("Write", target)
    assert completed.returncode == HYGIENE_EXIT_CODE
    assert CRLF_ERROR_MESSAGE in completed.stderr
    parsed = json.loads(completed.stdout)
    assert parsed["decision"] == BLOCK_DECISION
    assert parsed["reason"] == CRLF_ERROR_MESSAGE


def test_edit_with_nul_blocks(tmp_path: Path) -> None:
    target = tmp_path / "nul.py"
    target.write_bytes(b"x=1\x00")
    completed = _run_hook("Edit", target)
    assert completed.returncode == HYGIENE_EXIT_CODE
    assert NUL_ERROR_MESSAGE in completed.stderr
    parsed = json.loads(completed.stdout)
    assert parsed["decision"] == BLOCK_DECISION
    assert parsed["reason"] == NUL_ERROR_MESSAGE


def test_lf_only_write_allows(tmp_path: Path) -> None:
    target = tmp_path / "clean.py"
    target.write_bytes(b"x=1\n")
    completed = _run_hook("Write", target)
    assert completed.returncode == 0
    assert completed.stdout.strip() == ""
    assert CRLF_ERROR_MESSAGE not in completed.stderr
    assert NUL_ERROR_MESSAGE not in completed.stderr


def test_bash_tool_is_noop(tmp_path: Path) -> None:
    target = tmp_path / "crlf.py"
    target.write_bytes(b"x=1\r\n")
    completed = _run_hook("Bash", target)
    assert completed.returncode == 0
    assert completed.stdout.strip() == ""


def test_dispatcher_blocks_crlf_write(tmp_path: Path) -> None:
    target = tmp_path / "crlf_module.py"
    target.write_bytes(b"x=1\r\n")
    completed = _run_dispatcher("Write", target)
    assert completed.stdout.strip()
    parsed = json.loads(completed.stdout)
    assert parsed["decision"] == BLOCK_DECISION
    assert CRLF_ERROR_MESSAGE in parsed["reason"]
