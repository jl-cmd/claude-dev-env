"""Tests for typed Codex Astra replies."""

import json
import sys
from pathlib import Path

SCRIPTS_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(SCRIPTS_ROOT / "config"))
sys.path.insert(0, str(SCRIPTS_ROOT))

from codex_astra_reply import (
    build_fallback_reply,
    build_success_reply,
    parse_codex_jsonl_reply,
)


def test_build_fallback_reply_preserves_fallback_kind() -> None:
    reply = build_fallback_reply("declined", True, "declined")

    assert reply.is_fallback
    assert reply.fallback_kind == "declined"


def test_build_success_reply_preserves_guidance_fields() -> None:
    reply = build_success_reply("thread-1", "PLAN\ninspect", "PLAN")

    assert reply.successful
    assert reply.session_id == "thread-1"
    assert reply.signal == "PLAN"


def test_parse_codex_jsonl_reply_preserves_fallback_kind() -> None:
    reply = parse_codex_jsonl_reply(
        json.dumps({"type": "thread.started", "thread_id": "thread-1"}),
        None,
        True,
        "broken",
    )

    assert reply.is_fallback
    assert reply.fallback_kind == "broken"
