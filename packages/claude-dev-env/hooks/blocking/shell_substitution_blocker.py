#!/usr/bin/env python3
"""PreToolUse hook: block Bash commands containing shell command substitution.

Root cause: Claude Code's auto-allowlist matcher operates on the raw command
string, not on parsed syntax, so it does not descend into command substitutions
such as $(...), unescaped backticks, or bash process substitutions <(...) and
>(...). A compound of the form

    cd X && echo "$(git rev-parse HEAD)"

therefore falls outside the auto-allowed set for `cd` + `echo` + `git rev-parse`
and forces a permission prompt, even though every segment would be auto-allowed
individually. The same mechanics apply to `diff <(cat a) <(cat b)` and
`tee >(gzip > out.gz)`: each inner command would be auto-allowed on its own,
but the outer wrapper defeats the matcher. Splitting into two separate Bash
tool calls, or collapsing to a substitution-free form like
`git -C X rev-parse HEAD`, avoids the prompt.

Detection: a regex match for `$(`, an unescaped backtick, or `<(` / `>(`, after
stripping single-quoted literal runs. Single-quoted regions are intentionally
ignored because bash performs no substitution inside them (for example
`echo '$(not-executed)'`). Backslash-escaped backticks outside single quotes
are treated as literal only when the count of preceding backslashes is odd;
an even count (including zero) means the backtick is a live substitution.

Bash arithmetic expansion ``$((...))`` is explicitly NOT blocked: it does not
spawn a subshell and does not defeat the allowlist matcher. Telling it apart
from a disguised command substitution takes more than counting two open
parens, because bash itself falls back from arithmetic to command
substitution when the expansion body does not close as arithmetic. Observed
against real bash:

    echo $((1 + 2))            prints 3            (arithmetic; not blocked)
    echo $((cd /tmp) && pwd)   prints the new cwd   (command substitution; blocked)
    echo $((1+2) )             runs "1+2" as a command, rc=0, no output
                                                     (command substitution; blocked)

Bash's own rule is the terminator: walk forward from ``$((`` tracking paren
depth; when depth returns to zero on a closer immediately preceded by
another ``)`` (an ``))`` pair), the expansion is arithmetic and passes. When
the closer that brings depth to zero is a lone ``)``, bash has fallen back to
running a parenthesized command inside the substitution, so it is blocked.
This hook applies that walk, tracking paren depth from the opening ``$((``.

False positives are still possible when the user is intentionally writing
shell-script content (for example, authoring a .sh file via heredoc) and the
substitution is literal payload rather than something to execute. In that
case, author the file with the Write tool, not a Bash heredoc.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.shell_substitution_blocker_constants import (  # noqa: E402
    BASH_TOOL_NAME,
    CLOSE_PAREN_CHARACTER,
    COMMAND_KEY,
    CORRECTIVE_MESSAGE,
    DENY_DECISION,
    DOLLAR_PAREN_PATTERN,
    EVEN_BACKSLASH_BACKTICK_PATTERN,
    HOOK_EVENT_NAME,
    HOOK_EVENT_NAME_KEY,
    HOOK_SPECIFIC_OUTPUT_KEY,
    OPEN_PAREN_CHARACTER,
    PAREN_DEPTH_AFTER_DOUBLE_OPEN,
    PERMISSION_DECISION_KEY,
    PERMISSION_DECISION_REASON_KEY,
    PROCESS_SUBSTITUTION_PATTERN,
    SINGLE_QUOTED_RUN_PATTERN,
    STRIPPED_RUN_REPLACEMENT,
    TOOL_INPUT_KEY,
    TOOL_NAME_KEY,
)


def _strip_single_quoted_runs(command: str) -> str:
    return SINGLE_QUOTED_RUN_PATTERN.sub(STRIPPED_RUN_REPLACEMENT, command)


def _closes_as_arithmetic_expansion(command: str, scan_start_index: int) -> bool:
    """Return True when a ``$((`` expansion closes on an ``))`` pair.

    See the module docstring for the real-bash evidence behind this rule.
    """
    paren_depth = PAREN_DEPTH_AFTER_DOUBLE_OPEN
    was_previous_character_close_paren = False
    for each_index in range(scan_start_index, len(command)):
        current_character = command[each_index]
        if current_character == OPEN_PAREN_CHARACTER:
            paren_depth += 1
            was_previous_character_close_paren = False
            continue
        if current_character != CLOSE_PAREN_CHARACTER:
            was_previous_character_close_paren = False
            continue
        paren_depth -= 1
        if paren_depth == 0:
            return was_previous_character_close_paren
        was_previous_character_close_paren = True
    return False


def _has_unsafe_dollar_paren_expansion(command: str) -> bool:
    """Return True for a `$(` that is not a safe `$((...))` arithmetic pair."""
    for each_match in DOLLAR_PAREN_PATTERN.finditer(command):
        is_arithmetic_style_open = (
            command[each_match.end() : each_match.end() + 1] == OPEN_PAREN_CHARACTER
        )
        if not is_arithmetic_style_open:
            return True
        if not _closes_as_arithmetic_expansion(command, each_match.end() + 1):
            return True
    return False


def has_shell_substitution(command: str) -> bool:
    """Return True when a Bash command carries a live shell substitution.

    ::

        echo "$(git rev-parse HEAD)"   flag: command substitution
        echo `date`                    flag: live backtick
        diff <(cat a) <(cat b)         flag: process substitution
        echo '$(not-executed)'         ok:   single-quoted, inert
        echo $((2 + 2))                ok:   arithmetic expansion

    Single-quoted runs are stripped first because bash substitutes nothing
    inside them. A backtick preceded by an odd backslash count is escaped.
    A `$((` pair is walked to its terminator (module docstring) to tell
    real arithmetic from a disguised subshell.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        True when a substitution the matcher cannot descend into is present.
    """
    scannable_command = _strip_single_quoted_runs(command)
    if _has_unsafe_dollar_paren_expansion(scannable_command):
        return True
    if EVEN_BACKSLASH_BACKTICK_PATTERN.search(scannable_command):
        return True
    if PROCESS_SUBSTITUTION_PATTERN.search(scannable_command):
        return True
    return False


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get(TOOL_NAME_KEY, "")
    if tool_name != BASH_TOOL_NAME:
        sys.exit(0)

    command = hook_input.get(TOOL_INPUT_KEY, {}).get(COMMAND_KEY, "")
    if not command or not has_shell_substitution(command):
        sys.exit(0)

    deny_payload = {
        HOOK_SPECIFIC_OUTPUT_KEY: {
            HOOK_EVENT_NAME_KEY: HOOK_EVENT_NAME,
            PERMISSION_DECISION_KEY: DENY_DECISION,
            PERMISSION_DECISION_REASON_KEY: CORRECTIVE_MESSAGE,
        }
    }
    print(json.dumps(deny_payload))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
