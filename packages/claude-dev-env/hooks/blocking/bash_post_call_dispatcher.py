#!/usr/bin/env python3
"""PostToolUse dispatcher that hosts the Bash hook chain running after a call.

Named ``bash_post_call_dispatcher`` rather than the more obvious
``bash_post_tool_use_dispatcher``: ``bin/install.test.mjs`` counts every
PostToolUse command whose text contains the literal substring
``post_tool_use_dispatcher.py`` and asserts exactly one match, against the
unrelated Write/Edit dispatcher in ``validation/post_tool_use_dispatcher.py``.
That check carries no basename anchor (its PreToolUse sibling does), so a
correctly-named Bash-side sibling here would read as a second match of an
unrelated dispatcher. This name carries the same meaning without the
collision, and needs no change to that shared, out-of-scope test file.

Reads the tool payload from stdin once, selects the hosted hooks applicable to
the payload's tool name, and runs each one in-process via the shared
hosted-hook runner. A hosted PostToolUse hook here carries no permission
decision -- it is a side-effecting observer, not a gate -- so this dispatcher
runs the whole roster unconditionally and emits nothing itself, matching every
hosted hook's own empty-stdout contract.

A single hosted hook crash fails open: ``run_hook_capturing_output`` isolates
it, so it contributes nothing and does not stop the remaining hosted hooks.

One interpreter start here serves the whole roster: every hosted hook's
imports load once into this process rather than once per hook.
"""

from __future__ import annotations

from pathlib import Path

import _path_setup  # noqa: F401

from hooks_constants.bash_post_call_dispatcher_constants import (
    ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES,
)
from hooks_constants.bash_pre_tool_use_dispatcher_constants import BashHostedHookEntry
from hooks_constants.hosted_hook_runner import run_dispatcher_main, run_hook_capturing_output


def select_applicable_entries(tool_name: str) -> list[BashHostedHookEntry]:
    """Return the ordered hosted-hook entries that apply to tool_name."""
    return [
        each_entry
        for each_entry in ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES
        if tool_name in each_entry.applicable_tool_names
    ]


def _resolve_hook_script_path(relative_path: str) -> str:
    """Resolve a hooks/-relative path to an absolute script path."""
    hooks_root = Path(__file__).resolve().parent.parent
    return str(hooks_root / relative_path)


def dispatch(payload_text: str, tool_name: str) -> None:
    """Run every hosted hook applicable to tool_name, in registration order.

    Each hosted hook's crash is isolated by ``run_hook_capturing_output``, so
    one hook failing never stops a later one in the same roster.
    """
    for each_entry in select_applicable_entries(tool_name):
        script_path = _resolve_hook_script_path(each_entry.script_relative_path)
        run_hook_capturing_output(script_path, payload_text)


def main() -> None:
    """Read stdin once and dispatch the Bash PostToolUse hosted-hook roster."""
    run_dispatcher_main(dispatch)


if __name__ == "__main__":
    main()
