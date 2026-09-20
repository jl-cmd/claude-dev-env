"""Run one registered hook the way its hooks.json entry registers it.

The payload shapes, the matcher evaluation, and the outcome classification
follow the external hooks reference (source lock W1). Nothing here imports a
hook module, so an expected outcome never comes from the code under test.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from hook_audit_parts.config.hook_harness_constants import (
    ALL_EVENTS_CARRYING_PERMISSION_MODE,
    ALL_EVENTS_CARRYING_TOOL_USE_ID,
    ALL_EVENTS_EXIT_TWO_BLOCKS,
    ALL_EVENTS_EXIT_TWO_FEEDS_MODEL,
    ALL_EVENTS_PLAIN_STDOUT_IS_CONTEXT,
    ALL_EVENTS_STDOUT_DISCARDED,
    ALL_HOME_ENVIRONMENT_NAMES,
    ALL_MATCH_EVERY_PAYLOAD_MATCHERS,
    ALL_MATCHER_FIELDS_BY_EVENT,
    ALL_OUTCOMES_BY_SEVERITY,
    ALL_SCRATCH_ENVIRONMENT_NAMES,
    DEFAULT_HOOK_TIMEOUT_SECONDS,
    EXACT_MATCHER_PATTERN,
    EXIT_CODE_BLOCKING,
    EXIT_CODE_SUCCESS,
    MATCHER_ALTERNATIVE_PATTERN,
    MILLISECONDS_PER_SECOND,
    PLUGIN_ROOT_ENVIRONMENT_NAME,
    PLUGIN_ROOT_PLACEHOLDER,
    SECONDS_PER_DAY,
    Outcome,
)


@dataclass(frozen=True)
class HookRegistration:
    event: str
    matcher: str
    command: str
    timeout_seconds: float

    @property
    def hook_id(self) -> str:
        script_name = self.command.replace('"', "").split("/")[-1]
        return f"{self.event}:{script_name}"


@dataclass(frozen=True)
class HookRun:
    exit_code: int | None
    stdout: str
    stderr: str
    wall_ms: float
    is_timed_out: bool
    parsed_stdout: dict[str, object] | None
    outcome: Outcome
    injected_characters: int


@dataclass
class Sandbox:
    root: Path
    home: Path = field(init=False)
    scratch: Path = field(init=False)

    def __post_init__(self) -> None:
        self.home = self.root / "home"
        self.scratch = self.root / "temp"
        self.home.mkdir(parents=True, exist_ok=True)
        self.scratch.mkdir(parents=True, exist_ok=True)

    def expand(self, templated_text: str) -> str:
        """Substitute the sandbox path placeholders a case row may carry.

        Args:
            templated_text: Text that may hold a sandbox path placeholder.

        Returns:
            The text with every placeholder expanded to a sandbox path.
        """
        return (
            templated_text.replace("{home}", self.home.as_posix())
            .replace("{temp}", self.scratch.as_posix())
            .replace("{sandbox}", self.root.as_posix())
        )

    def expand_payload(self, payload: object) -> object:
        """Substitute sandbox path placeholders through a nested payload.

        Args:
            payload: A string, list, dictionary, or scalar from a case row.

        Returns:
            The same shape with every string expanded.
        """
        if isinstance(payload, str):
            return self.expand(payload)
        if isinstance(payload, list):
            return [self.expand_payload(each_entry) for each_entry in payload]
        if isinstance(payload, dict):
            return {
                each_key: self.expand_payload(each_field)
                for each_key, each_field in payload.items()
            }
        return payload

    def environment(self, all_extra_environment: dict[str, str]) -> dict[str, str]:
        """Point the home and scratch environment names at this sandbox.

        Args:
            all_extra_environment: Names a case row sets on top of the sandbox.

        Returns:
            The environment mapping a hook process is started with.
        """
        environment = dict(os.environ)
        for each_name in ALL_HOME_ENVIRONMENT_NAMES:
            environment[each_name] = str(self.home)
        for each_name in ALL_SCRATCH_ENVIRONMENT_NAMES:
            environment[each_name] = str(self.scratch)
        environment.update(all_extra_environment)
        return environment


def _registration(
    event: str, matcher: str, all_handler_fields: dict[str, object]
) -> HookRegistration:
    return HookRegistration(
        event=event,
        matcher=matcher,
        command=str(all_handler_fields["command"]),
        timeout_seconds=float(
            all_handler_fields.get("timeout", DEFAULT_HOOK_TIMEOUT_SECONDS)
        ),
    )


def _registrations_for_event(
    event: str, all_groups: list[dict[str, object]]
) -> list[HookRegistration]:
    all_registrations: list[HookRegistration] = []
    for each_group in all_groups:
        all_handlers = each_group["hooks"]
        assert isinstance(all_handlers, list)
        matcher = str(each_group.get("matcher", ""))
        all_registrations.extend(
            _registration(event, matcher, each_handler)
            for each_handler in all_handlers
        )
    return all_registrations


def load_registrations(hooks_json_path: Path) -> list[HookRegistration]:
    """Read every hook a hooks.json file registers.

    Args:
        hooks_json_path: The hooks.json file to read.

    Returns:
        One registration per registered handler, in file order.
    """
    document = json.loads(hooks_json_path.read_text(encoding="utf-8"))
    all_registrations: list[HookRegistration] = []
    for each_event, each_group_list in document["hooks"].items():
        all_registrations.extend(
            _registrations_for_event(each_event, each_group_list)
        )
    return all_registrations


def build_payload(
    event: str, sandbox: Sandbox, all_event_fields: dict[str, object]
) -> dict[str, object]:
    """Build the stdin payload a client sends for one event.

    Args:
        event: The hook event name the payload announces.
        sandbox: The sandbox whose paths the payload points at.
        all_event_fields: Event-specific fields a case row supplies.

    Returns:
        The payload mapping, with every placeholder expanded.
    """
    payload: dict[str, object] = {
        "session_id": "audit-session-0001",
        "transcript_path": sandbox.expand(
            "{home}/.claude/projects/audit/transcript.jsonl"
        ),
        "cwd": sandbox.root.as_posix(),
        "hook_event_name": event,
    }
    if event in ALL_EVENTS_CARRYING_PERMISSION_MODE:
        payload["permission_mode"] = "default"
    if event in ALL_EVENTS_CARRYING_TOOL_USE_ID:
        payload["tool_use_id"] = "toolu_audit_0001"
    expanded_fields = sandbox.expand_payload(all_event_fields)
    assert isinstance(expanded_fields, dict)
    payload.update(expanded_fields)
    return payload


def is_matcher_hit(
    registration: HookRegistration, all_payload_fields: dict[str, object]
) -> bool:
    """Report whether a registration's matcher selects this payload.

    Args:
        registration: The registration whose event and matcher are read.
        all_payload_fields: The payload the matcher is evaluated against.

    Returns:
        True when the client would run this hook for this payload.
    """
    if registration.event != all_payload_fields.get("hook_event_name"):
        return False
    matcher = registration.matcher
    if matcher in ALL_MATCH_EVERY_PAYLOAD_MATCHERS:
        return True
    matcher_field = ALL_MATCHER_FIELDS_BY_EVENT.get(registration.event)
    if matcher_field is None:
        return True
    matched_field_text = str(all_payload_fields.get(matcher_field, ""))
    if EXACT_MATCHER_PATTERN.fullmatch(matcher):
        all_alternatives = [
            each_part.strip()
            for each_part in MATCHER_ALTERNATIVE_PATTERN.split(matcher)
        ]
        return matched_field_text in all_alternatives
    return re.search(matcher, matched_field_text) is not None


def resolve_shell() -> str:
    """Find the POSIX shell a shell-form hook command is started through.

    Returns:
        The path of the first shell found.

    Raises:
        FileNotFoundError: When no POSIX shell is on the host.
    """
    program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
    all_candidates = [
        program_files / "Git" / "bin" / "bash.exe",
        program_files / "Git" / "usr" / "bin" / "bash.exe",
    ]
    for each_candidate in all_candidates:
        if each_candidate.is_file():
            return str(each_candidate)
    located_shell = shutil.which("bash") or shutil.which("sh")
    if located_shell is None:
        raise FileNotFoundError("no POSIX shell found to run a shell-form hook command")
    return located_shell


def _decode_stdout(stripped_stdout: str) -> dict[str, object] | None:
    if not stripped_stdout.startswith("{"):
        return None
    try:
        decoded_stdout = json.loads(stripped_stdout)
    except json.JSONDecodeError:
        return None
    return decoded_stdout if isinstance(decoded_stdout, dict) else None


def _classify_exit_code(event: str, exit_code: int) -> Outcome | None:
    if exit_code == EXIT_CODE_BLOCKING:
        if event in ALL_EVENTS_EXIT_TWO_BLOCKS:
            return "block"
        if event in ALL_EVENTS_EXIT_TWO_FEEDS_MODEL:
            return "advise"
        return "harness_failure"
    if exit_code != EXIT_CODE_SUCCESS:
        return "harness_failure"
    return None


def classify(
    event: str, exit_code: int | None, stdout: str, is_timed_out: bool
) -> tuple[Outcome, dict[str, object] | None, int]:
    """Read one hook run the way a client reads it.

    Args:
        event: The hook event the run answered.
        exit_code: The process exit code, or None after a timeout.
        stdout: Everything the process wrote to stdout.
        is_timed_out: True when the process passed its registered timeout.

    Returns:
        The outcome, the decoded stdout mapping when there is one, and the
        count of context characters the run injects.
    """
    if is_timed_out or exit_code is None:
        return "harness_failure", None, 0
    exit_code_outcome = _classify_exit_code(event, exit_code)
    if exit_code_outcome is not None:
        return exit_code_outcome, None, 0
    stripped_stdout = stdout.strip()
    parsed_stdout = _decode_stdout(stripped_stdout)
    if event in ALL_EVENTS_STDOUT_DISCARDED:
        return "silent", parsed_stdout, 0
    if parsed_stdout is None:
        if stripped_stdout and event in ALL_EVENTS_PLAIN_STDOUT_IS_CONTEXT:
            return "advise", None, len(stripped_stdout)
        return "silent", None, 0
    return _classify_json(parsed_stdout)


def _classify_json(
    all_stdout_fields: dict[str, object],
) -> tuple[Outcome, dict[str, object], int]:
    hook_specific = all_stdout_fields.get("hookSpecificOutput")
    hook_specific_fields = hook_specific if isinstance(hook_specific, dict) else {}
    additional_context = hook_specific_fields.get("additionalContext")
    system_message = all_stdout_fields.get("systemMessage")
    injected_characters = (
        len(additional_context) if isinstance(additional_context, str) else 0
    )
    permission_decision = hook_specific_fields.get("permissionDecision")
    if permission_decision == "deny":
        return "block", all_stdout_fields, injected_characters
    if (
        all_stdout_fields.get("decision") == "block"
        or all_stdout_fields.get("continue") is False
    ):
        return "block", all_stdout_fields, injected_characters
    if permission_decision == "ask":
        return "ask", all_stdout_fields, injected_characters
    if "updatedInput" in hook_specific_fields:
        return "rewrite", all_stdout_fields, injected_characters
    if injected_characters or isinstance(system_message, str):
        return "advise", all_stdout_fields, injected_characters
    return "silent", all_stdout_fields, injected_characters


def _working_directory(stdin_text: str, sandbox: Sandbox) -> str:
    """Return the payload's cwd, the directory the client runs a hook in."""
    try:
        payload = json.loads(stdin_text)
    except json.JSONDecodeError:
        return str(sandbox.root)
    payload_cwd = payload.get("cwd") if isinstance(payload, dict) else None
    if isinstance(payload_cwd, str) and Path(payload_cwd).is_dir():
        return payload_cwd
    return str(sandbox.root)


def _completed_streams(
    registration: HookRegistration,
    stdin_text: str,
    command: str,
    all_environment: dict[str, str],
    sandbox: Sandbox,
) -> tuple[int | None, str, str, bool]:
    try:
        completed = subprocess.run(
            [resolve_shell(), "-c", command],
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=registration.timeout_seconds,
            env=all_environment,
            cwd=_working_directory(stdin_text, sandbox),
            check=False,
        )
    except subprocess.TimeoutExpired as timeout_failure:
        timed_out_stdout = (
            timeout_failure.stdout if isinstance(timeout_failure.stdout, str) else ""
        )
        timed_out_stderr = (
            timeout_failure.stderr if isinstance(timeout_failure.stderr, str) else ""
        )
        return None, timed_out_stdout, timed_out_stderr, True
    return completed.returncode, completed.stdout, completed.stderr, False


def run_hook(
    registration: HookRegistration,
    stdin_text: str,
    plugin_root: Path,
    sandbox: Sandbox,
    all_extra_environment: dict[str, str] | None = None,
) -> HookRun:
    """Start one registered hook and read what the client would read.

    Args:
        registration: The hook to start, as hooks.json registers it.
        stdin_text: The bytes handed to the hook on stdin.
        plugin_root: The checkout the plugin-root placeholder resolves to.
        sandbox: The sandbox whose home and scratch paths the hook sees.
        all_extra_environment: Names a case row sets for this run.

    Returns:
        The exit code, both streams, the wall time, and the outcome.
    """
    command = registration.command.replace(
        PLUGIN_ROOT_PLACEHOLDER, plugin_root.as_posix()
    )
    environment = sandbox.environment(all_extra_environment or {})
    environment[PLUGIN_ROOT_ENVIRONMENT_NAME] = plugin_root.as_posix()
    started_at = time.perf_counter()
    exit_code, stdout, stderr, is_timed_out = _completed_streams(
        registration, stdin_text, command, environment, sandbox
    )
    wall_ms = (time.perf_counter() - started_at) * MILLISECONDS_PER_SECOND
    outcome, parsed_stdout, injected_characters = classify(
        registration.event, exit_code, stdout, is_timed_out
    )
    return HookRun(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        wall_ms=wall_ms,
        is_timed_out=is_timed_out,
        parsed_stdout=parsed_stdout,
        outcome=outcome,
        injected_characters=injected_characters,
    )


def run_event_chain(
    all_registrations: list[HookRegistration],
    all_payload_fields: dict[str, object],
    plugin_root: Path,
    sandbox: Sandbox,
    excluded_hook_id: str | None = None,
    all_extra_environment: dict[str, str] | None = None,
) -> Outcome:
    """Return the strongest outcome over every matching hook except the excluded one.

    Args:
        all_registrations: Every hook registered for the checkout under audit.
        all_payload_fields: The payload each registration is matched against.
        plugin_root: The checkout the plugin-root placeholder resolves to.
        sandbox: The sandbox each hook runs inside.
        excluded_hook_id: A hook to leave out, which shows what the rest do.
        all_extra_environment: Names each run in the chain is started with.

    Returns:
        The strongest outcome any remaining hook reached.
    """
    all_outcomes: list[Outcome] = ["silent"]
    for each_registration in all_registrations:
        if each_registration.hook_id == excluded_hook_id:
            continue
        if not is_matcher_hit(each_registration, all_payload_fields):
            continue
        each_run = run_hook(
            each_registration,
            json.dumps(all_payload_fields),
            plugin_root,
            sandbox,
            all_extra_environment,
        )
        all_outcomes.append(each_run.outcome)
    return min(all_outcomes, key=ALL_OUTCOMES_BY_SEVERITY.index)


def age_path(target_path: Path, age_days: float) -> None:
    """Move a path's modification time back by a number of days.

    Args:
        target_path: The file or directory whose timestamps move.
        age_days: How many days into the past the timestamps move.
    """
    aged_timestamp = time.time() - age_days * SECONDS_PER_DAY
    os.utime(target_path, (aged_timestamp, aged_timestamp))
