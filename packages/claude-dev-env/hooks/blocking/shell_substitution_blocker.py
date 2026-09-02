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

A quoted heredoc body is stripped for the same reason. `<<'EOF'`, `<<"EOF"`
and `<<\\EOF` each tell bash to expand nothing between the opener and the
terminator, so a backtick there is text the file receives rather than a
command the shell runs. A bare `<<EOF` expands its body and keeps its scan,
and text outside any heredoc is scanned either way.

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
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from re import Match

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
    BACKSLASH_CHARACTER,
    COMMAND_LINE_SEPARATOR,
    DOUBLE_QUOTE_CHARACTER,
    NO_TERMINATOR_INDEX,
    SINGLE_QUOTE_CHARACTER,
    SINGLE_QUOTED_RUN_PATTERN,
    STRIPPED_RUN_REPLACEMENT,
    TOOL_INPUT_KEY,
    TOOL_NAME_KEY,
)


from hooks_constants.piped_pytest_blocker_constants import (  # noqa: E402
    HEREDOC_ESCAPE_GROUP,
    HEREDOC_OPENER_PATTERN,
    HEREDOC_QUOTE_GROUP,
    HEREDOC_TAB_STRIP_GROUP,
    HEREDOC_TAB_STRIP_MARKER,
    HEREDOC_TERMINATOR_GROUP,
    HEREDOC_UNQUOTED_MARKER,
)
from hooks_constants.shell_command_pipeline import (  # noqa: E402
    PendingHeredoc,
    closes_the_heredoc,
)


def _strip_single_quoted_runs(command: str) -> str:
    return SINGLE_QUOTED_RUN_PATTERN.sub(STRIPPED_RUN_REPLACEMENT, command)


def _opener_suppresses_expansion(opener_match: Match[str]) -> bool:
    """Return whether an opener's delimiter is quoted or backslash-escaped.

    ::

        <<'EOF'  -> True   quoted, the body is literal
        <<EOF    -> False  bare, bash expands the body

    Args:
        opener_match: One HEREDOC_OPENER_PATTERN match from a command line.

    Returns:
        True when bash expands nothing down to this opener's terminator.
    """
    is_quoted = opener_match.group(HEREDOC_QUOTE_GROUP) != HEREDOC_UNQUOTED_MARKER
    is_escaped = opener_match.group(HEREDOC_ESCAPE_GROUP) != HEREDOC_UNQUOTED_MARKER
    return is_quoted or is_escaped


def _sits_outside_quotes(command_line: str, character_index: int) -> bool:
    """Return whether a position on a line sits outside every quoted run.

    ::

        cat <<'EOF'      index of << -> True   bash reads an opener
        echo "<<'EOF'"   index of << -> False  bash reads a string

    Counting unescaped quotes before the position tells the two apart: an even
    count of each quote character means every run opened before it also closed.

    Args:
        command_line: One line of the command.
        character_index: Position of the candidate opener on that line.

    Returns:
        True when bash reads this position as shell syntax.
    """
    single_quote_count = 0
    double_quote_count = 0
    is_escaped = False
    for each_character in command_line[:character_index]:
        if is_escaped:
            is_escaped = False
            continue
        if each_character == BACKSLASH_CHARACTER:
            is_escaped = True
            continue
        if each_character == SINGLE_QUOTE_CHARACTER:
            single_quote_count += 1
        elif each_character == DOUBLE_QUOTE_CHARACTER:
            double_quote_count += 1
    return single_quote_count % 2 == 0 and double_quote_count % 2 == 0


def _first_literal_opener(command_line: str) -> Match[str] | None:
    """Return the line's first heredoc opener whose body bash leaves literal.

    An opener spelled inside a quoted string is text bash passes on, so it
    opens nothing and the lines below it stay in the scan.

    Args:
        command_line: One line of the command.

    Returns:
        The matching opener, or None when the line opens no literal heredoc.
    """
    for each_opener in HEREDOC_OPENER_PATTERN.finditer(command_line):
        if not _sits_outside_quotes(command_line, each_opener.start()):
            continue
        if _opener_suppresses_expansion(each_opener):
            return each_opener
    return None


def _index_past_literal_body(
    all_lines: list[str], body_start_index: int, opener_match: Match[str]
) -> int:
    """Return the index of the line that closes a literal heredoc body.

    The terminator match, including the ``<<-`` tab-strip rule, comes from
    ``closes_the_heredoc`` so this hook and the shared pipeline agree on what
    ends a body.

    Args:
        all_lines: Every line of the command.
        body_start_index: Index of the body's first line.
        opener_match: The opener whose terminator closes this body.

    Returns:
        The index of the terminator line, or NO_TERMINATOR_INDEX when the
        command holds none.
    """
    pending_heredoc = PendingHeredoc(
        terminator=opener_match.group(HEREDOC_TERMINATOR_GROUP),
        allows_leading_tabs=(
            opener_match.group(HEREDOC_TAB_STRIP_GROUP) == HEREDOC_TAB_STRIP_MARKER
        ),
    )
    for each_index in range(body_start_index, len(all_lines)):
        if closes_the_heredoc(all_lines[each_index], pending_heredoc):
            return each_index
    return NO_TERMINATOR_INDEX


def _strip_quoted_heredoc_bodies(command: str) -> str:
    """Return the command holding its openers, terminators, and shell text.

    ::

        cat <<'EOF'        ->  cat <<'EOF'
        inert text             EOF
        EOF

    A quoted or escaped delimiter makes the lines below it text the shell hands
    on, so a scan of those lines reports a substitution bash never runs. A bare
    delimiter keeps its body, and text outside any heredoc keeps its scan.

    An opener with no terminator returns the command whole. Bash consumes the
    rest of the input in that case, and dropping those lines would hide a live
    substitution among them.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        The command with each literal heredoc body dropped.
    """
    all_lines = command.split(COMMAND_LINE_SEPARATOR)
    all_kept_lines: list[str] = []
    each_index = 0
    while each_index < len(all_lines):
        current_line = all_lines[each_index]
        all_kept_lines.append(current_line)
        each_index += 1
        opener_match = _first_literal_opener(current_line)
        if opener_match is None:
            continue
        terminator_index = _index_past_literal_body(all_lines, each_index, opener_match)
        if terminator_index == NO_TERMINATOR_INDEX:
            return command
        each_index = terminator_index
    return COMMAND_LINE_SEPARATOR.join(all_kept_lines)


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

    Literal heredoc bodies are dropped first, then single-quoted runs are
    stripped, because bash substitutes nothing inside either. A backtick
    preceded by an odd backslash count is escaped.
    A `$((` pair is walked to its terminator (module docstring) to tell
    real arithmetic from a disguised subshell.

    Args:
        command: The raw Bash command string from the tool input.

    Returns:
        True when a substitution the matcher cannot descend into is present.
    """
    scannable_command = _strip_single_quoted_runs(_strip_quoted_heredoc_bodies(command))
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
