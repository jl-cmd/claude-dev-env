"""Tests for refactor advisory constants."""

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.refactor_guard_constants import (
    ALL_PYTHON_KEYWORDS,
    CHANGED_SURFACE_MATCH_RATIO,
    MAXIMUM_REFACTOR_LINE_DELTA,
    REFACTOR_LINE_DELTA_DIVISOR,
)

def test_refactor_threshold_constants_define_a_half_boundary() -> None:
    assert CHANGED_SURFACE_MATCH_RATIO * REFACTOR_LINE_DELTA_DIVISOR == 1
    assert MAXIMUM_REFACTOR_LINE_DELTA > REFACTOR_LINE_DELTA_DIVISOR
    assert "return" in ALL_PYTHON_KEYWORDS
