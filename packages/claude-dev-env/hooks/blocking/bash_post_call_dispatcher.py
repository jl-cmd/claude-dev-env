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
decision -- it is an observer, not a gate -- so this dispatcher runs the whole
roster unconditionally and never blocks. The one thing it forwards is context:
a hosted hook may print a ``hookSpecificOutput.additionalContext`` string (the
PR done reminder does), and the dispatcher joins every such string into one
PostToolUse payload. A hook that prints nothing adds nothing.

A single hosted hook crash fails open: ``run_hook_capturing_output`` isolates
it, so it contributes nothing and does not stop the remaining hosted hooks.

One interpreter start here serves the whole roster: every hosted hook's
imports load once into this process rather than once per hook.
"""

from __future__ import annotations

import json
import sys

import _path_setup  # noqa: F401

from hooks_constants.bash_post_call_dispatcher_constants import (
    ADDITIONAL_CONTEXT_JOIN_SEPARATOR,
    ADDITIONAL_CONTEXT_KEY,
    ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES,
    HOOK_SPECIFIC_OUTPUT_KEY,
    POST_TOOL_USE_HOOK_EVENT_NAME,
)
from hooks_constants.bash_pre_tool_use_dispatcher_constants import BashHostedHookEntry
from hooks_constants.hosted_hook_runner import (
    run_hook_capturing_output,
    resolved_hook_script_path,
    run_dispatcher_main,
)


def select_applicable_entries(tool_name: str) -> list[BashHostedHookEntry]:
    """Return the ordered hosted-hook entries that apply to tool_name."""
    return [
        each_entry
        for each_entry in ALL_BASH_POST_TOOL_USE_HOSTED_HOOK_ENTRIES
        if tool_name in each_entry.applicable_tool_names
    ]


def additional_context_from_hook_output(captured_stdout: str) -> str | None:
    """Return the additionalContext string a hosted hook printed, or None.

    Empty output, non-JSON output, and JSON without a non-empty
    ``hookSpecificOutput.additionalContext`` string all return None.
    """
    if not captured_stdout.strip():
        return None
    try:
        hook_output = json.loads(captured_stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(hook_output, dict):
        return None
    hook_specific_output = hook_output.get(HOOK_SPECIFIC_OUTPUT_KEY)
    if not isinstance(hook_specific_output, dict):
        return None
    additional_context = hook_specific_output.get(ADDITIONAL_CONTEXT_KEY)
    if not isinstance(additional_context, str) or not additional_context.strip():
        return None
    return additional_context


def dispatch(payload_text: str, tool_name: str) -> None:
    """Run every hosted hook applicable to tool_name, then forward their context.

    Each hosted hook's crash is isolated by ``run_hook_capturing_output``, so
    one hook failing never stops a later one in the same roster. Every
    additionalContext string the hooks printed is joined into one PostToolUse
    payload on stdout; when no hook printed one, nothing is written.
    """
    all_additional_context: list[str] = []
    for each_entry in select_applicable_entries(tool_name):
        script_path = resolved_hook_script_path(each_entry.script_relative_path)
        hook_run = run_hook_capturing_output(script_path, payload_text)
        additional_context = additional_context_from_hook_output(hook_run.captured_stdout)
        if additional_context is not None:
            all_additional_context.append(additional_context)
    if not all_additional_context:
        return
    payload = {
        HOOK_SPECIFIC_OUTPUT_KEY: {
            "hookEventName": POST_TOOL_USE_HOOK_EVENT_NAME,
            ADDITIONAL_CONTEXT_KEY: ADDITIONAL_CONTEXT_JOIN_SEPARATOR.join(all_additional_context),
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()


def main() -> None:
    """Read stdin once and dispatch the Bash PostToolUse hosted-hook roster."""
    run_dispatcher_main(dispatch)


if __name__ == "__main__":
    main()
