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
from dataclasses import asdict
from pathlib import Path

_scripts_directory = Path(__file__).resolve().parent
_config_directory = _scripts_directory / "config"
sys.path[:0] = [
    each_import_directory_text
    for each_import_directory_text in map(str, (_scripts_directory, _config_directory))
    if each_import_directory_text not in sys.path
]

from advisor_scripts_constants.astra_advisor_constants import (
    ADVISOR_CODEX_EXECUTABLE_ENV_VAR,
    ALL_ASTRA_TRUTHY_VALUES,
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
)
from advisor_scripts_constants.advisor_route_constants import (
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
from codex_astra_models import AstraPreflight, CodexAstraAdvisorReply, _parse_codex_event


def _preflight_fallback(
    reason: str, percent_left: float | None, fallback_kind: str
) -> AstraPreflight:
    return AstraPreflight(False, percent_left, reason, fallback_kind)


def _reply_fallback(
    reason: str,
    is_astra_enabled: bool,
    fallback_kind: str | None = ASTRA_FALLBACK_KIND_BROKEN,
) -> CodexAstraAdvisorReply:
    return CodexAstraAdvisorReply(
        None,
        None,
        False,
        reason,
        True,
        None,
        is_astra_enabled,
        ADVISOR_FALLBACK_TIER,
        ADVISOR_FALLBACK_RESULT,
        fallback_kind,
    )


def _reply_success(
    session_id: str, guidance: str, signal: str
) -> CodexAstraAdvisorReply:
    return CodexAstraAdvisorReply(
        session_id,
        guidance,
        True,
        None,
        False,
        signal,
        True,
        ADVISOR_MODEL_TIER,
        CODEX_BIND_SUCCESS_TOKEN,
        None,
    )


def _resolved_settings(
    all_settings: Mapping[str, str] | None,
) -> Mapping[str, str]:
    return os.environ if all_settings is None else all_settings


def is_astra_advisor_enabled(all_settings: Mapping[str, str] | None) -> bool:
    raw_setting = _resolved_settings(all_settings).get(ASTRA_ENV_VAR, "")
    return raw_setting.strip().lower() in ALL_ASTRA_TRUTHY_VALUES


def resolve_advisor_effort(all_settings: Mapping[str, str] | None) -> str:
    requested = _resolved_settings(all_settings).get(ADVISOR_EFFORT_ENV_VAR, "")
    normalized = requested.strip().lower()
    return normalized if normalized in ALL_ADVISOR_EFFORT_LEVELS else ADVISOR_EFFORT_DEFAULT


def resolve_usage_probe_path(home_directory: Path) -> Path:
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
    return importlib.import_module("codex_usage_probe").is_codex_review_required


def _parse_probe_percent(stdout_text: str) -> tuple[float | None, str | None]:
    try:
        report = json.loads(stdout_text)
    except (TypeError, json.JSONDecodeError):
        return None, "usage report is malformed"
    if not isinstance(report, dict):
        return None, "usage report is malformed"
    raw_percent = report.get("percent_left")
    if isinstance(raw_percent, bool) or not isinstance(raw_percent, (int, float)):
        return None, "usage meter is unknown" if raw_percent is None else "usage meter is malformed"
    percent_left = float(raw_percent)
    if not math.isfinite(percent_left):
        return None, "usage meter is malformed"
    return percent_left, None


def _run_probe(
    probe_path: Path,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> subprocess.CompletedProcess[str]:
    return process_runner(
        [sys.executable, str(probe_path)],
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=ASTRA_USAGE_PROBE_TIMEOUT_SECONDS,
    )


def _preflight_from_probe(
    probe_path: Path, completed: subprocess.CompletedProcess[str]
) -> AstraPreflight:
    if completed.returncode != 0:
        reason = f"{ASTRA_PREFLIGHT_FAILURE_REASON}: probe exit {completed.returncode}"
        return _preflight_fallback(reason, None, ASTRA_FALLBACK_KIND_BROKEN)
    percent_left, parse_reason = _parse_probe_percent(completed.stdout)
    if parse_reason is not None or percent_left is None:
        reason = f"{ASTRA_PREFLIGHT_FAILURE_REASON}: {parse_reason or 'usage meter is unknown'}"
        return _preflight_fallback(reason, None, ASTRA_FALLBACK_KIND_BROKEN)
    if not _load_usage_gate(probe_path)(percent_left):
        reason = f"{ASTRA_PREFLIGHT_FAILURE_REASON}: usage meter is at or below the gate"
        return _preflight_fallback(reason, percent_left, ASTRA_FALLBACK_KIND_DECLINED)
    return AstraPreflight(True, percent_left, "usage meter is above the Astra gate")


def run_astra_preflight(
    probe_path: Path,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> AstraPreflight:
    try:
        completed = _run_probe(probe_path, process_runner)
        return _preflight_from_probe(probe_path, completed)
    except subprocess.TimeoutExpired as error:
        return _preflight_fallback(
            f"{ASTRA_PROBE_TIMEOUT_REASON}: {error}", None, ASTRA_FALLBACK_KIND_BROKEN
        )
    except (OSError, subprocess.SubprocessError, ImportError, AttributeError, TypeError, ValueError) as error:
        return _preflight_fallback(
            f"{ASTRA_PREFLIGHT_FAILURE_REASON}: {error}",
            None,
            ASTRA_FALLBACK_KIND_BROKEN,
        )


def resolve_codex_executable(all_settings: Mapping[str, str] | None) -> str | None:
    override = _resolved_settings(all_settings).get(ADVISOR_CODEX_EXECUTABLE_ENV_VAR, "").strip()
    return override or shutil.which(CODEX_EXECUTABLE)


def build_codex_arguments(
    codex_executable: str,
    session_id: str | None = None,
    reasoning_effort: str = ADVISOR_EFFORT_DEFAULT,
) -> list[str]:
    arguments = [
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
        arguments.extend([CODEX_RESUME_SUBCOMMAND, session_id])
    arguments.append(CODEX_PROMPT_FROM_STDIN)
    return arguments


def _guidance_signal(guidance: str) -> str | None:
    for each_line in guidance.splitlines():
        candidate = each_line.strip()
        if candidate:
            return candidate if candidate in ALL_ADVISOR_GUIDANCE_SIGNALS else None
    return None


def parse_codex_jsonl_reply(
    jsonl_text: str,
    existing_session_id: str | None,
    is_astra_enabled: bool,
    fallback_kind: str | None = None,
) -> CodexAstraAdvisorReply:
    session_id: str | None = None
    guidance: str | None = None
    try:
        for each_line in jsonl_text.splitlines():
            if not each_line.strip():
                continue
            discovered_session_id, discovered_guidance = _parse_codex_event(each_line)
            session_id = discovered_session_id or session_id
            guidance = discovered_guidance or guidance
    except (TypeError, json.JSONDecodeError):
        return _reply_fallback(ASTRA_MALFORMED_JSONL_REASON, is_astra_enabled, fallback_kind)
    if session_id is None or (existing_session_id is not None and session_id != existing_session_id):
        return _reply_fallback(ASTRA_MISSING_SESSION_REASON, is_astra_enabled, fallback_kind)
    if not guidance:
        return _reply_fallback(ASTRA_REPLY_FAILURE_REASON, is_astra_enabled, fallback_kind)
    signal = _guidance_signal(guidance)
    return _reply_success(session_id, guidance, signal) if signal else _reply_fallback(
        ASTRA_INVALID_SIGNAL_REASON, is_astra_enabled, fallback_kind
    )


def _resolve_preflight(
    preflight: AstraPreflight | None,
    probe_path: Path | None,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> AstraPreflight:
    if preflight is not None:
        return preflight
    resolved_path = resolve_usage_probe_path(Path.home()) if probe_path is None else probe_path
    return run_astra_preflight(resolved_path, process_runner)


def _run_codex(
    prompt: str,
    working_directory: Path,
    session_id: str | None,
    all_settings: Mapping[str, str] | None,
    executable: str,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> subprocess.CompletedProcess[str]:
    return process_runner(
        build_codex_arguments(
            executable,
            session_id=session_id,
            reasoning_effort=resolve_advisor_effort(all_settings),
        ),
        cwd=str(working_directory),
        input=prompt,
        capture_output=True,
        text=True,
        check=False,
        shell=False,
        timeout=ASTRA_CODEX_TIMEOUT_SECONDS,
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
    if not is_astra_advisor_enabled(setting_by_name):
        return _reply_fallback("Astra advisor flag is disabled", False, ASTRA_FALLBACK_KIND_DECLINED)
    executable = resolve_codex_executable(setting_by_name)
    if executable is None:
        return _reply_fallback(ASTRA_EXECUTABLE_NOT_FOUND_REASON, True)
    resolved_preflight = _resolve_preflight(preflight, probe_path, process_runner)
    if not resolved_preflight.eligible:
        return _reply_fallback(resolved_preflight.reason, True, resolved_preflight.fallback_kind)
    return _run_enabled_advisor(
        prompt,
        working_directory,
        session_id,
        setting_by_name,
        executable,
        process_runner,
    )


def _run_enabled_advisor(
    prompt: str,
    working_directory: Path,
    session_id: str | None,
    setting_by_name: Mapping[str, str] | None,
    executable: str,
    process_runner: Callable[..., subprocess.CompletedProcess[str]],
) -> CodexAstraAdvisorReply:
    try:
        completed = _run_codex(
            prompt, working_directory, session_id, setting_by_name, executable, process_runner
        )
    except subprocess.TimeoutExpired as error:
        return _reply_fallback(f"{ASTRA_CODEX_TIMEOUT_REASON}: {error}", True)
    except (OSError, subprocess.SubprocessError) as error:
        return _reply_fallback(f"{ASTRA_BIND_FAILURE_REASON}: {error}", True)
    if completed.returncode != 0:
        return _reply_fallback(f"{ASTRA_BIND_FAILURE_REASON}: process exit {completed.returncode}", True)
    return parse_codex_jsonl_reply(completed.stdout, session_id, True)


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Bind or consult a read-only Codex Astra advisor.")
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--bind", action="store_true")
    mode_group.add_argument("--resume", metavar=ASTRA_SESSION_ID_METAVAR)
    parser.add_argument("--cwd", required=True, type=Path)
    parser.add_argument(ASTRA_ENABLE_FLAG, dest="is_astra_requested", action="store_true")
    parser.add_argument(
        ASTRA_EFFORT_FLAG,
        dest="astra_effort",
        choices=ALL_ADVISOR_EFFORT_LEVELS,
        default=None,
    )
    return parser


def main(all_cli_arguments: Sequence[str]) -> int:
    parsed = build_argument_parser().parse_args(list(all_cli_arguments))
    all_settings = dict(os.environ)
    if parsed.is_astra_requested:
        all_settings[ASTRA_ENV_VAR] = "1"
    if parsed.astra_effort is not None:
        all_settings[ADVISOR_EFFORT_ENV_VAR] = parsed.astra_effort
    reply = run_codex_astra_advisor(
        sys.stdin.read(),
        parsed.cwd,
        None,
        None,
        all_settings,
        parsed.resume if not parsed.bind else None,
        subprocess.run,
    )
    payload = asdict(reply)
    payload[SPAWN_OUTCOME_KEY] = payload.pop("outcome")
    sys.stdout.write(f"{json.dumps(payload, sort_keys=True)}\n")
    return 0 if reply.successful else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
