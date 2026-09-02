"""Smoke tests for hooks_constants.messages — verify user-facing notice constants exist."""

from hooks_constants import messages


def test_module_carries_no_hedging_or_intent_ending_notices() -> None:
    """The hedging and intent-only-ending Stop hooks are removed; their
    dedicated notices no longer live here."""
    assert not hasattr(messages, "USER_FACING_NOTICE")
    assert not hasattr(messages, "USER_FACING_INTENT_ENDING_NOTICE")


def test_user_facing_tdd_notice_is_nonempty_string() -> None:
    assert isinstance(messages.USER_FACING_TDD_NOTICE, str)
    assert messages.USER_FACING_TDD_NOTICE


def test_user_facing_askuserquestion_notice_is_nonempty_string() -> None:
    assert isinstance(messages.USER_FACING_ASKUSERQUESTION_NOTICE, str)
    assert messages.USER_FACING_ASKUSERQUESTION_NOTICE
