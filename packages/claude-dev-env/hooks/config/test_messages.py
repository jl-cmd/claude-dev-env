"""Smoke tests for config.messages — verify user-facing notice constants exist."""

import sys

sys.modules.pop("config", None)

from config import messages


def test_user_facing_notice_is_nonempty_string() -> None:
    assert isinstance(messages.USER_FACING_NOTICE, str)
    assert messages.USER_FACING_NOTICE


def test_user_facing_tdd_notice_is_nonempty_string() -> None:
    assert isinstance(messages.USER_FACING_TDD_NOTICE, str)
    assert messages.USER_FACING_TDD_NOTICE


def test_user_facing_askuserquestion_notice_is_nonempty_string() -> None:
    assert isinstance(messages.USER_FACING_ASKUSERQUESTION_NOTICE, str)
    assert messages.USER_FACING_ASKUSERQUESTION_NOTICE
