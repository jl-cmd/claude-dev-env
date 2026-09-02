"""Tests for the write_existing_file_blocker hook.

Each case drives the real hook's ``main()`` through its production stdin path,
feeding it the PreToolUse JSON payload Claude Code sends and reading the
permission decision back off stdout.
"""

from __future__ import annotations

import contextlib
import io
import json
from collections.abc import Mapping
from pathlib import Path

import pytest

import write_existing_file_blocker


def _run_payload(
    payload: Mapping[str, object],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> str:
    """Run the real hook entry point and return its stdout."""
    monkeypatch.setattr(write_existing_file_blocker.sys, "stdin", io.StringIO(json.dumps(payload)))
    with contextlib.suppress(SystemExit):
        write_existing_file_blocker.main()
    return capsys.readouterr().out


def _is_deny(stdout_text: str) -> bool:
    if not stdout_text.strip():
        return False
    decision = json.loads(stdout_text)
    return decision["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_write_denies_an_existing_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A Write onto a path that already exists is denied."""
    existing_path = tmp_path / "already_here.py"
    existing_path.write_text("x = 1\n", encoding="utf-8")
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": str(existing_path), "content": "x = 2\n"},
    }

    stdout = _run_payload(payload, monkeypatch, capsys)

    assert _is_deny(stdout), f"expected a deny, got {stdout!r}"


def test_apply_patch_add_denies_an_existing_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An apply_patch 'Add File' section targeting an existing path is denied."""
    existing_path = tmp_path / "already_here.py"
    existing_path.write_text("x = 1\n", encoding="utf-8")
    payload = {
        "tool_name": "apply_patch",
        "cwd": str(tmp_path),
        "tool_input": {
            "command": ("*** Begin Patch\n*** Add File: already_here.py\n+x = 2\n*** End Patch")
        },
    }

    stdout = _run_payload(payload, monkeypatch, capsys)

    assert _is_deny(stdout), f"expected a deny, got {stdout!r}"


def test_apply_patch_update_on_an_existing_target_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An 'Update File' section on an existing path is not an unread overwrite."""
    existing_path = tmp_path / "already_here.py"
    existing_path.write_text("x = 1\n", encoding="utf-8")
    payload = {
        "tool_name": "apply_patch",
        "cwd": str(tmp_path),
        "tool_input": {
            "command": (
                "*** Begin Patch\n"
                "*** Update File: already_here.py\n"
                "@@\n"
                "-x = 1\n"
                "+x = 2\n"
                "*** End Patch"
            )
        },
    }

    stdout = _run_payload(payload, monkeypatch, capsys)

    assert not _is_deny(stdout), f"expected an allow, got {stdout!r}"


def test_multi_edit_on_an_existing_target_is_allowed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A MultiEdit always targets a file already on disk, so it is never denied here.

    Every MultiEdit edit must match an ``old_string`` already present in the
    file, so MultiEdit carries no blind create-or-clobber path the way a Write
    or an apply_patch 'Add File' does — this hook allows it unconditionally.
    """
    existing_path = tmp_path / "already_here.py"
    existing_path.write_text("x = 1\n", encoding="utf-8")
    payload = {
        "tool_name": "MultiEdit",
        "tool_input": {
            "file_path": str(existing_path),
            "edits": [{"old_string": "x = 1", "new_string": "x = 2"}],
        },
    }

    stdout = _run_payload(payload, monkeypatch, capsys)

    assert not _is_deny(stdout), f"expected an allow, got {stdout!r}"
