"""Tests for the Stop-hook dispatcher hosted-hook roster."""

from hooks_constants.stop_dispatcher_constants import ALL_STOP_HOSTED_HOOK_PATHS


def test_roster_has_no_blocking_hooks() -> None:
    assert ALL_STOP_HOSTED_HOOK_PATHS == ()
