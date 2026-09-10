#!/usr/bin/env python3
"""PostToolUse context advisory: Git Bash rewrote a ``<rev>:<path>`` argument.

This hook never blocks. It watches every Bash call finish and, when git failed
with either its ambiguous-argument error or its invalid-object-name error and
the quoted argument carries the marks of MSYS path conversion, adds one loud
note to the agent's context::

    === MSYS PATH CONVERSION (context reminder, never a block) ===
    Git saw:     origin\\main;.claude\\skills\\x\\test_run_evals.py
    Git Bash rewrote a <rev>:<path> argument before git saw it, turning the
    colon into a semicolon and the slashes into backslashes.
    Fix:         export MSYS_NO_PATHCONV=1 MSYS2_ARG_CONV_EXCL='*'
    Put that export and the git command in the same command.

Why a reminder and not a gate: the rewriting happens inside the shell, so the
command text the agent wrote looks correct and the error names an argument the
agent never typed. The note arrives at the moment the failure lands, which is
the only moment the two names line up.

Quiet branches: a non-Bash tool, a zero-exit call, a failure carrying neither
marker, a quoted argument free of both mangling marks, and
a command that already exports the workaround each emit nothing.

Hosted by ``blocking/bash_post_call_dispatcher.py``, which forwards the
``hookSpecificOutput.additionalContext`` this hook prints.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

try:
    _hooks_root_directory = str(Path(__file__).resolve().parent.parent)
    if _hooks_root_directory not in sys.path:
        sys.path.insert(0, _hooks_root_directory)
    from hooks_constants.bash_pre_tool_use_dispatcher_constants import (
        ALL_BASH_ONLY_TOOL_NAMES,
    )
    from hooks_constants.msys_path_conversion_advisor_constants import (
        ADVISORY_HEADER,
        ADVISORY_LINE_SEPARATOR,
        ALL_MANGLED_ARGUMENT_MARKERS,
        ALL_MSYS_MANGLING_CHARACTERS,
        AMBIGUOUS_ARGUMENT_CLOSING_QUOTE,
        FIX_LINE_TEMPLATE,
        MANGLED_ARGUMENT_LINE_TEMPLATE,
        MANGLING_EXPLANATION_LINE,
        MSYS_EXPORT_FIX_LINE,
        MSYS_PATH_CONVERSION_VARIABLE_NAME,
        SAME_COMMAND_LINE,
    )
    from hooks_constants.pr_done_reminder_constants import EXIT_CODE_ERROR_PREFIX
    from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin
except ImportError as import_error:
    raise ImportError(
        "msys_path_conversion_advisor: cannot import its dependencies; "
        "ensure the hooks directory is importable."
    ) from import_error


def text_after_first_mangled_argument_marker(response_text: str) -> str | None:
    """Return what follows the first marker present in a git failure, else None.

    Git names a mangled ``<rev>:<path>`` argument under two messages, one for a
    path after the colon and one for an absolute path after the colon. The
    markers are walked in order and the first one present wins.

    Args:
        response_text: The harness response text for the failed call.

    Returns:
        The text following the opening quote of the first marker present, or
        None when the response carries no marker.
    """
    for each_marker in ALL_MANGLED_ARGUMENT_MARKERS:
        _, marker_text, text_after_marker = response_text.partition(each_marker)
        if marker_text:
            return text_after_marker
    return None


def mangled_revision_path_argument(command_text: str, tool_response: object) -> str | None:
    """Return the argument git reported, when MSYS mangled it, else None.

    Four conditions all hold before an argument is returned. The harness
    reported a non-zero exit status, which arrives as a string carrying the
    exit-code prefix. Git printed either its ambiguous-argument error or its
    invalid-object-name error, and the quoted argument after it closes. That
    argument carries a backslash or a semicolon, which is what path conversion
    leaves behind and what separates this failure from a revision that is
    simply absent. The command does not already export the workaround.

    Args:
        command_text: The Bash command text the agent ran.
        tool_response: The harness response for the finished call.

    Returns:
        The quoted argument word for word, or None to stay quiet.
    """
    if not isinstance(tool_response, str) or not tool_response.startswith(EXIT_CODE_ERROR_PREFIX):
        return None
    text_after_marker = text_after_first_mangled_argument_marker(tool_response)
    if text_after_marker is None:
        return None
    argument_text, closing_quote, _ = text_after_marker.partition(AMBIGUOUS_ARGUMENT_CLOSING_QUOTE)
    if not closing_quote:
        return None
    if not any(each_character in argument_text for each_character in ALL_MSYS_MANGLING_CHARACTERS):
        return None
    if MSYS_PATH_CONVERSION_VARIABLE_NAME in command_text:
        return None
    return argument_text


def build_advisory_context(mangled_argument: str) -> str:
    """Build the advisory text naming the mangled argument and the two exports.

    Args:
        mangled_argument: The argument git reported, word for word.

    Returns:
        The multi-line note the dispatcher forwards as additionalContext.
    """
    all_lines = [
        ADVISORY_HEADER,
        MANGLED_ARGUMENT_LINE_TEMPLATE.format(argument=mangled_argument),
        MANGLING_EXPLANATION_LINE,
        FIX_LINE_TEMPLATE.format(export_line=MSYS_EXPORT_FIX_LINE),
        SAME_COMMAND_LINE,
    ]
    return ADVISORY_LINE_SEPARATOR.join(all_lines)


def _emit_context(context_text: str) -> None:
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context_text,
        }
    }
    sys.stdout.write(json.dumps(payload))
    sys.stdout.flush()


def main() -> None:
    """Add the MSYS path-conversion note after a git call the shell mangled.

    Reads the PostToolUse payload from stdin. Every quiet branch returns with
    no output, so this hook can never alter or block a tool call.
    """
    hook_payload = read_hook_input_dictionary_from_stdin()
    if hook_payload is None or hook_payload.get("tool_name") not in ALL_BASH_ONLY_TOOL_NAMES:
        return
    tool_input = hook_payload.get("tool_input")
    command_text = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(command_text, str):
        return
    mangled_argument = mangled_revision_path_argument(
        command_text, hook_payload.get("tool_response")
    )
    if mangled_argument is not None:
        _emit_context(build_advisory_context(mangled_argument))


if __name__ == "__main__":
    main()
