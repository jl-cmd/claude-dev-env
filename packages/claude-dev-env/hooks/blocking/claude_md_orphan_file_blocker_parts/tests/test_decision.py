"""Tests for the CLAUDE.md orphan-file blocker decision parts module."""

import json

import pytest
from claude_md_orphan_file_blocker_parts import decision as decision_module
from claude_md_orphan_file_blocker_parts.config.orphan_blocker_constants import (
    ROW_FIRST_RETRY_HINT,
)
from claude_md_orphan_file_blocker_parts.decision import (
    build_block_payload,
    deny_orphan_files,
)


def test_deny_orphan_files_emits_deny(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(decision_module, "log_hook_block", lambda **each_argument: None)
    deny_orphan_files("Write", "/pkg/CLAUDE.md", "/pkg", ["absent.py"])
    emitted_payload = json.loads(capsys.readouterr().out)
    assert emitted_payload["hookSpecificOutput"]["permissionDecision"] == "deny"


def test_build_block_payload_names_missing_files_and_denies() -> None:
    block_payload = build_block_payload(["absent.py"], "/pkg")
    hook_output = block_payload["hookSpecificOutput"]
    assert hook_output["permissionDecision"] == "deny"
    assert "absent.py" in hook_output["permissionDecisionReason"]


def test_build_block_payload_appends_retry_hint() -> None:
    block_payload = build_block_payload(["absent.py"], "/pkg")
    assert ROW_FIRST_RETRY_HINT in block_payload["hookSpecificOutput"]["permissionDecisionReason"]
