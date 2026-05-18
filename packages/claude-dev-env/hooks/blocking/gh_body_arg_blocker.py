#!/usr/bin/env python3
"""PreToolUse hook: block gh commands that use --body <string> instead of --body-file.

Root cause: in shell-invoked gh command contexts, passing markdown body text via
--body "..." can cause backticks to be stored as literal backslash-backtick sequences
on GitHub instead of rendering as inline code or code fences. Quoting and escaping
rules vary by execution environment (Bash, PowerShell, CMD) but the failure mode is
the same. The fix is always to write the body to a temp file and pass --body-file.

Affected subcommands: gh issue create/edit/comment, gh pr create/edit/comment/review.

Detection strategy: join bash \\ and PowerShell ` line continuations into a single
logical line, then use shlex.split(..., posix=False) on that line so '--body'
appearing inside a quoted flag value or in heredoc body content on non-continuation
lines does not trigger a false positive. Both '--body value' and '--body=value' forms are blocked,
as are their short '-b' equivalents. '--body-file' and '--body-file=...' are allowed.
Fails CLOSED on shlex ValueError when the logical line matches an affected
subcommand AND contains a bare '--body'/'-b' literal (exactly the heredoc
pattern this hook must catch); otherwise approves unparseable input.
"""

import json
import re
import sys

from _gh_body_arg_utils import (
    _is_bash_continuation,
    _is_powershell_continuation,
    all_body_flags,
    all_body_flag_prefixes,
    get_logical_first_line,
    iter_significant_tokens,
)

_GH_BODY_SUBCOMMANDS = re.compile(
    r"\bgh\s+(?:"
    r"issue\s+(?:create|edit|comment)|"
    r"pr\s+(?:create|edit|comment|review)"
    r")\b",
    re.IGNORECASE,
)

_BARE_BODY_TOKEN_PATTERN = re.compile(
    r"(?<!\S)(?:--body|-b)(?:=|(?![-\w]))",
)

_BASH_TOOL_NAME = "Bash"

_CORRECTIVE_MESSAGE = (
    "BLOCKED [gh-body-file]: gh --body <string> escapes backticks as \\` on GitHub, "
    "corrupting inline code and code fences in issues, PRs, comments, and reviews. "
    "Write the body to a temp file and use --body-file instead.\n\n"
    "Safe Python pattern:\n"
    "  import tempfile\n"
    "  with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:\n"
    "      f.write(body_text)\n"
    "      body_path = f.name\n"
    "  # then: gh ... --body-file body_path\n\n"
    "Safe PowerShell pattern (BOM-free, works on 5.1 and 7+):\n"
    "  $bodyPath = [System.IO.Path]::ChangeExtension((New-TemporaryFile).FullName, '.md')\n"
    "  $body = @'\n"
    "  <your markdown body>\n"
    "  '@\n"
    "  [IO.File]::WriteAllText($bodyPath, $body, [Text.UTF8Encoding]::new($false))\n"
    "  gh ... --body-file $bodyPath\n\n"
    "See ~/.claude/rules/gh-body-file.md for full guidance."
)


def _logical_line_has_bare_body_token(logical_line: str) -> bool:
    return bool(_BARE_BODY_TOKEN_PATTERN.search(logical_line))


def _line_before_marker_has_unclosed_double_quote(
    line_excluding_trailing_marker: str,
) -> bool:
    """Return True when the line text has an odd count of `"` characters.

    Counts every `"` character in the segment via `str.count('"')` and
    returns True when the total is odd. The target shell for this
    continuation check is PowerShell, which represents a literal double
    quote inside a double-quoted string as a doubled `""` rather than a
    backslash-escaped `\\"`. A raw `"` count is therefore the appropriate
    signal for whether a quoted segment is still open at the end of the
    line.

    An odd count means a body argument like `--body "Thanks ` opens a quote
    that this line never closes — the next line carries the closing quote.
    A trailing backtick on that line is body content, not a PowerShell
    continuation marker.
    """
    return (line_excluding_trailing_marker.count('"') % 2) == 1


def _has_backtick(command: str) -> bool:
    """Return True if command contains a backtick that is not a line continuation.

    Joins both bash `` \\ `` and PowerShell `` ` `` continuation lines so
    backticks in multi-line body values on later non-continuation lines are
    not missed. A PowerShell continuation marker requires whitespace before
    the trailing backtick AND a balanced quote count on the line excluding
    the marker — a line ending `--body "Thanks `` carries an unclosed quote,
    so the trailing backtick is body content rather than a continuation.

    Scans the entire command string for backtick characters, not just --body
    argument content. This is intentionally conservative — any command
    containing backticks should use --body-file regardless of where they
    appear. False positives (backticks in non-body flags) are safe
    over-blocks.
    """
    continuation_separator = " "
    all_joined_lines: list[str] = []
    for each_line in command.splitlines():
        stripped_line = each_line.rstrip()
        if _is_bash_continuation(stripped_line):
            all_joined_lines.append(stripped_line[:-1].rstrip() + continuation_separator)
            continue
        if _is_powershell_continuation(stripped_line):
            line_before_marker = stripped_line[:-1]
            if not _line_before_marker_has_unclosed_double_quote(line_before_marker):
                all_joined_lines.append(line_before_marker.rstrip() + continuation_separator)
                continue
        all_joined_lines.append(each_line)
    full_logical_command = "".join(all_joined_lines)
    return "`" in full_logical_command


def _uses_body_string_arg(command: str) -> bool:
    """Return True if command calls an affected gh subcommand with --body <string>.

    Joins bash \\ and PowerShell ` line continuations before scanning so that
    '--body' on a continuation line is not missed. Uses shlex.split(posix=False)
    for Windows-friendly tokenization: backslashes in unquoted paths are preserved
    and quoted values retain their surrounding quotes as part of the token, so
    '--body' embedded in a quoted value cannot be mistaken for a standalone flag.
    Detects both '--body value'/'--body=value' forms and their short '-b'
    equivalents. Fails CLOSED on shlex ValueError when the logical line matches
    an affected subcommand and contains a bare --body / -b token literal, since
    heredoc-wrapped --body arguments are exactly the pattern this hook exists
    to block; otherwise approves unparseable input (out of scope).
    """
    if not _GH_BODY_SUBCOMMANDS.search(get_logical_first_line(command)):
        return False
    try:
        significant_tokens = list(iter_significant_tokens(command))
    except ValueError:
        return _logical_line_has_bare_body_token(get_logical_first_line(command))
    for each_token, _remaining_tokens in significant_tokens:
        if each_token in all_body_flags:
            return True
        if any(each_token.startswith(each_prefix) for each_prefix in all_body_flag_prefixes):
            return True
    return False


def main() -> None:
    try:
        hook_input = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    if tool_name != _BASH_TOOL_NAME:
        sys.exit(0)

    command = hook_input.get("tool_input", {}).get("command", "")
    if not command:
        sys.exit(0)

    if not _uses_body_string_arg(command):
        sys.exit(0)

    if not _has_backtick(command):
        sys.exit(0)

    deny_payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": _CORRECTIVE_MESSAGE,
        }
    }
    print(json.dumps(deny_payload))
    sys.stdout.flush()
    sys.exit(0)


if __name__ == "__main__":
    main()
