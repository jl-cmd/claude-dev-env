"""Detect body flags and recover the positional PR number from a gh command.

Reports whether a captured shell command carries any body or body-file flag,
and extracts the positional PR number (bare integer or GitHub PR URL) from a
gh pr edit/comment command while skipping value-taking flags and their values.
"""

import re
import shlex
import sys
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from blocking._gh_body_arg_utils import (  # noqa: E402
    all_body_flags,
    body_file_flag,
    body_file_short_flag,
    count_extra_tokens_to_skip_for_split_quoted_value,
    get_logical_first_line,
    is_flag_shaped_token,
    is_unresolvable_shell_value,
    match_body_file_equals_prefix,
    match_body_flag_equals_prefix,
    match_non_body_value_flag_equals_prefix,
    non_body_value_flags,
    strip_surrounding_quotes,
)
from hooks_constants.pr_description_enforcer_constants import (  # noqa: E402
    GH_PR_COMMAND_MIN_TOKEN_COUNT,
)


def _resolve_positional_pr_number(token: str) -> int | None:
    """Return the PR number named by a positional token, or None if it is not one.

    Accepts either a bare integer literal or a GitHub PR URL whose final path
    segment is ``/pull/<number>``. The token may carry surrounding quotes;
    unresolvable shell variables are rejected.
    """
    stripped_candidate = strip_surrounding_quotes(token)
    if is_unresolvable_shell_value(stripped_candidate):
        return None
    url_match = re.match(
        r"^https?://[^/]+/[^/]+/[^/]+/pull/(\d+)(?:[/?#].*)?$",
        stripped_candidate,
    )
    if url_match is not None:
        try:
            return int(url_match.group(1))
        except ValueError:
            return None
    try:
        return int(stripped_candidate)
    except ValueError:
        return None


def _extract_pr_number_from_command(command: str) -> int | None:
    """Return the PR number positional argument from a `gh pr edit|comment` command.

    Skips value-taking non-body flags (and their value tokens) so that ``--repo owner/r``
    pairs do not consume the trailing PR number. Accepts both a bare integer literal
    and a GitHub PR URL (``https://github.com/o/r/pull/<n>``) in the positional slot.

    Args:
        command: The raw shell command captured by the hook.

    Returns:
        The PR number when one positional value (integer or URL) is present, else None.
    """
    logical_line = get_logical_first_line(command)
    if not logical_line:
        return None
    try:
        all_tokens = shlex.split(logical_line, posix=False)
    except ValueError:
        return None
    if len(all_tokens) < GH_PR_COMMAND_MIN_TOKEN_COUNT:
        return None
    if all_tokens[0] != "gh" or all_tokens[1] != "pr":
        return None
    subcommand_token = all_tokens[2]
    if subcommand_token not in {"edit", "comment"}:
        return None
    all_value_taking_bare_flags: frozenset[str] = (
        non_body_value_flags | all_body_flags | {body_file_flag, body_file_short_flag}
    )
    token_index = GH_PR_COMMAND_MIN_TOKEN_COUNT
    while token_index < len(all_tokens):
        current_token = all_tokens[token_index]
        matched_equals_prefix = (
            match_non_body_value_flag_equals_prefix(current_token)
            or match_body_flag_equals_prefix(current_token)
            or match_body_file_equals_prefix(current_token)
        )
        if matched_equals_prefix is not None:
            first_value_token = current_token[len(matched_equals_prefix) :]
            remaining_raw_tokens = all_tokens[token_index + 1 :]
            extra_skip = (
                count_extra_tokens_to_skip_for_split_quoted_value(
                    remaining_raw_tokens, first_value_token
                )
                or 0
            )
            token_index += 1 + extra_skip
            continue
        if current_token in all_value_taking_bare_flags:
            token_index += 1
            if token_index < len(all_tokens):
                token_index += 1
            continue
        if is_flag_shaped_token(current_token):
            token_index += 1
            continue
        resolved_pr_number = _resolve_positional_pr_number(current_token)
        if resolved_pr_number is not None:
            return resolved_pr_number
        return None
    return None


def _command_carries_body_flag(command: str) -> bool:
    """Return True when the command string carries any body or body-file flag.

    Detects the body/body-file forms accepted by ``gh pr {create,edit,comment}``:

    - Long flags: a single ``"--body" in command`` substring check catches
      every long form — ``--body``, ``--body=<value>``, ``--body-file``, and
      ``--body-file=<value>`` — because ``--body`` is a prefix of
      ``--body-file``. No separate ``--body-file`` check is needed.
    - Short flags, space-separated: ``-b <value>``, ``-F <value>`` — matched
      as `` -b `` and `` -F `` so the literal substring cannot collide with a
      surrounding token (e.g. ``-base``, ``-Foo``).
    - Short flags, equal-attached: ``-b=<value>``, ``-F=<value>`` — matched
      as `` -b=`` and `` -F=`` for the same anti-collision reason. The test
      suite relies on this detection path.

    Args:
        command: The raw shell command captured by the hook.

    Returns:
        True if any documented body or body-file flag appears in the command.
    """
    return (
        "--body" in command
        or " -b " in command
        or " -b=" in command
        or " -F " in command
        or " -F=" in command
    )
