"""Bind and consult a read-only Codex CLI session at Astra low effort."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

_scripts_directory = Path(__file__).resolve().parent
_config_directory = _scripts_directory / "config"
_config_directory_text = str(_config_directory)
if _config_directory_text not in sys.path:
    sys.path.insert(0, _config_directory_text)

from advisor_scripts_constants.astra_advisor_constants import (
    ADVISOR_CODEX_EXECUTABLE_ENV_VAR,
    ALL_ASTRA_TRUTHY_VALUES,
    CLAUDE_CONFIG_DIRECTORY_NAME,
    CODEX_CONFIG_FLAG,
    CODEX_EXECUTABLE,
    CODEX_EXEC_SUBCOMMAND,
    CODEX_JSON_FLAG,
    CODEX_MODEL_FLAG,
    CODEX_PROMPT_FROM_STDIN,
    CODEX_READ_ONLY_SANDBOX,
    CODEX_REASONING_CONFIG_TEMPLATE,
    CODEX_RESUME_SUBCOMMAND,
    CODEX_SANDBOX_FLAG,
    USAGE_PROBE_FILENAME,
    USAGE_PROBE_PACKAGE_DIRECTORY_NAME,
    USAGE_PROBE_SCRIPTS_DIRECTORY_NAME,
    USAGE_PROBE_SHARED_DIRECTORY_NAME,
    ASTRA_BIND_FAILURE_REASON,
    ASTRA_CODEX_TIMEOUT_REASON,
    ASTRA_CODEX_TIMEOUT_SECONDS,
    ASTRA_EFFORT_FLAG,
    ASTRA_ENABLE_FLAG,
    ASTRA_ENV_VAR,
    ASTRA_EXECUTABLE_NOT_FOUND_REASON,
    ASTRA_FALLBACK_KIND_BROKEN,
    ASTRA_FALLBACK_KIND_DECLINED,
    ASTRA_INVALID_SIGNAL_REASON,
    ASTRA_MALFORMED_JSONL_REASON,
    ASTRA_MISSING_SESSION_REASON,
    ASTRA_PREFLIGHT_FAILURE_REASON,
    ASTRA_PROBE_TIMEOUT_REASON,
    ASTRA_REPLY_FAILURE_REASON,
    ASTRA_SESSION_ID_METAVAR,
    ASTRA_USAGE_PROBE_TIMEOUT_SECONDS,
)
from advisor_scripts_constants.advisor_route_constants import (  # noqa: E402
    ADVISOR_CODEX_MODEL_ID,
    ADVISOR_EFFORT_DEFAULT,
    ADVISOR_EFFORT_ENV_VAR,
    ADVISOR_FALLBACK_RESULT,
    ADVISOR_FALLBACK_TIER,
    ADVISOR_MODEL_TIER,
    ALL_ADVISOR_EFFORT_LEVELS,
    ALL_ADVISOR_GUIDANCE_SIGNALS,
    CODEX_BIND_SUCCESS_TOKEN,
    SPAWN_OUTCOME_KEY,
)


@dataclass(frozen=True)
class AstraPreflight:
    """Record the weekly-meter decision made before an Astra attempt."""

    eligible: bool
    percent_left: float | None
    reason: str
    fallback_kind: str | None = None


@dataclass(frozen=True)
class CodexAstraAdvisorReply:
    """Record a parsed Codex advisor response or an explicit fallback."""

    session_id: str | None
    guidance: str | None
    successful: bool
    reason: str | None
    is_fallback: bool
    signal: str | None
    astra_enabled: bool
    selected_tier: str
    outcome: str
    fallback_kind: str | None


def _preflight_fallback(
    reason: str,
    percent_left: float | None,
    fallback_kind: str,
) -> AstraPreflight:
    return AstraPreflight(False, percent_left, reason, fallback_kind)


def _reply_fallback(
    reason: str,
    is_astra_enabled: bool,
    fallback_kind: str | None = ASTRA_FALLBACK_KIND_BROKEN,
) -> CodexAstraAdvisorReply:
    return CodexAstraAdvisorReply(
        session_id=None,
        guidance=None,
        successful=False,
        reason=reason,
        is_fallback=True,
        signal=None,
        astra_enabled=is_astra_enabled,
        selected_tier=ADVISOR_FALLBACK_TIER,
        outcome=ADVISOR_FALLBACK_RESULT,
        fallback_kind=fallback_kind,
    )


def _reply_success(
    session_id: str,
    guidance: str,
    signal: str,
) -> CodexAstraAdvisorReply:
    return CodexAstraAdvisorReply(
        session_id=session_id,
        guidance=guidance,
        successful=True,
        reason=None,
        is_fallback=False,
        signal=signal,
        astra_enabled=True,
        selected_tier=ADVISOR_MODEL_TIER,
        outcome=CODEX_BIND_SUCCESS_TOKEN,
        fallback_kind=None,
    )


def _resolved_setting_by_name(
    setting_by_name: Mapping[str, str] | None,
) -> Mapping[str, str]:
    return os.environ if setting_by_name is None else setting_by_name


def is_astra_advisor_enabled(
    setting_by_name: Mapping[str, str] | None,
) -> bool:
    """Return whether the optional Astra rung is enabled.

    Args:
        setting_by_name: Optional environment-like settings mapping.

    Returns:
        Whether the Astra feature flag contains a recognized truthy value.
    """
    resolved_setting_by_name = _resolved_setting_by_name(setting_by_name)
    return (
        resolved_setting_by_name.get(ASTRA_ENV_VAR, "").strip().lower()
        in ALL_ASTRA_TRUTHY_VALUES
    )


def resolve_advisor_effort(
    setting_by_name: Mapping[str, str] | None,
) -> str:
    """Return the shared advisor effort from settings, or the default.

    ::

        resolve_advisor_effort({"ADVISOR_EFFORT": "medium"})
        # ok: "medium"
        resolve_advisor_effort({"ADVISOR_EFFORT": "MAX"})
        # ok: "max"
        resolve_advisor_effort({})
        # ok: default low
        resolve_advisor_effort({"ADVISOR_EFFORT": "nope"})
        # ok: default low
        resolve_advisor_effort({"ADVISOR_ASTRA_EFFORT": "high"})
        # ok: default low

    Fable and Astra both read this value. Unset and unrecognized values use
    low. The Astra-only name does not set effort.

    Args:
        setting_by_name: Optional environment-like settings mapping.

    Returns:
        One of low, medium, high, xhigh, or max.
    """
    resolved_setting_by_name = _resolved_setting_by_name(setting_by_name)
    requested_effort = (
        resolved_setting_by_name.get(ADVISOR_EFFORT_ENV_VAR, "").strip().lower()
    )
    if requested_effort in ALL_ADVISOR_EFFORT_LEVELS:
        return requested_effort
    return ADVISOR_EFFORT_DEFAULT


def resolve_usage_probe_path(home_directory: Path) -> Path:
    """Return the installed Codex weekly usage probe path.

    ::

        resolve_usage_probe_path(Path.home())
            -> ~/.claude/_shared/pr-loop/scripts/codex_usage_probe.py

    This is the only probe path the Astra helper uses. Do not search worktrees
    or archived ``skills/codex-review`` trees for a second copy.

    Args:
        home_directory: Home directory used to construct the path.

    Returns:
        The path to the installed weekly usage probe.
    """
    return (
        home_directory
        / CLAUDE_CONFIG_DIRECTORY_NAME
        / USAGE_PROBE_SHARED_DIRECTORY_NAME
        / USAGE_PROBE_PACKAGE_DIRECTORY_NAME
        / USAGE_PROBE_SCRIPTS_DIRECTORY_NAME
        / USAGE_PROBE_FILENAME
    )


def _load_usage_gate(probe_path: Path) -> Callable[[float], bool]:
    probe_directory = str(probe_path.parent)
    if probe_directory not in sys.path:
        sys.path.insert(0, probe_directory)
    usage_probe_module = importlib.import_module("codex_usage_probe")
    return usage_probe_module.is_codex_review_required


def _parse_probe_percent(stdout_text: str) -> tuple[float | None, str | None]:
    try:
        usage_report = json.loads(stdout_text)
    except (TypeError, json.JSONDecodeError):
        return None, "usage report is malformed"
    if not isinstance(usage_report, dict):
        return None, "usage report is malformed"
    raw_percent_left = usage_report.get("percent_left")
    if raw_percent_left is None:
        return None, "usage meter is unknown"
    if isinstance(raw_percent_left, bool) or not isinstance(
        raw_percent_left, (int, float)
    ):
        return None, "usage meter is malformed"
    percent_left = float(raw_percent_left)
    if not math.isfinite(percent_left):
        return None, "usage meter is malformed"
    return percent_left, None


def run_astra_preflight(
    probe_path: Path,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> AstraPreflight:
    """Run the existing usage probe and require a finite meter above its gate.

    Args:
        probe_path: Path to the installed usage probe.
        process_runner: Callable used to execute the probe.

    Returns:
        The usage-meter eligibility decision and any fallback reason.
    """
    try:
        completed_process = process_runner(
            [sys.executable, str(probe_path)],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=ASTRA_USAGE_PROBE_TIMEOUT_SECONDS,
        )
        if completed_process.returncode != 0:
            return _preflight_fallback(
                f"{ASTRA_PREFLIGHT_FAILURE_REASON}: probe exit {completed_process.returncode}",
                None,
                ASTRA_FALLBACK_KIND_BROKEN,
            )
        percent_left, parse_reason = _parse_probe_percent(completed_process.stdout)
        if parse_reason is not None:
            return _preflight_fallback(
                f"{ASTRA_PREFLIGHT_FAILURE_REASON}: {parse_reason}",
                None,
                ASTRA_FALLBACK_KIND_BROKEN,
            )
        usage_gate = _load_usage_gate(probe_path)
        if not callable(usage_gate) or percent_left is None:
            return _preflight_fallback(
                f"{ASTRA_PREFLIGHT_FAILURE_REASON}: usage meter is unknown",
                None,
                ASTRA_FALLBACK_KIND_BROKEN,
            )
        if not usage_gate(percent_left):
            return _preflight_fallback(
                f"{ASTRA_PREFLIGHT_FAILURE_REASON}: usage meter is at or below the gate",
                percent_left,
                ASTRA_FALLBACK_KIND_DECLINED,
            )
    except subprocess.TimeoutExpired as probe_error:
        return _preflight_fallback(
            f"{ASTRA_PROBE_TIMEOUT_REASON}: {probe_error}",
            None,
            ASTRA_FALLBACK_KIND_BROKEN,
        )
    except (
        OSError,
        subprocess.SubprocessError,
        ImportError,
        AttributeError,
        TypeError,
        ValueError,
    ) as probe_error:
        return _preflight_fallback(
            f"{ASTRA_PREFLIGHT_FAILURE_REASON}: {probe_error}",
            None,
            ASTRA_FALLBACK_KIND_BROKEN,
        )
    return AstraPreflight(True, percent_left, "usage meter is above the Astra gate")


def resolve_codex_executable(
    setting_by_name: Mapping[str, str] | None,
) -> str | None:
    """Resolve the Codex CLI executable to an invocable name or path.

    A bare "codex" name fails Windows `CreateProcess`, since the npm shim
    directory holds only `codex` (a sh script), `codex.cmd`, and `codex.ps1`.
    `shutil.which` finds `codex.cmd` via `PATHEXT`. An explicit override
    always wins and is trusted without a `which` check.

    Args:
        setting_by_name: Optional environment-like settings mapping.

    Returns:
        An invocable executable name or path, or None when unresolved.
    """
    resolved_setting_by_name = _resolved_setting_by_name(setting_by_name)
    executable_override = resolved_setting_by_name.get(ADVISOR_CODEX_EXECUTABLE_ENV_VAR, "").strip()
    if executable_override:
        return executable_override
    return shutil.which(CODEX_EXECUTABLE)


def build_codex_arguments(
    codex_executable: str,
    session_id: str | None = None,
    reasoning_effort: str = ADVISOR_EFFORT_DEFAULT,
) -> list[str]:
    """Build the installed CLI's shell-free bind or resume argv.

    Args:
        codex_executable: Resolved executable name or path to invoke.
        session_id: Optional existing session to resume.
        reasoning_effort: Codex model_reasoning_effort token.

    Returns:
        The shell-free Codex command argument vector.
    """
    command_arguments = [
        codex_executable,
        CODEX_EXEC_SUBCOMMAND,
        CODEX_MODEL_FLAG,
        ADVISOR_CODEX_MODEL_ID,
        CODEX_CONFIG_FLAG,
        CODEX_REASONING_CONFIG_TEMPLATE.format(effort=reasoning_effort),
        CODEX_SANDBOX_FLAG,
        CODEX_READ_ONLY_SANDBOX,
        CODEX_JSON_FLAG,
    ]
    if session_id is not None:
        command_arguments.extend([CODEX_RESUME_SUBCOMMAND, session_id])
    command_arguments.append(CODEX_PROMPT_FROM_STDIN)
    return command_arguments


def _guidance_signal(guidance: str) -> str | None:
    for each_line in guidance.splitlines():
        stripped_line = each_line.strip()
        if not stripped_line:
            continue
        return stripped_line if stripped_line in ALL_ADVISOR_GUIDANCE_SIGNALS else None
    return None


def parse_codex_jsonl_reply(
    jsonl_text: str,
    existing_session_id: str | None,
    is_astra_enabled: bool,
) -> CodexAstraAdvisorReply:
    """Parse strict Codex JSONL into a session id and final guidance.

    Args:
        jsonl_text: JSONL emitted by the Codex CLI.
        existing_session_id: Optional session id required on resume.
        is_astra_enabled: Whether the attempted route had Astra enabled.

    Returns:
        The parsed guidance or an explicit Fable fallback reply.
    """
    discovered_session_id: str | None = None
    final_guidance: str | None = None
    try:
        for each_line in jsonl_text.splitlines():
            if not each_line.strip():
                continue
            event = json.loads(each_line)
            if not isinstance(event, dict):
                return _reply_fallback(ASTRA_MALFORMED_JSONL_REASON, is_astra_enabled)
            if event.get("type") == "thread.started":
                thread_id = event.get("thread_id")
                if isinstance(thread_id, str) and thread_id.strip():
                    discovered_session_id = thread_id.strip()
            completed_event = event.get("item")
            if (
                event.get("type") == "item.completed"
                and isinstance(completed_event, dict)
                and completed_event.get("type") == "agent_message"
                and isinstance(completed_event.get("text"), str)
            ):
                final_guidance = completed_event["text"].strip()
    except (TypeError, json.JSONDecodeError):
        return _reply_fallback(ASTRA_MALFORMED_JSONL_REASON, is_astra_enabled)
    if discovered_session_id is None:
        return _reply_fallback(ASTRA_MISSING_SESSION_REASON, is_astra_enabled)
    if (
        existing_session_id is not None
        and discovered_session_id != existing_session_id
    ):
        return _reply_fallback(ASTRA_MISSING_SESSION_REASON, is_astra_enabled)
    if not final_guidance:
        return _reply_fallback(ASTRA_REPLY_FAILURE_REASON, is_astra_enabled)
    guidance_signal = _guidance_signal(final_guidance)
    if guidance_signal is None:
        return _reply_fallback(ASTRA_INVALID_SIGNAL_REASON, is_astra_enabled)
    return _reply_success(discovered_session_id, final_guidance, guidance_signal)


def _resolve_astra_preflight(
    preflight: AstraPreflight | None,
    probe_path: Path | None,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> AstraPreflight:
    if preflight is not None:
        return preflight
    resolved_probe_path = (
        resolve_usage_probe_path(Path.home()) if probe_path is None else probe_path
    )
    return run_astra_preflight(
        probe_path=resolved_probe_path, process_runner=process_runner
    )


def run_codex_astra_advisor(
    prompt: str,
    working_directory: Path,
    preflight: AstraPreflight | None,
    probe_path: Path | None,
    setting_by_name: Mapping[str, str] | None,
    session_id: str | None,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> CodexAstraAdvisorReply:
    """Run one usage-gated read-only Astra bind or resume attempt.

    Args:
        prompt: Advisor charter or delta consult sent to Codex.
        working_directory: Repository directory supplied to the CLI.
        preflight: Optional precomputed usage-meter decision.
        probe_path: Optional installed usage-probe path.
        setting_by_name: Optional environment-like settings mapping.
        session_id: Existing session id for a resume attempt.
        process_runner: Callable used to execute the probe and Codex.

    Returns:
        The parsed Astra guidance or an explicit Fable fallback reply.
    """
    if not is_astra_advisor_enabled(setting_by_name):
        return _reply_fallback(
            "Astra advisor flag is disabled",
            False,
            fallback_kind=ASTRA_FALLBACK_KIND_DECLINED,
        )
    codex_executable = resolve_codex_executable(setting_by_name)
    if codex_executable is None:
        return _reply_fallback(ASTRA_EXECUTABLE_NOT_FOUND_REASON, True)
    resolved_preflight = _resolve_astra_preflight(preflight, probe_path, process_runner)
    if not resolved_preflight.eligible:
        return _reply_fallback(
            resolved_preflight.reason,
            True,
            fallback_kind=resolved_preflight.fallback_kind,
        )
    try:
        completed_process = process_runner(
            build_codex_arguments(
                codex_executable,
                session_id=session_id,
                reasoning_effort=resolve_advisor_effort(setting_by_name),
            ),
            cwd=str(working_directory),
            input=prompt,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=ASTRA_CODEX_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as bind_error:
        return _reply_fallback(f"{ASTRA_CODEX_TIMEOUT_REASON}: {bind_error}", True)
    except (OSError, subprocess.SubprocessError) as bind_error:
        return _reply_fallback(f"{ASTRA_BIND_FAILURE_REASON}: {bind_error}", True)
    if completed_process.returncode != 0:
        return _reply_fallback(
            f"{ASTRA_BIND_FAILURE_REASON}: process exit {completed_process.returncode}",
            True,
        )
    return parse_codex_jsonl_reply(
        completed_process.stdout,
        existing_session_id=session_id,
        is_astra_enabled=True,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for Astra bind and resume.

    Returns:
        The parser for the helper's bind and resume modes.
    """
    argument_parser = argparse.ArgumentParser(
        description="Bind or consult a read-only Codex Astra advisor."
    )
    mode_group = argument_parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--bind", action="store_true")
    mode_group.add_argument("--resume", metavar=ASTRA_SESSION_ID_METAVAR)
    argument_parser.add_argument("--cwd", required=True, type=Path)
    argument_parser.add_argument(
        ASTRA_ENABLE_FLAG,
        dest="is_astra_requested",
        action="store_true",
        help="Open the Astra rung for this invocation without an environment flag.",
    )
    argument_parser.add_argument(
        ASTRA_EFFORT_FLAG,
        dest="astra_effort",
        choices=ALL_ADVISOR_EFFORT_LEVELS,
        default=None,
        help="Shared advisor effort for this invocation.",
    )
    return argument_parser


def main(all_cli_arguments: Sequence[str]) -> int:
    """Run one bind or resume from stdin and print a JSON response.

    Args:
        all_cli_arguments: Command-line arguments without the program name.

    Returns:
        Zero for a successful Astra response, or one for an explicit fallback.
    """
    parsed_arguments = build_argument_parser().parse_args(list(all_cli_arguments))
    setting_by_name: dict[str, str] = dict(os.environ)
    if parsed_arguments.is_astra_requested:
        setting_by_name[ASTRA_ENV_VAR] = "1"
    if parsed_arguments.astra_effort is not None:
        setting_by_name[ADVISOR_EFFORT_ENV_VAR] = parsed_arguments.astra_effort
    advisor_reply = run_codex_astra_advisor(
        prompt=sys.stdin.read(),
        working_directory=parsed_arguments.cwd,
        preflight=None,
        probe_path=None,
        setting_by_name=setting_by_name,
        session_id=parsed_arguments.resume if not parsed_arguments.bind else None,
        process_runner=subprocess.run,
    )
    reply_payload = asdict(advisor_reply)
    reply_payload[SPAWN_OUTCOME_KEY] = reply_payload.pop("outcome")
    print(json.dumps(reply_payload, sort_keys=True))
    return 0 if advisor_reply.successful else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
