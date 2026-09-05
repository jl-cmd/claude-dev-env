#!/usr/bin/env python3
"""PostToolUse context reminder: the PR done checklist after a push.

This hook never blocks. It watches every Bash call finish and, after a
successful ``git push`` or ``gh pr create``, probes the branch's pull request
through ``gh pr view`` and adds one loud checklist to the agent's context::

    === PR DONE CHECKLIST (context reminder, never a block) ===
    PR #42  https://github.com/acme/widgets/pull/42
    Mergeable:   CONFLICTING  (CONFLICTS with the base branch. Merge origin/main ...)
    CI checks:   1 failing, 2 pending, 4 total
    Draft:       yes
    Label done:  not set
    Verdict:     NOT DONE. Do not add the done label yet.
    Re-check:    gh pr view 42 --json mergeable,mergeStateStatus,statusCheckRollup,labels
    A PR is done only when every line above is clean.

Why a reminder and not a gate: agents keep working. The rule "a PR is done
only when GitHub reports it mergeable and CI is clean" arrives as live state
at the exact moment the agent just pushed, so no instruction file has to be
remembered. A block would stall the run; this only informs it.

Quiet branches: a non-Bash tool, a command that is not a push or a PR
creation, a push whose harness-reported exit status is non-zero, or a ``gh``
failure other than "no pull requests found" each emit nothing.

Hosted by ``blocking/bash_post_call_dispatcher.py``, which forwards the
``hookSpecificOutput.additionalContext`` this hook prints.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path

try:
    _hooks_root_directory = str(Path(__file__).resolve().parent.parent)
    if _hooks_root_directory not in sys.path:
        sys.path.insert(0, _hooks_root_directory)
    from hooks_constants.bash_pre_tool_use_dispatcher_constants import (
        ALL_BASH_AND_POWERSHELL_TOOL_NAMES,
    )
    from hooks_constants.pr_done_reminder_constants import (
        ADD_LABEL_COMMAND_TEMPLATE,
        ALL_FAILING_CHECK_CONCLUSIONS,
        ALL_PASSING_CHECK_CONCLUSIONS,
        CHECK_COMPLETED_STATUS,
        DONE_LABEL_NAME,
        EXIT_CODE_ERROR_PREFIX,
        GH_PR_CREATE_ACTION,
        GH_PR_SUBCOMMAND,
        ALL_GH_PR_VIEW_ARGUMENTS,
        ALL_GIT_OPTIONS_WITH_VALUE,
        ALL_POWERSHELL_COMMAND_FLAGS,
        ALL_POWERSHELL_PROGRAM_NAMES,
        GH_PR_VIEW_TIMEOUT_SECONDS,
        GH_PROGRAM_NAME,
        GIT_PROGRAM_NAME,
        GIT_PUSH_SUBCOMMAND,
        MERGEABLE_CLEAN_VALUE,
        MERGEABLE_UNKNOWN_VALUE,
        NO_PULL_REQUEST_MARKER,
        NO_PULL_REQUEST_REMINDER,
        RECHECK_COMMAND_TEMPLATE,
        REMINDER_FOOTER,
        REMINDER_HEADER,
        REMINDER_LINE_SEPARATOR,
        ALL_REMINDER_HINTS_BY_MERGEABLE,
        STATUS_CONTEXT_STATE_KEY,
        VERDICT_DONE,
        VERDICT_NOT_DONE,
    )
    from hooks_constants.pre_tool_use_stdin import read_hook_input_dictionary_from_stdin
    from hooks_constants.shell_command_segments import (
        effective_leading_program,
        split_into_segments,
        token_basename,
    )
except ImportError as import_error:
    raise ImportError(
        "pr_done_reminder: cannot import its dependencies; "
        "ensure the hooks directory is importable."
    ) from import_error


def _command_tokens(command: str) -> list[str]:
    try:
        return shlex.split(command, posix=True)
    except ValueError:
        return command.split()


def _segment_program_and_arguments(all_segment_tokens: list[str]) -> tuple[str, list[str]]:
    program_token = effective_leading_program(all_segment_tokens)
    if program_token is None:
        return "", []
    program_index = all_segment_tokens.index(program_token)
    return token_basename(program_token), all_segment_tokens[program_index + 1 :]


def _git_subcommand(all_arguments: list[str]) -> str | None:
    """Return git's subcommand after its global options.

    ``git -C <path> push`` and ``git -c <key=value> push`` carry an option
    value before the subcommand; ``--git-dir=<path>`` carries none. The first
    token left after those is the subcommand, so ``git stash push`` yields
    ``stash`` and ``git log --grep push`` yields ``log``.
    """
    should_skip_next_token = False
    for each_argument in all_arguments:
        if should_skip_next_token:
            should_skip_next_token = False
            continue
        if each_argument in ALL_GIT_OPTIONS_WITH_VALUE:
            should_skip_next_token = True
            continue
        if each_argument.startswith("-"):
            continue
        return each_argument
    return None


def _is_git_push(program_name: str, all_arguments: list[str]) -> bool:
    return (
        program_name == GIT_PROGRAM_NAME and _git_subcommand(all_arguments) == GIT_PUSH_SUBCOMMAND
    )


def _is_gh_pr_create(program_name: str, all_arguments: list[str]) -> bool:
    return program_name == GH_PROGRAM_NAME and all_arguments[:2] == [
        GH_PR_SUBCOMMAND,
        GH_PR_CREATE_ACTION,
    ]


def _powershell_inner_commands(all_command_tokens: list[str]) -> list[str]:
    """Return the script texts every ``pwsh -Command "..."`` wrapper runs.

    Read from the raw shlex tokens, before segment splitting: the quoted
    script is one token here, and splitting it on ``;`` first would cut a
    ``git add -A; git push`` script in half.
    """
    all_inner_commands: list[str] = []
    has_seen_powershell_program = False
    for each_token_index, each_token in enumerate(all_command_tokens[:-1]):
        if token_basename(each_token) in ALL_POWERSHELL_PROGRAM_NAMES:
            has_seen_powershell_program = True
            continue
        if has_seen_powershell_program and each_token.lower() in ALL_POWERSHELL_COMMAND_FLAGS:
            all_inner_commands.append(all_command_tokens[each_token_index + 1])
            has_seen_powershell_program = False
    return all_inner_commands


def command_triggers_reminder(command: str) -> bool:
    """Return True when any segment of the command is a git push or a gh pr create.

    A ``pwsh -Command "..."`` wrapper is unwrapped and its inner text scanned
    the same way, since the shell rule routes Bash-tool commands through pwsh.

    Args:
        command: The Bash command text the agent ran.
    """
    all_command_tokens = _command_tokens(command)
    for each_inner_command in _powershell_inner_commands(all_command_tokens):
        if command_triggers_reminder(each_inner_command):
            return True
    for each_segment in split_into_segments(all_command_tokens):
        program_name, all_arguments = _segment_program_and_arguments(each_segment)
        if _is_git_push(program_name, all_arguments) or _is_gh_pr_create(
            program_name, all_arguments
        ):
            return True
    return False


def _harness_reported_failure(tool_response: object) -> bool:
    return isinstance(tool_response, str) and tool_response.startswith(EXIT_CODE_ERROR_PREFIX)


def _check_outcome(all_check_fields: dict[str, object]) -> str:
    """Return failing, pending, or passing for one statusCheckRollup entry.

    A CheckRun entry carries ``status`` and ``conclusion``; a StatusContext
    entry carries ``state``. Both shapes appear in the same rollup list.
    """
    state_text = str(all_check_fields.get(STATUS_CONTEXT_STATE_KEY) or "").upper()
    if state_text:
        if state_text in ALL_FAILING_CHECK_CONCLUSIONS:
            return "failing"
        return "passing" if state_text in ALL_PASSING_CHECK_CONCLUSIONS else "pending"
    if str(all_check_fields.get("status") or "").upper() != CHECK_COMPLETED_STATUS:
        return "pending"
    conclusion_text = str(all_check_fields.get("conclusion") or "").upper()
    return "failing" if conclusion_text in ALL_FAILING_CHECK_CONCLUSIONS else "passing"


def _check_counts(all_pr_fields: dict[str, object]) -> dict[str, int]:
    all_checks = all_pr_fields.get("statusCheckRollup")
    all_check_counts = {"failing": 0, "pending": 0, "passing": 0, "total": 0}
    if not isinstance(all_checks, list):
        return all_check_counts
    for each_check_fields in all_checks:
        if isinstance(each_check_fields, dict):
            all_check_counts[_check_outcome(each_check_fields)] += 1
            all_check_counts["total"] += 1
    return all_check_counts


def _checks_line(all_check_counts: dict[str, int]) -> str:
    if all_check_counts["total"] == 0:
        return "none reported"
    return (
        f"{all_check_counts['failing']} failing, "
        f"{all_check_counts['pending']} pending, "
        f"{all_check_counts['total']} total"
    )


def _has_done_label(all_pr_fields: dict[str, object]) -> bool:
    all_labels = all_pr_fields.get("labels")
    if not isinstance(all_labels, list):
        return False
    return any(
        isinstance(each_label, dict) and each_label.get("name") == DONE_LABEL_NAME
        for each_label in all_labels
    )


def _is_done(mergeable_value: str, all_check_counts: dict[str, int]) -> bool:
    return (
        mergeable_value == MERGEABLE_CLEAN_VALUE
        and all_check_counts["failing"] == 0
        and all_check_counts["pending"] == 0
    )


def _verdict_lines(number: object, is_done: bool) -> list[str]:
    """Return the verdict line, the add-label command on DONE, and the re-check line."""
    all_lines = [f"Verdict:     {VERDICT_DONE if is_done else VERDICT_NOT_DONE}"]
    if is_done:
        add_label_command = ADD_LABEL_COMMAND_TEMPLATE.format(number=number, label=DONE_LABEL_NAME)
        all_lines.append(f"Add label:   {add_label_command}")
    all_lines.append(f"Re-check:    {RECHECK_COMMAND_TEMPLATE.format(number=number)}")
    return all_lines


def build_reminder_context(all_pr_fields: dict[str, object]) -> str:
    """Build the checklist text from a ``gh pr view --json`` object.

    Args:
        all_pr_fields: The parsed pull request JSON with number, url, isDraft,
            mergeable, mergeStateStatus, statusCheckRollup, and labels.

    Returns:
        The multi-line checklist ending in a DONE or NOT DONE verdict.
    """
    number = all_pr_fields.get("number", "?")
    mergeable_value = str(all_pr_fields.get("mergeable") or MERGEABLE_UNKNOWN_VALUE).upper()
    mergeable_hint = ALL_REMINDER_HINTS_BY_MERGEABLE.get(
        mergeable_value, ALL_REMINDER_HINTS_BY_MERGEABLE[MERGEABLE_UNKNOWN_VALUE]
    )
    all_check_counts = _check_counts(all_pr_fields)
    all_lines = [
        REMINDER_HEADER,
        f"PR #{number}  {all_pr_fields.get('url', '')}",
        f"Mergeable:   {mergeable_value}  ({mergeable_hint})",
        f"CI checks:   {_checks_line(all_check_counts)}",
        f"Draft:       {'yes' if all_pr_fields.get('isDraft') else 'no'}",
        f"Label done:  {'set' if _has_done_label(all_pr_fields) else 'not set'}",
        *_verdict_lines(number, _is_done(mergeable_value, all_check_counts)),
        REMINDER_FOOTER,
    ]
    return REMINDER_LINE_SEPARATOR.join(all_lines)


def _probe_pull_request(cwd: str) -> str | None:
    """Return the reminder text from a live ``gh pr view``, or None to stay quiet."""
    try:
        completed_process = subprocess.run(
            list(ALL_GH_PR_VIEW_ARGUMENTS),
            cwd=cwd or None,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GH_PR_VIEW_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed_process.returncode != 0:
        combined_output = f"{completed_process.stdout}\n{completed_process.stderr}".lower()
        return NO_PULL_REQUEST_REMINDER if NO_PULL_REQUEST_MARKER in combined_output else None
    try:
        all_pr_fields = json.loads(completed_process.stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(all_pr_fields, dict):
        return None
    return build_reminder_context(all_pr_fields)


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
    """Add the PR done checklist to context after a successful push or PR creation.

    Reads the PostToolUse payload from stdin. Every quiet branch returns with
    no output, so this hook can never alter or block a tool call.
    """
    hook_payload = read_hook_input_dictionary_from_stdin()
    if (
        hook_payload is None
        or hook_payload.get("tool_name") not in ALL_BASH_AND_POWERSHELL_TOOL_NAMES
    ):
        return
    tool_input = hook_payload.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(command, str) or not command_triggers_reminder(command):
        return
    if _harness_reported_failure(hook_payload.get("tool_response")):
        return
    context_text = _probe_pull_request(str(hook_payload.get("cwd") or ""))
    if context_text is not None:
        _emit_context(context_text)


if __name__ == "__main__":
    main()
