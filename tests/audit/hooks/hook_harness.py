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
from typing import Literal

Outcome = Literal["block", "ask", "rewrite", "advise", "silent", "harness_failure"]

PLUGIN_ROOT_TOKEN = "${CLAUDE_PLUGIN_ROOT}"
EXIT_CODE_SUCCESS = 0
EXIT_CODE_BLOCKING = 2
SECONDS_PER_DAY = 86400
ALL_EVENTS_EXIT_TWO_BLOCKS = frozenset({"PreToolUse", "UserPromptSubmit"})
ALL_EVENTS_EXIT_TWO_FEEDS_MODEL = frozenset({"PostToolUse"})
ALL_EVENTS_PLAIN_STDOUT_IS_CONTEXT = frozenset({"SessionStart", "UserPromptSubmit"})
ALL_EVENTS_OUTPUT_DISCARDED = frozenset({"SessionEnd", "InstructionsLoaded"})
MATCHER_FIELD_BY_EVENT = {
    "PreToolUse": "tool_name",
    "PostToolUse": "tool_name",
    "SessionStart": "source",
    "SessionEnd": "reason",
    "InstructionsLoaded": "load_reason",
}
EXACT_MATCHER_PATTERN = re.compile(r"^[A-Za-z0-9_\- ,|]*$")
OUTCOME_SEVERITY: tuple[Outcome, ...] = (
    "harness_failure",
    "block",
    "ask",
    "rewrite",
    "advise",
    "silent",
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
    parsed_output: dict[str, object] | None
    outcome: Outcome
    injected_characters: int


@dataclass
class Sandbox:
    root: Path
    home: Path = field(init=False)
    temp: Path = field(init=False)

    def __post_init__(self) -> None:
        self.home = self.root / "home"
        self.temp = self.root / "temp"
        self.home.mkdir(parents=True, exist_ok=True)
        self.temp.mkdir(parents=True, exist_ok=True)

    def expand(self, templated_text: str) -> str:
        return (
            templated_text.replace("{home}", self.home.as_posix())
            .replace("{temp}", self.temp.as_posix())
            .replace("{sandbox}", self.root.as_posix())
        )

    def expand_payload(self, payload: object) -> object:
        if isinstance(payload, str):
            return self.expand(payload)
        if isinstance(payload, list):
            return [self.expand_payload(each_item) for each_item in payload]
        if isinstance(payload, dict):
            return {
                each_key: self.expand_payload(each_value)
                for each_key, each_value in payload.items()
            }
        return payload

    def environment(self, extra_environment: dict[str, str]) -> dict[str, str]:
        environment = dict(os.environ)
        for each_name in ("HOME", "USERPROFILE"):
            environment[each_name] = str(self.home)
        for each_name in ("TEMP", "TMP", "TMPDIR"):
            environment[each_name] = str(self.temp)
        environment.update(extra_environment)
        return environment


def load_registrations(hooks_json_path: Path) -> list[HookRegistration]:
    document = json.loads(hooks_json_path.read_text(encoding="utf-8"))
    all_registrations: list[HookRegistration] = []
    for each_event, all_groups in document["hooks"].items():
        for each_group in all_groups:
            for each_handler in each_group["hooks"]:
                all_registrations.append(
                    HookRegistration(
                        event=each_event,
                        matcher=each_group.get("matcher", ""),
                        command=each_handler["command"],
                        timeout_seconds=float(each_handler.get("timeout", 600)),
                    )
                )
    return all_registrations


def build_payload(
    event: str, sandbox: Sandbox, event_fields: dict[str, object]
) -> dict[str, object]:
    payload: dict[str, object] = {
        "session_id": "audit-session-0001",
        "transcript_path": sandbox.expand(
            "{home}/.claude/projects/audit/transcript.jsonl"
        ),
        "cwd": sandbox.root.as_posix(),
        "hook_event_name": event,
    }
    if event in ("PreToolUse", "PostToolUse", "UserPromptSubmit"):
        payload["permission_mode"] = "default"
    if event in ("PreToolUse", "PostToolUse"):
        payload["tool_use_id"] = "toolu_audit_0001"
    expanded_fields = sandbox.expand_payload(event_fields)
    assert isinstance(expanded_fields, dict)
    payload.update(expanded_fields)
    return payload


def is_matcher_hit(registration: HookRegistration, payload: dict[str, object]) -> bool:
    if registration.event != payload.get("hook_event_name"):
        return False
    matcher = registration.matcher
    if matcher in ("", "*"):
        return True
    matcher_field = MATCHER_FIELD_BY_EVENT.get(registration.event)
    if matcher_field is None:
        return True
    matched_value = str(payload.get(matcher_field, ""))
    if EXACT_MATCHER_PATTERN.fullmatch(matcher):
        all_alternatives = [
            each_part.strip() for each_part in re.split(r"[|,]", matcher)
        ]
        return matched_value in all_alternatives
    return re.search(matcher, matched_value) is not None


def resolve_shell() -> str:
    all_candidates = [
        Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        / "Git"
        / "bin"
        / "bash.exe",
        Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        / "Git"
        / "usr"
        / "bin"
        / "bash.exe",
    ]
    for each_candidate in all_candidates:
        if each_candidate.is_file():
            return str(each_candidate)
    located_shell = shutil.which("bash") or shutil.which("sh")
    if located_shell is None:
        raise FileNotFoundError("no POSIX shell found to run a shell-form hook command")
    return located_shell


def classify(
    event: str, exit_code: int | None, stdout: str, is_timed_out: bool
) -> tuple[Outcome, dict[str, object] | None, int]:
    if is_timed_out or exit_code is None:
        return "harness_failure", None, 0
    if exit_code == EXIT_CODE_BLOCKING:
        if event in ALL_EVENTS_EXIT_TWO_BLOCKS:
            return "block", None, 0
        if event in ALL_EVENTS_EXIT_TWO_FEEDS_MODEL:
            return "advise", None, 0
        return "harness_failure", None, 0
    if exit_code != EXIT_CODE_SUCCESS:
        return "harness_failure", None, 0
    stripped_stdout = stdout.strip()
    parsed_output: dict[str, object] | None = None
    if stripped_stdout.startswith("{"):
        try:
            decoded_output = json.loads(stripped_stdout)
        except json.JSONDecodeError:
            decoded_output = None
        if isinstance(decoded_output, dict):
            parsed_output = decoded_output
    if event in ALL_EVENTS_OUTPUT_DISCARDED:
        return "silent", parsed_output, 0
    if parsed_output is None:
        if stripped_stdout and event in ALL_EVENTS_PLAIN_STDOUT_IS_CONTEXT:
            return "advise", None, len(stripped_stdout)
        return "silent", None, 0
    return _classify_json(parsed_output)


def _classify_json(
    parsed_output: dict[str, object],
) -> tuple[Outcome, dict[str, object], int]:
    hook_specific = parsed_output.get("hookSpecificOutput")
    hook_specific_fields = hook_specific if isinstance(hook_specific, dict) else {}
    additional_context = hook_specific_fields.get("additionalContext")
    system_message = parsed_output.get("systemMessage")
    injected_characters = (
        len(additional_context) if isinstance(additional_context, str) else 0
    )
    permission_decision = hook_specific_fields.get("permissionDecision")
    if permission_decision == "deny":
        return "block", parsed_output, injected_characters
    if (
        parsed_output.get("decision") == "block"
        or parsed_output.get("continue") is False
    ):
        return "block", parsed_output, injected_characters
    if permission_decision == "ask":
        return "ask", parsed_output, injected_characters
    if "updatedInput" in hook_specific_fields:
        return "rewrite", parsed_output, injected_characters
    if injected_characters or isinstance(system_message, str):
        return "advise", parsed_output, injected_characters
    return "silent", parsed_output, injected_characters


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


def run_hook(
    registration: HookRegistration,
    stdin_text: str,
    plugin_root: Path,
    sandbox: Sandbox,
    extra_environment: dict[str, str] | None = None,
) -> HookRun:
    command = registration.command.replace(PLUGIN_ROOT_TOKEN, plugin_root.as_posix())
    environment = sandbox.environment(extra_environment or {})
    environment["CLAUDE_PLUGIN_ROOT"] = plugin_root.as_posix()
    started_at = time.perf_counter()
    is_timed_out = False
    exit_code: int | None
    try:
        completed = subprocess.run(
            [resolve_shell(), "-c", command],
            input=stdin_text,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=registration.timeout_seconds,
            env=environment,
            cwd=_working_directory(stdin_text, sandbox),
            check=False,
        )
        exit_code, stdout, stderr = (
            completed.returncode,
            completed.stdout,
            completed.stderr,
        )
    except subprocess.TimeoutExpired as timeout_failure:
        is_timed_out = True
        exit_code = None
        stdout = (
            timeout_failure.stdout if isinstance(timeout_failure.stdout, str) else ""
        )
        stderr = (
            timeout_failure.stderr if isinstance(timeout_failure.stderr, str) else ""
        )
    wall_ms = (time.perf_counter() - started_at) * 1000
    outcome, parsed_output, injected_characters = classify(
        registration.event, exit_code, stdout, is_timed_out
    )
    return HookRun(
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        wall_ms=wall_ms,
        is_timed_out=is_timed_out,
        parsed_output=parsed_output,
        outcome=outcome,
        injected_characters=injected_characters,
    )


def run_event_chain(
    all_registrations: list[HookRegistration],
    payload: dict[str, object],
    plugin_root: Path,
    sandbox: Sandbox,
    excluded_hook_id: str | None = None,
) -> Outcome:
    """Return the strongest outcome over every matching hook except the excluded one."""
    all_outcomes: list[Outcome] = ["silent"]
    for each_registration in all_registrations:
        if each_registration.hook_id == excluded_hook_id:
            continue
        if not is_matcher_hit(each_registration, payload):
            continue
        each_run = run_hook(
            each_registration, json.dumps(payload), plugin_root, sandbox
        )
        all_outcomes.append(each_run.outcome)
    return min(all_outcomes, key=OUTCOME_SEVERITY.index)


def age_path(target_path: Path, age_days: float) -> None:
    aged_timestamp = time.time() - age_days * SECONDS_PER_DAY
    os.utime(target_path, (aged_timestamp, aged_timestamp))
