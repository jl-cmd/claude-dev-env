"""Tests for Codex Astra support functions."""

from pathlib import Path

from codex_astra_support import reply_fallback, resolve_usage_probe_path


def test_resolve_usage_probe_path_uses_supplied_home(tmp_path: Path) -> None:
    assert resolve_usage_probe_path(tmp_path) == (
        tmp_path / ".claude" / "_shared" / "pr-loop" / "scripts" / "codex_usage_probe.py"
    )


def test_reply_fallback_marks_failed_advisor_reply() -> None:
    reply = reply_fallback("unavailable", True)
    assert reply.is_fallback
    assert not reply.successful
