"""Tests for what the Bash and PowerShell PreToolUse chain costs to run.

A Bash tool call starts one interpreter, the dispatcher's own. Each roster
entry then runs in that process through runpy, so the roster's exact content is
the chain's cost after that single start. One allow-and-rewrite hook is the
whole roster; a blocking hook added here fails this test.
"""

import sys
from pathlib import Path

_HOOKS_ROOT = Path(__file__).resolve().parent.parent
if str(_HOOKS_ROOT) not in sys.path:
    sys.path.insert(0, str(_HOOKS_ROOT))

from hooks_constants.bash_pre_tool_use_dispatcher_constants import (
    ALL_BASH_HOSTED_HOOK_ENTRIES,
    ALL_BASH_ONLY_TOOL_NAMES,
    BashHostedHookEntry,
)


def test_bash_roster_starts_only_the_msys_rewriter_and_no_blocking_hook() -> None:
    assert ALL_BASH_HOSTED_HOOK_ENTRIES == (
        BashHostedHookEntry(
            script_relative_path="blocking/msys_rev_path_rewriter.py",
            applicable_tool_names=ALL_BASH_ONLY_TOOL_NAMES,
        ),
    )
