"""Bind and consult a read-only Codex CLI session through Astra."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict
from pathlib import Path

_scripts_directory = Path(__file__).resolve().parent
_config_directory = _scripts_directory / "config"
sys.path[:0] = [str(_scripts_directory), str(_config_directory)]

from advisor_scripts_constants.advisor_route_constants import (
    ADVISOR_CODEX_MODEL_ID,
    ADVISOR_EFFORT_DEFAULT,
    ADVISOR_EFFORT_ENV_VAR,
    ALL_ADVISOR_EFFORT_LEVELS,
    SPAWN_OUTCOME_KEY,
)
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
    ASTRA_SESSION_ID_METAVAR,
    CODEX_CONFIG_FLAG,
    CODEX_EXEC_SUBCOMMAND,
    CODEX_EXECUTABLE,
    CODEX_JSON_FLAG,
    CODEX_MODEL_FLAG,
    CODEX_PROMPT_FROM_STDIN,
    CODEX_READ_ONLY_SANDBOX,
    CODEX_REASONING_CONFIG_TEMPLATE,
    CODEX_RESUME_SUBCOMMAND,
    CODEX_SANDBOX_FLAG,
)
from codex_astra_support import (
    AstraPreflight,
    CodexAstraAdvisorReply,
    parse_codex_jsonl_reply,
    reply_fallback,
    resolve_usage_probe_path,
    run_astra_preflight,
)


def _resolved_settings(
    all_settings: Mapping[str, str] | None,
) -> Mapping[str, str]:
    return os.environ if all_settings is None else all_settings


def is_astra_advisor_enabled(all_settings: Mapping[str, str] | None) -> bool:
    """Return whether the Astra advisor flag is enabled.

    Args:
        all_settings: Optional environment-like settings mapping.

    Returns:
        Whether the Astra feature flag contains a documented truthy value.
    """
    raw_setting = _resolved_settings(all_settings).get(ASTRA_ENV_VAR, "")
    return raw_setting.strip().lower() in ALL_ASTRA_TRUTHY_VALUES


def resolve_advisor_effort(all_settings: Mapping[str, str] | None) -> str:
    """Resolve the configured advisor effort.

    Args:
        all_settings: Optional environment-like settings mapping.

    Returns:
        A supported effort level, defaulting to low.
    """
    requested = _resolved_settings(all_settings).get(ADVISOR_EFFORT_ENV_VAR, "")
    normalized = requested.strip().lower()
    return normalized if normalized in ALL_ADVISOR_EFFORT_LEVELS else ADVISOR_EFFORT_DEFAULT


def resolve_codex_executable(all_settings: Mapping[str, str] | None) -> str | None:
    """Resolve the Codex executable override or PATH entry.

    Args:
        all_settings: Optional environment-like settings mapping.

    Returns:
        The executable path or name, or None when unavailable.
    """
    override = _resolved_settings(all_settings).get(ADVISOR_CODEX_EXECUTABLE_ENV_VAR, "").strip()
    return override or shutil.which(CODEX_EXECUTABLE)


def build_codex_arguments(
    codex_executable: str,
    session_id: str | None = None,
    reasoning_effort: str = ADVISOR_EFFORT_DEFAULT,
) -> list[str]:
    """Build the shell-free Codex argv for bind or resume.

    Args:
        codex_executable: Resolved Codex executable.
        session_id: Existing Codex session to resume, when present.
        reasoning_effort: Codex model reasoning effort.

    Returns:
        The command argument vector.
    """
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
    """Run one usage-gated Astra bind or resume attempt.

    Args:
        prompt: Advisor charter or consult text.
        working_directory: Repository working directory.
        preflight: Optional precomputed meter decision.
        probe_path: Optional usage-probe path.
        setting_by_name: Optional environment-like settings mapping.
        session_id: Existing session to resume.
        process_runner: Callable used to execute probe and Codex processes.

    Returns:
        A successful advisor reply or typed fallback.
    """
    if not is_astra_advisor_enabled(setting_by_name):
        return reply_fallback("Astra advisor flag is disabled", False, ASTRA_FALLBACK_KIND_DECLINED)
    executable = resolve_codex_executable(setting_by_name)
    if executable is None:
        return reply_fallback(
            ASTRA_EXECUTABLE_NOT_FOUND_REASON,
            True,
            ASTRA_FALLBACK_KIND_BROKEN,
        )
    resolved_preflight = _resolve_preflight(preflight, probe_path, process_runner)
    if not resolved_preflight.eligible:
        return reply_fallback(resolved_preflight.reason, True, resolved_preflight.fallback_kind)
    try:
        completed = _run_codex(
            prompt, working_directory, session_id, setting_by_name, executable, process_runner
        )
    except subprocess.TimeoutExpired as error:
        return reply_fallback(f"{ASTRA_CODEX_TIMEOUT_REASON}: {error}", True)
    except (OSError, subprocess.SubprocessError) as error:
        return reply_fallback(f"{ASTRA_BIND_FAILURE_REASON}: {error}", True)
    if completed.returncode != 0:
        return reply_fallback(f"{ASTRA_BIND_FAILURE_REASON}: process exit {completed.returncode}", True)
    return parse_codex_jsonl_reply(completed.stdout, session_id, True)


def build_argument_parser() -> argparse.ArgumentParser:
    """Build the Astra helper command-line parser.

    Returns:
        The configured parser.
    """
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
    """Run one bind or resume request from stdin.

    Args:
        all_cli_arguments: CLI arguments excluding the program name.

    Returns:
        Zero for a successful advisor reply and one for fallback.
    """
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
