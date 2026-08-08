"""Tests for the disabled hook_log_stop_wrapper Stop hook."""

from __future__ import annotations

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from diagnostic import hook_log_stop_wrapper


def test_main_returns_zero_without_side_effects() -> None:
    """Disabled main exits success and does no work."""
    assert hook_log_stop_wrapper.main() == 0
