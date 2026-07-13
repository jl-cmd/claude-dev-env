#!/usr/bin/env python3
"""Static soft gate for whether tier 1 (grok headless) is usable.

Callers continue down their fallback chain on a non-zero exit. A non-zero exit
is never a run failure for the caller — it is only a fallthrough signal.

Checks run in order and stop at the first failure:

1. The ``grok`` binary is resolvable on PATH.
2. Auth material is present: ``grok models`` exits 0. The probe uses its own
   ``--leader-socket`` path so it never contends with running workers.
3. ``claude-dev-env`` is installed for the requested role: the install manifest
   exists in the user Claude config directory, and every agent definition file
   that role needs is present under ``agents/``.

Opt-in ``--ping`` runs one cached live single-turn call with a run-scoped TTL.
The cache file lives under the caller-supplied run state directory. Auth failure
invalidates any cached ping. Usage exhaustion is reported under a distinct
reason from auth failure.

Stdout is one machine-readable line::

    grok_preflight: ok
    grok_preflight: fallthrough reason=<reason>

Import ``run_preflight`` for the outcome object, or run the module as a CLI::

    python grok_worker_preflight.py [--role bugteam] [--ping]
        --run-temp-dir <dir>
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from dev_env_scripts_constants.grok_worker_constants import (
    AGENTS_SUBDIRECTORY,
    ALL_AGENT_FILENAMES_BY_ROLE,
    ALL_AUTH_FAILURE_SIGNATURES,
    ALL_USAGE_EXHAUSTION_SIGNATURES,
    AUTH_LEADER_SOCKET_FILENAME,
    CLAUDE_HOME_SUBDIRECTORY,
    CLI_PING_FLAG,
    CLI_ROLE_FLAG,
    CLI_RUN_STATE_DIR_FLAG,
    DEFAULT_AUTH_TIMEOUT_SECONDS,
    DEFAULT_PING_TIMEOUT_SECONDS,
    DEFAULT_ROLE,
    EXIT_FALLTHROUGH,
    EXIT_USABLE,
    GROK_BINARY_NAME,
    LEADER_SOCKET_FLAG,
    MANIFEST_FILENAME,
    MAX_TURNS_FLAG,
    MODELS_SUBCOMMAND,
    PING_CACHE_CHECKED_AT_KEY,
    PING_CACHE_FILENAME,
    PING_CACHE_IS_OK_KEY,
    PING_LEADER_SOCKET_FILENAME,
    PING_MAX_TURNS,
    PING_PROMPT,
    PING_TTL_SECONDS,
    REASON_CLAUDE_DEV_ENV_CONFIG_MISSING,
    REASON_GROK_AUTH_FAILED,
    REASON_GROK_BINARY_MISSING,
    REASON_GROK_USAGE_EXHAUSTED,
    SINGLE_TURN_FLAG,
    STDOUT_FALLTHROUGH_TEMPLATE,
    STDOUT_OK_LINE,
    UTF8_ENCODING,
)

preflight_which = shutil.which
preflight_subprocess_runner = subprocess.run
preflight_time = time.time


@dataclass(frozen=True)
class PreflightOutcome:
    """Outcome of one soft-gate evaluation.

    ``reason`` is ``None`` when tier 1 is usable. Otherwise it is one of the
    fallthrough reason constants from ``grok_worker_constants``.
    """

    is_usable: bool
    reason: str | None


def claude_config_home() -> Path:
    """Return the per-user Claude configuration directory."""
    return Path.home() / CLAUDE_HOME_SUBDIRECTORY


def _install_manifest_path() -> Path:
    return claude_config_home() / MANIFEST_FILENAME


def _agents_directory() -> Path:
    return claude_config_home() / AGENTS_SUBDIRECTORY


def _ping_cache_path(run_state_directory: Path) -> Path:
    return run_state_directory / PING_CACHE_FILENAME


def _fallthrough(reason: str) -> PreflightOutcome:
    return PreflightOutcome(is_usable=False, reason=reason)


def _usable() -> PreflightOutcome:
    return PreflightOutcome(is_usable=True, reason=None)


def _combined_completion_text(completion: subprocess.CompletedProcess[str]) -> str:
    return f"{completion.stdout}{completion.stderr}".lower()


def _matches_any_signature(
    completion: subprocess.CompletedProcess[str], all_signatures: tuple[str, ...]
) -> bool:
    combined_text = _combined_completion_text(completion)
    return any(
        each_signature in combined_text for each_signature in all_signatures
    )


def _is_usage_exhaustion(completion: subprocess.CompletedProcess[str]) -> bool:
    return _matches_any_signature(completion, ALL_USAGE_EXHAUSTION_SIGNATURES)


def _is_auth_failure_text(completion: subprocess.CompletedProcess[str]) -> bool:
    return _matches_any_signature(completion, ALL_AUTH_FAILURE_SIGNATURES)


def _invalidate_ping_cache(run_state_directory: Path) -> None:
    cache_file = _ping_cache_path(run_state_directory)
    cache_file.unlink(missing_ok=True)


def _read_ping_cache(run_state_directory: Path) -> dict[str, object] | None:
    cache_file = _ping_cache_path(run_state_directory)
    if not cache_file.is_file():
        return None
    try:
        parsed_payload = json.loads(cache_file.read_text(encoding=UTF8_ENCODING))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(parsed_payload, dict):
        return None
    return parsed_payload


def _is_ping_cache_fresh(all_cache_payload: dict[str, object], now_timestamp: float) -> bool:
    checked_at = all_cache_payload.get(PING_CACHE_CHECKED_AT_KEY)
    is_ok = all_cache_payload.get(PING_CACHE_IS_OK_KEY)
    if not isinstance(checked_at, (int, float)):
        return False
    if is_ok is not True:
        return False
    age_seconds = now_timestamp - float(checked_at)
    return age_seconds >= 0 and age_seconds <= PING_TTL_SECONDS


def _write_successful_ping_cache(
    run_state_directory: Path, checked_at: float
) -> None:
    all_cache_payload = {
        PING_CACHE_CHECKED_AT_KEY: checked_at,
        PING_CACHE_IS_OK_KEY: True,
    }
    _ping_cache_path(run_state_directory).write_text(
        json.dumps(all_cache_payload), encoding=UTF8_ENCODING
    )


def _is_grok_binary_resolvable() -> bool:
    return preflight_which(GROK_BINARY_NAME) is not None


def _is_claude_dev_env_config_present(role: str) -> bool:
    if not _install_manifest_path().is_file():
        return False
    all_agent_filenames = ALL_AGENT_FILENAMES_BY_ROLE.get(role)
    if all_agent_filenames is None:
        return False
    agents_root = _agents_directory()
    return all(
        (agents_root / each_filename).is_file()
        for each_filename in all_agent_filenames
    )


def _build_models_invocation(leader_socket_path: Path) -> list[str]:
    return [
        GROK_BINARY_NAME,
        MODELS_SUBCOMMAND,
        LEADER_SOCKET_FLAG,
        str(leader_socket_path),
    ]


def _build_ping_invocation(leader_socket_path: Path) -> list[str]:
    return [
        GROK_BINARY_NAME,
        SINGLE_TURN_FLAG,
        PING_PROMPT,
        MAX_TURNS_FLAG,
        PING_MAX_TURNS,
        LEADER_SOCKET_FLAG,
        str(leader_socket_path),
    ]


def _run_grok_command(
    all_arguments: list[str], *, timeout_seconds: int
) -> subprocess.CompletedProcess[str] | None:
    try:
        return preflight_subprocess_runner(
            all_arguments,
            capture_output=True,
            text=True,
            encoding=UTF8_ENCODING,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=all_arguments,
            returncode=EXIT_FALLTHROUGH,
            stdout="",
            stderr="",
        )


def _probe_grok_auth(run_state_directory: Path) -> PreflightOutcome:
    leader_socket_path = run_state_directory / AUTH_LEADER_SOCKET_FILENAME
    completion = _run_grok_command(
        _build_models_invocation(leader_socket_path),
        timeout_seconds=DEFAULT_AUTH_TIMEOUT_SECONDS,
    )
    if completion is None or completion.returncode != 0:
        _invalidate_ping_cache(run_state_directory)
        return _fallthrough(REASON_GROK_AUTH_FAILED)
    return _usable()


def _classify_failed_ping(
    completion: subprocess.CompletedProcess[str],
    run_state_directory: Path,
) -> PreflightOutcome:
    if _is_usage_exhaustion(completion) and not _is_auth_failure_text(completion):
        return _fallthrough(REASON_GROK_USAGE_EXHAUSTED)
    _invalidate_ping_cache(run_state_directory)
    return _fallthrough(REASON_GROK_AUTH_FAILED)


def _probe_grok_ping(run_state_directory: Path) -> PreflightOutcome:
    now_timestamp = preflight_time()
    all_cache_payload = _read_ping_cache(run_state_directory)
    if all_cache_payload is not None and _is_ping_cache_fresh(all_cache_payload, now_timestamp):
        return _usable()
    leader_socket_path = run_state_directory / PING_LEADER_SOCKET_FILENAME
    completion = _run_grok_command(
        _build_ping_invocation(leader_socket_path),
        timeout_seconds=DEFAULT_PING_TIMEOUT_SECONDS,
    )
    if completion is None:
        _invalidate_ping_cache(run_state_directory)
        return _fallthrough(REASON_GROK_AUTH_FAILED)
    if completion.returncode != 0:
        return _classify_failed_ping(completion, run_state_directory)
    _write_successful_ping_cache(run_state_directory, now_timestamp)
    return _usable()


def run_preflight(
    *,
    role: str,
    should_ping: bool,
    run_state_directory: Path,
) -> PreflightOutcome:
    """Evaluate whether tier 1 (grok headless) is usable.

    Args:
        role: Role whose agent definition set must be installed.
        should_ping: When True, run the opt-in cached live single-turn ping.
        run_state_directory: Run-scoped directory for leader sockets and cache.

    Returns:
        The soft-gate outcome. Callers treat a non-usable outcome as fallthrough,
        not as a hard run failure.
    """
    if not _is_grok_binary_resolvable():
        return _fallthrough(REASON_GROK_BINARY_MISSING)
    auth_outcome = _probe_grok_auth(run_state_directory)
    if not auth_outcome.is_usable:
        return auth_outcome
    if not _is_claude_dev_env_config_present(role):
        return _fallthrough(REASON_CLAUDE_DEV_ENV_CONFIG_MISSING)
    if should_ping:
        return _probe_grok_ping(run_state_directory)
    return _usable()


def _format_stdout_line(outcome: PreflightOutcome) -> str:
    if outcome.is_usable:
        return STDOUT_OK_LINE
    return STDOUT_FALLTHROUGH_TEMPLATE.format(reason=outcome.reason)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Soft gate that decides whether tier 1 (grok headless) is usable."
        )
    )
    parser.add_argument(
        CLI_ROLE_FLAG,
        default=DEFAULT_ROLE,
        help="Role whose agent definition files must be present.",
    )
    parser.add_argument(
        CLI_PING_FLAG,
        action="store_true",
        default=False,
        help="Run one cached live single-turn ping after the static checks.",
    )
    parser.add_argument(
        CLI_RUN_STATE_DIR_FLAG,
        dest="run_state_directory",
        required=True,
        type=Path,
        help="Run-scoped state directory for leader sockets and the ping cache.",
    )
    return parser


def main(all_command_arguments: list[str]) -> int:
    """Run the soft gate for CLI arguments and return the process exit code.

    Args:
        all_command_arguments: The argument vector after the program name.

    Returns:
        ``0`` when tier 1 is usable; non-zero when callers should fall through.
    """
    parser = _build_argument_parser()
    parsed_arguments = parser.parse_args(all_command_arguments)
    run_state_directory = parsed_arguments.run_state_directory
    run_state_directory.mkdir(parents=True, exist_ok=True)
    outcome = run_preflight(
        role=parsed_arguments.role,
        should_ping=parsed_arguments.ping,
        run_state_directory=run_state_directory,
    )
    print(_format_stdout_line(outcome))
    if outcome.is_usable:
        return EXIT_USABLE
    return EXIT_FALLTHROUGH


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
