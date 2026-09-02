"""Constants for the Bash PostToolUse dispatcher.

Holds the ordered hosted-hook roster this dispatcher runs after a Bash call
finishes. Reuses ``BashHostedHookEntry`` and the Bash-only tool-name set from
``bash_pre_tool_use_dispatcher_constants`` -- the entry shape and the tool-name
membership question are identical on the PostToolUse side, so this module adds
no second copy of either.
"""

from __future__ import annotations

from hooks_constants.bash_pre_tool_use_dispatcher_constants import (
    ALL_BASH_ONLY_TOOL_NAMES,
    BashHostedHookEntry,
)

__all__ = ["ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES"]

ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES: tuple[BashHostedHookEntry, ...] = (
    BashHostedHookEntry("blocking/gh_pr_author_restore.py", ALL_BASH_ONLY_TOOL_NAMES),
    BashHostedHookEntry("observability/test_failure_recorder.py", ALL_BASH_ONLY_TOOL_NAMES),
)
