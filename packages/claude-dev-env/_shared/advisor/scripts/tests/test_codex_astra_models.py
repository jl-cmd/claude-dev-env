"""Behavioral tests for Codex Astra model values."""

from codex_astra_models import _parse_codex_event


def test_parse_codex_event_reads_session_and_guidance() -> None:
    session_id, guidance = _parse_codex_event(
        '{"type":"thread.started","thread_id":"thread-1"}'
    )
    assert session_id == "thread-1"
    assert guidance is None
