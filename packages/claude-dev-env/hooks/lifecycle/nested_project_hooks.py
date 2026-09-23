#!/usr/bin/env python3
"""SessionStart and PreToolUse hook: run the hooks of checkouts nested one level down.

Claude Code reads project hooks from ``<project>/.claude/settings.json`` of the
directory a session starts in. A cloud session that holds several repository
checkouts starts in their parent directory, which has no settings of its own,
and ``--add-dir`` loads no hooks from the checkouts. Their start hooks and tool
guards then never run. This hook runs them::

    session directory (no .git, no .claude/settings.json)
    |-- checkout-a/.claude/settings.json   hooks run with CLAUDE_PROJECT_DIR=checkout-a
    `-- checkout-b/.claude/settings.json   hooks run with CLAUDE_PROJECT_DIR=checkout-b

Each child hook receives the same stdin payload, runs inside its checkout, and
keeps its own matcher and timeout. A child ``exit 2`` blocks the tool call and a
child ``deny`` or ``ask`` decision passes through; a child ``allow`` is dropped,
so no child widens permissions for the session. SessionStart output from every
child joins into one ``additionalContext``.

When the session directory is itself a checkout or holds its own settings,
Claude Code already runs those hooks, and this hook exits at once.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

_hooks_dir = str(Path(__file__).resolve().parent.parent)
if _hooks_dir not in sys.path:
    sys.path.insert(0, _hooks_dir)

from hooks_constants.nested_project_hooks_constants import (
    ADDITIONAL_CONTEXT_KEY,
    ALL_FORWARDED_PERMISSION_DECISIONS,
    ALL_MATCH_EVERYTHING_MATCHERS,
    BLOCKING_EXIT_CODE,
    CHECKOUT_MARKER_NAME,
    COMMAND_HOOK_TYPE,
    COMMAND_KEY,
    CONTEXT_SECTION_SEPARATOR,
    DEFAULT_HOOK_TIMEOUT_SECONDS,
    HOOK_EVENT_NAME_KEY,
    HOOK_EVENT_NAME_OUTPUT_KEY,
    HOOK_SPECIFIC_OUTPUT_KEY,
    HOOK_TYPE_KEY,
    HOOKS_KEY,
    ALL_MATCH_TARGET_KEYS_BY_EVENT,
    MATCHER_KEY,
    PERMISSION_DECISION_KEY,
    PRE_TOOL_USE_EVENT,
    PROJECT_DIRECTORY_ENVIRONMENT_VARIABLE,
    SESSION_START_EVENT,
    SETTINGS_DIRECTORY_NAME,
    SETTINGS_ENCODING,
    SETTINGS_FILE_NAME,
    SHELL_COMMAND_FLAG,
    ALL_SHELL_PROGRAM_NAMES,
    TIMEOUT_KEY,
)
from hooks_constants.subprocess_window import hidden_window_creation_flags


@dataclass(frozen=True)
class NestedHook:
    """One command hook a nested checkout declares for the current event."""

    project_directory: Path
    command: str
    timeout_seconds: float


@dataclass(frozen=True)
class HookVerdict:
    """What this hook hands back to Claude Code."""

    exit_code: int
    stdout_text: str
    stderr_text: str


def _settings_path(directory: Path) -> Path:
    return directory / SETTINGS_DIRECTORY_NAME / SETTINGS_FILE_NAME


def find_nested_projects(session_directory: Path) -> list[Path]:
    """Return the child checkouts whose project hooks Claude Code skipped.

    Args:
        session_directory: The directory the session started in.

    Returns:
        Each immediate child holding both a ``.git`` entry and a
        ``.claude/settings.json`` file, sorted by name. Empty when the
        session directory is a checkout or has settings of its own.
    """
    if (session_directory / CHECKOUT_MARKER_NAME).exists():
        return []
    if _settings_path(session_directory).is_file():
        return []
    try:
        all_children = sorted(session_directory.iterdir())
    except OSError:
        return []
    return [
        each_child
        for each_child in all_children
        if each_child.is_dir()
        and (each_child / CHECKOUT_MARKER_NAME).exists()
        and _settings_path(each_child).is_file()
    ]


def _read_hook_groups(project_directory: Path, event_name: str) -> list[object]:
    try:
        settings_text = _settings_path(project_directory).read_text(encoding=SETTINGS_ENCODING)
        settings = json.loads(settings_text)
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(settings, dict):
        return []
    hooks_by_event = settings.get(HOOKS_KEY)
    if not isinstance(hooks_by_event, dict):
        return []
    all_groups = hooks_by_event.get(event_name)
    if not isinstance(all_groups, list):
        return []
    return all_groups


def matcher_selects(matcher: object, match_target: str) -> bool:
    """Report whether a settings matcher selects this event's target.

    Args:
        matcher: The ``matcher`` value of one hook group, possibly absent.
        match_target: The tool name for PreToolUse, the start source for
            SessionStart.

    Returns:
        True for an absent, empty, or ``*`` matcher, and for a matcher whose
        pattern matches the whole target. An invalid pattern matches only
        its exact text.
    """
    if matcher is None:
        return True
    if not isinstance(matcher, str):
        return False
    if matcher in ALL_MATCH_EVERYTHING_MATCHERS:
        return True
    try:
        return re.fullmatch(matcher, match_target) is not None
    except re.error:
        return matcher == match_target


def _command_hook(project_directory: Path, hook_fields: object) -> NestedHook | None:
    if not isinstance(hook_fields, dict):
        return None
    if hook_fields.get(HOOK_TYPE_KEY) != COMMAND_HOOK_TYPE:
        return None
    command = hook_fields.get(COMMAND_KEY)
    if not isinstance(command, str) or not command.strip():
        return None
    timeout_value = hook_fields.get(TIMEOUT_KEY)
    timeout_seconds = DEFAULT_HOOK_TIMEOUT_SECONDS
    if isinstance(timeout_value, (int, float)) and timeout_value > 0:
        timeout_seconds = float(timeout_value)
    return NestedHook(project_directory, command, timeout_seconds)


def _selected_hook_entries(
    project_directory: Path, event_name: str, match_target: str
) -> list[object]:
    all_hook_entries: list[object] = []
    for each_group in _read_hook_groups(project_directory, event_name):
        if not isinstance(each_group, dict):
            continue
        if not matcher_selects(each_group.get(MATCHER_KEY), match_target):
            continue
        all_group_hooks = each_group.get(HOOKS_KEY)
        if isinstance(all_group_hooks, list):
            all_hook_entries.extend(all_group_hooks)
    return all_hook_entries


def collect_nested_hooks(
    session_directory: Path, event_name: str, match_target: str
) -> list[NestedHook]:
    """Return every nested command hook that this event selects, in order.

    Args:
        session_directory: The directory the session started in.
        event_name: The hook event being handled.
        match_target: The value the event's matchers compare against.

    Returns:
        The selected command hooks, checkout by checkout in name order and
        in declaration order inside each checkout.
    """
    all_candidates = (
        _command_hook(each_project, each_entry)
        for each_project in find_nested_projects(session_directory)
        for each_entry in _selected_hook_entries(each_project, event_name, match_target)
    )
    return [each_candidate for each_candidate in all_candidates if each_candidate is not None]


def _shell_program() -> str | None:
    for each_name in ALL_SHELL_PROGRAM_NAMES:
        found_path = shutil.which(each_name)
        if found_path:
            return found_path
    return None


def _hook_environment(project_directory: Path) -> dict[str, str]:
    return {**os.environ, PROJECT_DIRECTORY_ENVIRONMENT_VARIABLE: str(project_directory)}


def run_nested_hook(
    nested_hook: NestedHook, payload_text: str
) -> subprocess.CompletedProcess[str] | None:
    """Run one nested hook the way Claude Code would run it in its own checkout.

    Args:
        nested_hook: The hook to run.
        payload_text: The stdin payload Claude Code handed this hook.

    Returns:
        The completed process, or None when no shell exists, the command
        cannot start, or it outlives its timeout.
    """
    shell_program = _shell_program()
    if shell_program is None:
        return None
    try:
        return subprocess.run(
            [shell_program, SHELL_COMMAND_FLAG, nested_hook.command],
            input=payload_text,
            capture_output=True,
            text=True,
            cwd=nested_hook.project_directory,
            env=_hook_environment(nested_hook.project_directory),
            timeout=nested_hook.timeout_seconds,
            check=False,
            creationflags=hidden_window_creation_flags(),
        )
    except (subprocess.TimeoutExpired, OSError):
        return None


def _parsed_hook_output(stdout_text: str) -> dict[str, object] | None:
    try:
        parsed_output = json.loads(stdout_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed_output, dict):
        return None
    return parsed_output


def _permission_decision(all_output_fields: dict[str, object]) -> object:
    specific_output = all_output_fields.get(HOOK_SPECIFIC_OUTPUT_KEY)
    if not isinstance(specific_output, dict):
        return None
    return specific_output.get(PERMISSION_DECISION_KEY)


def pre_tool_use_verdict(
    all_results: list[subprocess.CompletedProcess[str]],
) -> HookVerdict:
    """Fold nested PreToolUse results into the one verdict Claude Code reads.

    Args:
        all_results: The completed nested hooks, in run order.

    Returns:
        A blocking exit carrying the child's stderr when any child exits 2,
        else the first child ``deny`` or ``ask`` output, else an empty pass.
    """
    for each_result in all_results:
        if each_result.returncode == BLOCKING_EXIT_CODE:
            return HookVerdict(BLOCKING_EXIT_CODE, "", each_result.stderr)
    for each_result in all_results:
        if each_result.returncode != 0:
            continue
        parsed_output = _parsed_hook_output(each_result.stdout)
        if parsed_output is None:
            continue
        if _permission_decision(parsed_output) in ALL_FORWARDED_PERMISSION_DECISIONS:
            return HookVerdict(0, json.dumps(parsed_output), "")
    return HookVerdict(0, "", "")


def _session_start_context(stdout_text: str) -> str:
    parsed_output = _parsed_hook_output(stdout_text)
    if parsed_output is None:
        return stdout_text.strip()
    specific_output = parsed_output.get(HOOK_SPECIFIC_OUTPUT_KEY)
    if not isinstance(specific_output, dict):
        return ""
    context_text = specific_output.get(ADDITIONAL_CONTEXT_KEY)
    return context_text.strip() if isinstance(context_text, str) else ""


def _non_empty_sections(all_sections: Iterable[str]) -> list[str]:
    return [each_section for each_section in all_sections if each_section]


def session_start_verdict(
    all_results: list[subprocess.CompletedProcess[str]],
) -> HookVerdict:
    """Join nested SessionStart output into one additional-context block.

    Args:
        all_results: The completed nested hooks, in run order.

    Returns:
        A pass whose stdout carries every child's context, or an empty pass
        when no child printed any.
    """
    all_context_sections = _non_empty_sections(
        _session_start_context(each_result.stdout) for each_result in all_results
    )
    stderr_text = CONTEXT_SECTION_SEPARATOR.join(
        _non_empty_sections(each_result.stderr.strip() for each_result in all_results)
    )
    if not all_context_sections:
        return HookVerdict(0, "", stderr_text)
    hook_output = {
        HOOK_SPECIFIC_OUTPUT_KEY: {
            HOOK_EVENT_NAME_OUTPUT_KEY: SESSION_START_EVENT,
            ADDITIONAL_CONTEXT_KEY: CONTEXT_SECTION_SEPARATOR.join(all_context_sections),
        }
    }
    return HookVerdict(0, json.dumps(hook_output), stderr_text)


def _completed_results(
    all_nested_hooks: list[NestedHook], payload_text: str
) -> list[subprocess.CompletedProcess[str]]:
    all_outcomes = (run_nested_hook(each_hook, payload_text) for each_hook in all_nested_hooks)
    return [each_outcome for each_outcome in all_outcomes if each_outcome is not None]


def forward_nested_hooks(session_directory: Path, payload_text: str) -> HookVerdict:
    """Run the nested checkouts' hooks for one payload and fold their results.

    Args:
        session_directory: The directory the session started in.
        payload_text: The stdin payload Claude Code handed this hook.

    Returns:
        The verdict for Claude Code. An empty pass for an unreadable payload
        or an event this hook does not forward.
    """
    payload = _parsed_hook_output(payload_text)
    if payload is None:
        return HookVerdict(0, "", "")
    event_name = payload.get(HOOK_EVENT_NAME_KEY)
    if not isinstance(event_name, str) or event_name not in ALL_MATCH_TARGET_KEYS_BY_EVENT:
        return HookVerdict(0, "", "")
    match_target = payload.get(ALL_MATCH_TARGET_KEYS_BY_EVENT[event_name])
    all_nested_hooks = collect_nested_hooks(
        session_directory, event_name, match_target if isinstance(match_target, str) else ""
    )
    all_results = _completed_results(all_nested_hooks, payload_text)
    if event_name == PRE_TOOL_USE_EVENT:
        return pre_tool_use_verdict(all_results)
    return session_start_verdict(all_results)


def main() -> None:
    """Entry point: read the payload, forward it, and exit with the verdict."""
    session_directory_text = os.environ.get(PROJECT_DIRECTORY_ENVIRONMENT_VARIABLE)
    if not session_directory_text:
        sys.exit(0)
    payload_text = sys.stdin.read()
    verdict = forward_nested_hooks(Path(session_directory_text), payload_text)
    if verdict.stdout_text:
        sys.stdout.write(verdict.stdout_text)
    if verdict.stderr_text:
        sys.stderr.write(verdict.stderr_text)
    sys.exit(verdict.exit_code)


if __name__ == "__main__":
    main()
