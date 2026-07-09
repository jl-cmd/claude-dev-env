"""Tests for the Stop-hook dispatcher hosted-hook roster."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_DIR = str(Path(__file__).resolve().parent.parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

from hooks_constants.stop_dispatcher_constants import ALL_STOP_HOSTED_HOOK_PATHS  # noqa: E402

_EXPECTED_STOP_ORDER = (
    "blocking/hedging_language_blocker.py",
    "blocking/question_to_user_enforcer.py",
    "blocking/intent_only_ending_blocker.py",
    "blocking/session_handoff_blocker.py",
    "diagnostic/hook_log_stop_wrapper.py",
)


def test_roster_lists_all_stop_hooks_in_registration_order() -> None:
    """The roster reproduces the standalone Stop chain order exactly."""
    assert ALL_STOP_HOSTED_HOOK_PATHS == _EXPECTED_STOP_ORDER


def test_every_roster_path_points_at_an_existing_hook() -> None:
    """Each roster path names a hook script present on disk, catching a typo."""
    hooks_root = Path(__file__).resolve().parent.parent
    for each_relative_path in ALL_STOP_HOSTED_HOOK_PATHS:
        assert (hooks_root / each_relative_path).is_file()
