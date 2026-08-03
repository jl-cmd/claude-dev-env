"""Bind and consult a read-only Codex CLI session at Sol xhigh."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

_scripts_directory = Path(__file__).resolve().parent
_config_directory = _scripts_directory / "config"
_config_directory_text = str(_config_directory)
_scripts_directory_text = str(_scripts_directory)
if _config_directory_text not in sys.path:
    sys.path.insert(0, _config_directory_text)
if _scripts_directory_text not in sys.path:
    sys.path.insert(0, _scripts_directory_text)

from advisor_scripts_constants.sol_advisor_constants import (  # noqa: E402
    CODEX_CONFIG_FLAG,
    CODEX_EXECUTABLE,
    CODEX_RESULT,
    CODEX_EXEC_SUBCOMMAND,
    CODEX_JSON_FLAG,
    CODEX_MODEL_FLAG,
    CODEX_PROMPT_FROM_STDIN,
    CODEX_READ_ONLY_SANDBOX,
    CODEX_REASONING_CONFIG,
    CODEX_RESUME_SUBCOMMAND,
    CODEX_SANDBOX_FLAG,
    CODEX_SOL_MODEL_ID,
    CLAUDE_CONFIG_DIRECTORY_NAME,
    FABLE_MODEL_TIER,
    FABLE_RESULT,
    SOL_BIND_FAILURE_REASON,
    SOL_CODEX_TIMEOUT_REASON,
    SOL_CODEX_TIMEOUT_SECONDS,
    SOL_ENV_VAR,
    ALL_SOL_GUIDANCE_SIGNALS,
    SOL_INVALID_SIGNAL_REASON,
    SOL_MALFORMED_JSONL_REASON,
    SOL_MISSING_SESSION_REASON,
    SOL_PREFLIGHT_FAILURE_REASON,
    SOL_PROBE_TIMEOUT_REASON,
    SOL_REPLY_FAILURE_REASON,
    SOL_SESSION_ID_METAVAR,
    SOL_MODEL_TIER,
    ALL_SOL_TRUTHY_VALUES,
    SOL_USAGE_PROBE_TIMEOUT_SECONDS,
)


@dataclass(frozen=True)
class SolPreflight:
    """Record the weekly-meter decision made before a Sol attempt."""

    eligible: bool
    percent_left: float | None
    reason: str
    is_fallback: bool
    probe_succeeded: bool


@dataclass(frozen=True)
class CodexSolAdvisorReply:
    """Record a parsed Codex advisor response or an explicit fallback."""

    session_id: str | None
    guidance: str | None
    successful: bool
    reason: str | None
    is_fallback: bool
    signal: str | None
    sol_enabled: bool
    selected_tier: str
    outcome: str


def _preflight_fallback(
    reason: str, percent_left: float | None
) -> SolPreflight:
    return SolPreflight(False, percent_left, reason, True, False)


def _reply_fallback(
    reason: str,
    is_sol_enabled: bool,
) -> CodexSolAdvisorReply:
    return CodexSolAdvisorReply(
        session_id=None,
        guidance=None,
        successful=False,
        reason=reason,
        is_fallback=True,
        signal=None,
        sol_enabled=is_sol_enabled,
        selected_tier=FABLE_MODEL_TIER,
        outcome=FABLE_RESULT,
    )


def _reply_success(
    session_id: str,
    guidance: str,
    signal: str,
) -> CodexSolAdvisorReply:
    return CodexSolAdvisorReply(
        session_id=session_id,
        guidance=guidance,
        successful=True,
        reason=None,
        is_fallback=False,
        signal=signal,
        sol_enabled=True,
        selected_tier=SOL_MODEL_TIER,
        outcome=CODEX_RESULT,
    )


def is_sol_advisor_enabled(
    setting_by_name: Mapping[str, str] | None,
) -> bool:
    """Return whether the optional Sol xhigh rung is enabled.

    Args:
        setting_by_name: Optional environment-like settings mapping.

    Returns:
        Whether the Sol feature flag contains a recognized truthy value.
    """
    resolved_setting_by_name = os.environ if setting_by_name is None else setting_by_name
    return (
        resolved_setting_by_name.get(SOL_ENV_VAR, "").strip().lower()
        in ALL_SOL_TRUTHY_VALUES
    )


def resolve_usage_probe_path(home_directory: Path) -> Path:
    """Return the installed Codex weekly usage probe path.

    Args:
        home_directory: Home directory used to construct the path.

    Returns:
        The path to the installed weekly usage probe.
    """
    resolved_home_directory = Path.home() if home_directory is None else home_directory
    return (
        resolved_home_directory
        / CLAUDE_CONFIG_DIRECTORY_NAME
        / "skills"
        / "codex-review"
        / "scripts"
        / "codex_usage_probe.py"
    )


def _load_usage_gate(probe_path: Path) -> object:
    probe_directory = str(probe_path.parent)
    if probe_directory not in sys.path:
        sys.path.insert(0, probe_directory)
    usage_probe_module = importlib.import_module("codex_usage_probe")
    return getattr(usage_probe_module, "is_codex_review_required", None)


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


def run_sol_preflight(
    probe_path: Path,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> SolPreflight:
    """Run the existing usage probe and require a finite meter above its gate.

    Args:
        probe_path: Path to the installed usage probe.
        process_runner: Callable used to execute the probe.

    Returns:
        The usage-meter eligibility decision and any fallback reason.
    """
    resolved_probe_path = probe_path
    try:
        completed_process = process_runner(
            [sys.executable, str(resolved_probe_path)],
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=SOL_USAGE_PROBE_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as probe_error:
        return _preflight_fallback(f"{SOL_PROBE_TIMEOUT_REASON}: {probe_error}", None)
    except (OSError, subprocess.SubprocessError) as probe_error:
        return _preflight_fallback(
            f"{SOL_PREFLIGHT_FAILURE_REASON}: {probe_error}", None
        )
    if completed_process.returncode != 0:
        return _preflight_fallback(
            f"{SOL_PREFLIGHT_FAILURE_REASON}: probe exit {completed_process.returncode}",
            None,
        )
    try:
        percent_left, parse_reason = _parse_probe_percent(completed_process.stdout)
        if parse_reason is not None:
            return _preflight_fallback(
                f"{SOL_PREFLIGHT_FAILURE_REASON}: {parse_reason}", None
            )
        usage_gate = _load_usage_gate(resolved_probe_path)
        if not callable(usage_gate) or percent_left is None:
            return _preflight_fallback(
                f"{SOL_PREFLIGHT_FAILURE_REASON}: usage meter is unknown", None
            )
        if not usage_gate(percent_left):
            return _preflight_fallback(
                f"{SOL_PREFLIGHT_FAILURE_REASON}: usage meter is at or below the gate",
                percent_left,
            )
    except (ImportError, OSError, TypeError, ValueError) as parse_error:
        return _preflight_fallback(
            f"{SOL_PREFLIGHT_FAILURE_REASON}: {parse_error}", None
        )
    return SolPreflight(
        True,
        percent_left,
        "usage meter is above the Sol gate",
        False,
        True,
    )


def build_codex_arguments(session_id: str | None = None) -> list[str]:
    """Build the installed CLI's shell-free bind or resume argv.

    Args:
        session_id: Optional existing session to resume.

    Returns:
        The shell-free Codex command argument vector.
    """
    command_arguments = [
        CODEX_EXECUTABLE,
        CODEX_EXEC_SUBCOMMAND,
        CODEX_MODEL_FLAG,
        CODEX_SOL_MODEL_ID,
        CODEX_CONFIG_FLAG,
        CODEX_REASONING_CONFIG,
        CODEX_SANDBOX_FLAG,
        CODEX_READ_ONLY_SANDBOX,
        CODEX_JSON_FLAG,
    ]
    if session_id is not None:
        command_arguments.extend([CODEX_RESUME_SUBCOMMAND, session_id])
    command_arguments.append(CODEX_PROMPT_FROM_STDIN)
    return command_arguments


def _guidance_signal(guidance: str) -> str | None:
    all_guidance_lines = [
        each_line.strip()
        for each_line in guidance.splitlines()
        if each_line.strip()
    ]
    if not all_guidance_lines or all_guidance_lines[0] not in ALL_SOL_GUIDANCE_SIGNALS:
        return None
    return all_guidance_lines[0]


def parse_codex_jsonl_reply(
    jsonl_text: str,
    existing_session_id: str | None,
    is_sol_enabled: bool,
) -> CodexSolAdvisorReply:
    """Parse strict Codex JSONL into a session id and final guidance.

    Args:
        jsonl_text: JSONL emitted by the Codex CLI.
        existing_session_id: Optional session id required on resume.
        is_sol_enabled: Whether the attempted route had Sol enabled.

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
                return _reply_fallback(SOL_MALFORMED_JSONL_REASON, is_sol_enabled)
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
        return _reply_fallback(SOL_MALFORMED_JSONL_REASON, is_sol_enabled)
    if discovered_session_id is None:
        return _reply_fallback(SOL_MISSING_SESSION_REASON, is_sol_enabled)
    if (
        existing_session_id is not None
        and discovered_session_id != existing_session_id
    ):
        return _reply_fallback(SOL_MISSING_SESSION_REASON, is_sol_enabled)
    if final_guidance is None or not final_guidance:
        return _reply_fallback(SOL_REPLY_FAILURE_REASON, is_sol_enabled)
    guidance_signal = _guidance_signal(final_guidance)
    if guidance_signal is None:
        return _reply_fallback(SOL_INVALID_SIGNAL_REASON, is_sol_enabled)
    return _reply_success(discovered_session_id, final_guidance, guidance_signal)


def run_codex_sol_advisor(
    prompt: str,
    working_directory: Path,
    preflight: SolPreflight | None,
    probe_path: Path | None,
    setting_by_name: Mapping[str, str] | None,
    session_id: str | None,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> CodexSolAdvisorReply:
    """Run one usage-gated read-only Sol bind or resume attempt.

    Args:
        prompt: Advisor charter or delta consult sent to Codex.
        working_directory: Repository directory supplied to the CLI.
        preflight: Optional precomputed usage-meter decision.
        probe_path: Optional installed usage-probe path.
        setting_by_name: Optional environment-like settings mapping.
        session_id: Existing session id for a resume attempt.
        process_runner: Callable used to execute the probe and Codex.

    Returns:
        The parsed Sol guidance or an explicit Fable fallback reply.
    """
    is_sol_enabled = is_sol_advisor_enabled(setting_by_name)
    if not is_sol_enabled:
        return _reply_fallback("Sol advisor flag is disabled", False)
    resolved_preflight = (
        run_sol_preflight(
            probe_path=(
                resolve_usage_probe_path(Path.home())
                if probe_path is None
                else probe_path
            ),
            process_runner=process_runner,
        )
        if preflight is None
        else preflight
    )
    if not resolved_preflight.eligible or not resolved_preflight.probe_succeeded:
        return _reply_fallback(resolved_preflight.reason, is_sol_enabled)
    try:
        completed_process = process_runner(
            build_codex_arguments(session_id=session_id),
            cwd=str(working_directory),
            input=prompt,
            capture_output=True,
            text=True,
            check=False,
            shell=False,
            timeout=SOL_CODEX_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as bind_error:
        return _reply_fallback(
            f"{SOL_CODEX_TIMEOUT_REASON}: {bind_error}", is_sol_enabled
        )
    except (OSError, subprocess.SubprocessError) as bind_error:
        return _reply_fallback(
            f"{SOL_BIND_FAILURE_REASON}: {bind_error}", is_sol_enabled
        )
    if completed_process.returncode != 0:
        return _reply_fallback(
            f"{SOL_BIND_FAILURE_REASON}: process exit {completed_process.returncode}",
            is_sol_enabled,
        )
    return parse_codex_jsonl_reply(
        completed_process.stdout,
        existing_session_id=session_id,
        is_sol_enabled=is_sol_enabled,
    )


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for Sol bind and resume.

    Returns:
        The parser for the helper's bind and resume modes.
    """
    argument_parser = argparse.ArgumentParser(
        description="Bind or consult a read-only Codex Sol xhigh advisor."
    )
    mode_group = argument_parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--bind", action="store_true")
    mode_group.add_argument("--resume", metavar=SOL_SESSION_ID_METAVAR)
    argument_parser.add_argument("--cwd", required=True, type=Path)
    return argument_parser


def main(all_cli_arguments: Sequence[str]) -> int:
    """Run one bind or resume from stdin and print a JSON response.

    Args:
        all_cli_arguments: Command-line arguments without the program name.

    Returns:
        Zero for a successful Sol response, or one for an explicit fallback.
    """
    parsed_arguments = build_argument_parser().parse_args(list(all_cli_arguments))
    advisor_reply = run_codex_sol_advisor(
        prompt=sys.stdin.read(),
        working_directory=parsed_arguments.cwd,
        preflight=None,
        probe_path=None,
        setting_by_name=os.environ,
        session_id=parsed_arguments.resume if not parsed_arguments.bind else None,
        process_runner=subprocess.run,
    )
    reply_payload = asdict(advisor_reply)
    reply_payload["result"] = reply_payload.pop("outcome")
    print(json.dumps(reply_payload, sort_keys=True))
    return 0 if advisor_reply.successful else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
