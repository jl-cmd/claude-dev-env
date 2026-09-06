"""Tests for the retired Bash and PowerShell blocking roster."""

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.bash_pre_tool_use_dispatcher_constants import (
    ALL_BASH_HOSTED_HOOK_ENTRIES,
)


def test_retired_bash_roster_has_no_effective_blocking_hooks() -> None:
    assert ALL_BASH_HOSTED_HOOK_ENTRIES == ()
