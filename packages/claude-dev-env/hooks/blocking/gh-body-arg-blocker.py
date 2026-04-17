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
Falls back to a conservative approve if the logical line is unparseable.
"""

import json
import re
import shlex
import sys

from _gh_body_arg_utils import (
    all_body_flags,
    all_body_flag_prefixes,
    all_value_flags,
    get_logical_first_line,
)

_GH_BODY_SUBCOMMANDS = re.compile(
    r"\bgh\s+(?:"
    r"issue\s+(?:create|edit|comment)|"
    r"pr\s+(?:create|edit|comment|review)"
    r")\b",
    re.IGNORECASE,
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
    "Safe PowerShell pattern:\n"
    "  $bodyPath = [System.IO.Path]::ChangeExtension((New-TemporaryFile).FullName, '.md')\n"
    "  @'\n"
    "  <your markdown body>\n"
    "  '@ | Set-Content -Path $bodyPath -Encoding utf8\n"
    "  gh ... --body-file $bodyPath\n\n"
    "See ~/.claude/rules/gh-body-file.md for full guidance."
)


def _uses_body_string_arg(command: str) -> bool:
    """Return True if command calls an affected gh subcommand with --body <string>.

    Joins bash \\ and PowerShell ` line continuations before scanning so that
    '--body' on a continuation line is not missed. Uses shlex.split(posix=False)
    for Windows-friendly tokenization: backslashes in unquoted paths are preserved
    and quoted values retain their surrounding quotes as part of the token, so
    '--body' embedded in a quoted value cannot be mistaken for a standalone flag.
    Detects both '--body value'/'--body=value' forms and their short '-b'
    equivalents. Falls back to a conservative approve if the line is unparseable.
    """
    logical_line = get_logical_first_line(command)
    if not _GH_BODY_SUBCOMMANDS.search(logical_line):
        return False
    try:
        tokens = shlex.split(logical_line, posix=False)
    except ValueError:
        return False
    should_skip_next_token = False
    for each_token in tokens:
        if should_skip_next_token:
            should_skip_next_token = False
            continue
        if each_token in all_body_flags or any(
            each_token.startswith(each_prefix) for each_prefix in all_body_flag_prefixes
        ):
            return True
        if each_token in all_value_flags:
            should_skip_next_token = True
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
