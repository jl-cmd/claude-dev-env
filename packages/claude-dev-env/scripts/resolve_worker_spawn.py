#!/usr/bin/env python3
"""Dispatch a worker role through the grok then claude fallback tiers.

Walk order:

1. Soft-gate preflight for tier 1 (grok headless).
2. Tier 1 via ``grok_headless_runner.run_headless_worker``.
3. On fall-through, ``detect_host_profile()`` decides the next step.
   On a Claude host with the claude tier disabled, stop with
   ``claude_agent_required`` so the calling skill runs the Agent tool.
   On a third-party host, or when the claude tier is enabled, tier 3 runs
   ``claude_chain_runner.run_claude`` with ``-p --output-format json --agent
   <stem>``, prompt body on stdin from the prompt file, and subprocess
   ``cwd`` set to the caller's working directory.

Import ``resolve_worker_spawn`` for the outcome object, or run as a CLI::

    python resolve_worker_spawn.py --role <role> --prompt-file <path>
        --cwd <dir> --timeout-seconds N --run-temp-dir <dir>
        [--enable-claude-tier]
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import IO

if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

_advisor_scripts_path = str(
    Path(__file__).resolve().parent.parent / "_shared" / "advisor" / "scripts"
)
if _advisor_scripts_path not in sys.path:
    sys.path.insert(0, _advisor_scripts_path)

from advisor_scripts_constants.model_tier_run_validator_constants import (  # noqa: E402
    HOST_PROFILE_CLAUDE,
)
import claude_chain_runner as chain_runner  # noqa: E402
from claude_chain_runner import (  # noqa: E402
    ChainConfigurationError,
    ChainInvocationOutcome,
    run_claude,
)
from dev_env_scripts_constants.grok_worker_constants import (  # noqa: E402
    AGENT_FLAG,
    ALL_AGENT_FILENAMES_BY_ROLE,
    ATTEMPT_KEY_OK,
    ATTEMPT_KEY_REASON,
    ATTEMPT_KEY_TIER,
    CLI_ENABLE_CLAUDE_TIER_FLAG,
    CLI_ROLE_FLAG,
    CLI_RUN_STATE_DIR_FLAG,
    CLI_TIMEOUT_FLAG,
    CWD_FLAG,
    DEFAULT_ROLE,
    DEFAULT_SPAWN_MAX_TURNS,
    DEFAULT_WORKER_TIMEOUT_SECONDS,
    EMPTY_OUTPUT,
    OUTPUT_FORMAT_FLAG,
    OUTPUT_FORMAT_JSON,
    PROMPT_FILE_FLAG,
    REASON_CLAUDE_AGENT_REQUIRED,
    REASON_PROMPT_FILE_MISSING,
    RESULT_KEY_ATTEMPTS,
    RESULT_KEY_OK,
    RESULT_KEY_OUTPUT,
    RESULT_KEY_RETURNCODE,
    RESULT_KEY_TIER_USED,
    SINGLE_TURN_FLAG,
    SPAWN_CONFIG_ERROR_EXIT_CODE,
    SPAWN_EXHAUSTED_EXIT_CODE,
    SPAWN_SERVED_EXIT_CODE,
    TIER_CLAUDE_AGENT,
    TIER_CLAUDE_HEADLESS,
    TIER_GROK,
    UTF8_ENCODING,
)
from grok_headless_runner import GrokRunnerOutcome, run_headless_worker  # noqa: E402
from grok_worker_preflight import PreflightOutcome, run_preflight  # noqa: E402
from tier_model_ids import detect_host_profile  # noqa: E402

_HEADLESS_CHAIN_RUNNER_LOCK = threading.Lock()


def _headless_chain_runner_lock() -> threading.Lock:
    """Return the module lock that serializes headless chain-runner swaps."""
    return _HEADLESS_CHAIN_RUNNER_LOCK


@dataclass(frozen=True)
class SpawnAttempt:
    """One tier try recorded in the dispatcher attempts trail."""

    tier: int
    is_ok: bool
    reason: str | None


@dataclass(frozen=True)
class SpawnOutcome:
    """Outcome of walking the worker-spawn tier chain.

    ``tier_used`` is the tier number that served the call, or ``None`` when no
    tier served. ``all_attempts`` lists every tier tried in order.
    ``captured_stdout`` holds the serving tier's stdout (or empty).
    ``is_config_error`` is True when the walk stopped on a configuration fault
    such as a missing or unreadable prompt file.
    """

    tier_used: int | None
    is_ok: bool
    all_attempts: tuple[SpawnAttempt, ...]
    captured_stdout: str
    returncode: int
    is_config_error: bool = False


spawn_preflight_runner = run_preflight
spawn_grok_runner = run_headless_worker
spawn_claude_runner = run_claude
spawn_host_profile_detector = detect_host_profile


TextCapturingSubprocessRunner = Callable[
    ...,
    subprocess.CompletedProcess[str],
]


def _attempt(tier: int, *, is_ok: bool, reason: str | None) -> SpawnAttempt:
    return SpawnAttempt(tier=tier, is_ok=is_ok, reason=reason)


def _primary_agent_name_for_role(role: str) -> str:
    all_agent_filenames = ALL_AGENT_FILENAMES_BY_ROLE.get(role)
    if all_agent_filenames is None:
        return role
    if not all_agent_filenames:
        return role
    return Path(all_agent_filenames[0]).stem


def _build_claude_arguments(*, agent_name: str) -> list[str]:
    return [
        SINGLE_TURN_FLAG,
        OUTPUT_FORMAT_FLAG,
        OUTPUT_FORMAT_JSON,
        AGENT_FLAG,
        agent_name,
    ]


def _timeout_seconds_from_keywords(
    all_keywords: dict[str, object],
) -> float | None:
    maybe_timeout = all_keywords.get("timeout")
    if isinstance(maybe_timeout, (int, float)):
        return float(maybe_timeout)
    return None


def _run_claude_with_headless_overrides(
    all_claude_arguments: list[str],
    *,
    timeout_seconds: int,
    working_directory: Path,
    prompt_stdin: IO[str],
) -> ChainInvocationOutcome:
    working_directory_path = str(working_directory)
    with _HEADLESS_CHAIN_RUNNER_LOCK:
        previous_runner = chain_runner.chain_subprocess_runner

        def _runner_with_headless_overrides(
            all_invocation_tokens: Sequence[str],
            *all_positionals: object,
            **all_keywords: object,
        ) -> subprocess.CompletedProcess[str]:
            del all_positionals
            prompt_stdin.seek(0)
            completed_process: subprocess.CompletedProcess[str] = previous_runner(
                all_invocation_tokens,
                capture_output=True,
                text=True,
                timeout=_timeout_seconds_from_keywords(all_keywords),
                check=False,
                stdin=prompt_stdin,
                cwd=working_directory_path,
            )
            return completed_process

        headless_runner: TextCapturingSubprocessRunner = (
            _runner_with_headless_overrides
        )
        setattr(chain_runner, "chain_subprocess_runner", headless_runner)
        try:
            return spawn_claude_runner(
                all_claude_arguments, timeout_seconds=timeout_seconds
            )
        finally:
            setattr(chain_runner, "chain_subprocess_runner", previous_runner)


def _prompt_file_unreadable_outcome(
    all_attempts: list[SpawnAttempt],
) -> SpawnOutcome:
    all_attempts.append(
        _attempt(
            TIER_CLAUDE_HEADLESS,
            is_ok=False,
            reason=REASON_PROMPT_FILE_MISSING,
        )
    )
    return SpawnOutcome(
        tier_used=None,
        is_ok=False,
        all_attempts=tuple(all_attempts),
        captured_stdout=REASON_PROMPT_FILE_MISSING,
        returncode=SPAWN_CONFIG_ERROR_EXIT_CODE,
        is_config_error=True,
    )


def _claude_agent_required_outcome(
    all_attempts: list[SpawnAttempt], *, returncode: int
) -> SpawnOutcome:
    all_attempts.append(
        _attempt(
            TIER_CLAUDE_AGENT,
            is_ok=False,
            reason=REASON_CLAUDE_AGENT_REQUIRED,
        )
    )
    return SpawnOutcome(
        tier_used=None,
        is_ok=False,
        all_attempts=tuple(all_attempts),
        captured_stdout=EMPTY_OUTPUT,
        returncode=returncode,
    )


def _served_claude_outcome(
    all_attempts: list[SpawnAttempt],
    chain_outcome: ChainInvocationOutcome,
) -> SpawnOutcome:
    is_served = chain_outcome.served_command is not None
    is_ok = is_served and chain_outcome.returncode == SPAWN_SERVED_EXIT_CODE
    all_attempts.append(_attempt(TIER_CLAUDE_HEADLESS, is_ok=is_ok, reason=None))
    if not is_served:
        return SpawnOutcome(
            tier_used=None,
            is_ok=False,
            all_attempts=tuple(all_attempts),
            captured_stdout=chain_outcome.stdout,
            returncode=chain_outcome.returncode,
        )
    return SpawnOutcome(
        tier_used=TIER_CLAUDE_HEADLESS,
        is_ok=is_ok,
        all_attempts=tuple(all_attempts),
        captured_stdout=chain_outcome.stdout,
        returncode=chain_outcome.returncode,
    )


def _run_tier_claude_headless(
    *,
    role: str,
    prompt_file: Path,
    working_directory: Path,
    timeout_seconds: int,
    all_attempts: list[SpawnAttempt],
) -> SpawnOutcome:
    agent_name = _primary_agent_name_for_role(role)
    all_claude_arguments = _build_claude_arguments(agent_name=agent_name)
    try:
        prompt_stdin = prompt_file.open(encoding=UTF8_ENCODING)
    except OSError:
        return _prompt_file_unreadable_outcome(all_attempts)
    try:
        chain_outcome = _run_claude_with_headless_overrides(
            all_claude_arguments,
            timeout_seconds=timeout_seconds,
            working_directory=working_directory,
            prompt_stdin=prompt_stdin,
        )
    finally:
        prompt_stdin.close()
    return _served_claude_outcome(all_attempts, chain_outcome)


def _after_grok_fallthrough(
    *,
    role: str,
    prompt_file: Path,
    working_directory: Path,
    timeout_seconds: int,
    is_claude_tier_enabled: bool,
    all_attempts: list[SpawnAttempt],
    fallthrough_returncode: int,
) -> SpawnOutcome:
    host_profile = spawn_host_profile_detector()
    is_claude_host = host_profile == HOST_PROFILE_CLAUDE
    if is_claude_host and not is_claude_tier_enabled:
        return _claude_agent_required_outcome(
            all_attempts, returncode=fallthrough_returncode
        )
    return _run_tier_claude_headless(
        role=role,
        prompt_file=prompt_file,
        working_directory=working_directory,
        timeout_seconds=timeout_seconds,
        all_attempts=all_attempts,
    )


def _run_tier_grok(
    *,
    role: str,
    prompt_file: Path,
    working_directory: Path,
    run_state_directory: Path,
    max_turns: int,
    timeout_seconds: int,
) -> GrokRunnerOutcome:
    agent_name = _primary_agent_name_for_role(role)
    return spawn_grok_runner(
        prompt_file=prompt_file,
        working_directory=working_directory,
        run_state_directory=run_state_directory,
        max_turns=max_turns,
        timeout_seconds=timeout_seconds,
        agent_name=agent_name,
    )


def _record_preflight_fallthrough(
    preflight_outcome: PreflightOutcome,
    *,
    role: str,
    prompt_file: Path,
    working_directory: Path,
    timeout_seconds: int,
    is_claude_tier_enabled: bool,
) -> SpawnOutcome:
    all_attempts = [_attempt(TIER_GROK, is_ok=False, reason=preflight_outcome.reason)]
    return _after_grok_fallthrough(
        role=role,
        prompt_file=prompt_file,
        working_directory=working_directory,
        timeout_seconds=timeout_seconds,
        is_claude_tier_enabled=is_claude_tier_enabled,
        all_attempts=all_attempts,
        fallthrough_returncode=SPAWN_EXHAUSTED_EXIT_CODE,
    )


def _record_grok_success(
    grok_outcome: GrokRunnerOutcome,
) -> SpawnOutcome:
    return SpawnOutcome(
        tier_used=TIER_GROK,
        is_ok=True,
        all_attempts=(_attempt(TIER_GROK, is_ok=True, reason=None),),
        captured_stdout=grok_outcome.stdout,
        returncode=grok_outcome.returncode,
    )


def _record_grok_fallthrough(
    grok_outcome: GrokRunnerOutcome,
    *,
    role: str,
    prompt_file: Path,
    working_directory: Path,
    timeout_seconds: int,
    is_claude_tier_enabled: bool,
) -> SpawnOutcome:
    all_attempts = [
        _attempt(
            TIER_GROK,
            is_ok=False,
            reason=grok_outcome.classification,
        )
    ]
    return _after_grok_fallthrough(
        role=role,
        prompt_file=prompt_file,
        working_directory=working_directory,
        timeout_seconds=timeout_seconds,
        is_claude_tier_enabled=is_claude_tier_enabled,
        all_attempts=all_attempts,
        fallthrough_returncode=grok_outcome.returncode,
    )


def resolve_worker_spawn(
    *,
    role: str,
    prompt_file: Path,
    working_directory: Path,
    timeout_seconds: int,
    is_claude_tier_enabled: bool,
    run_state_directory: Path,
    max_turns: int,
) -> SpawnOutcome:
    """Walk the worker-spawn tiers and return the structured outcome.

    Args:
        role: Worker role name for preflight; mapped to a primary agent stem.
        prompt_file: Path to the prompt file for headless workers.
        working_directory: Working directory for grok and claude headless tiers.
        timeout_seconds: Timeout applied to each tier invocation.
        is_claude_tier_enabled: When True, allow tier 3 on a Claude host.
        run_state_directory: Run-scoped directory for leader sockets and cache.
        max_turns: Maximum agent turns for the headless grok worker.

    Returns:
        The dispatcher outcome including the ordered attempts trail.
    """
    preflight_outcome: PreflightOutcome = spawn_preflight_runner(
        role=role,
        should_ping=False,
        run_state_directory=run_state_directory,
    )
    if not preflight_outcome.is_usable:
        return _record_preflight_fallthrough(
            preflight_outcome,
            role=role,
            prompt_file=prompt_file,
            working_directory=working_directory,
            timeout_seconds=timeout_seconds,
            is_claude_tier_enabled=is_claude_tier_enabled,
        )

    grok_outcome = _run_tier_grok(
        role=role,
        prompt_file=prompt_file,
        working_directory=working_directory,
        run_state_directory=run_state_directory,
        max_turns=max_turns,
        timeout_seconds=timeout_seconds,
    )
    if grok_outcome.is_ok:
        return _record_grok_success(grok_outcome)
    return _record_grok_fallthrough(
        grok_outcome,
        role=role,
        prompt_file=prompt_file,
        working_directory=working_directory,
        timeout_seconds=timeout_seconds,
        is_claude_tier_enabled=is_claude_tier_enabled,
    )


def encode_spawn_outcome(spawn_outcome: SpawnOutcome) -> dict[str, object]:
    """Encode a spawn outcome as the JSON-serializable payload.

    Args:
        spawn_outcome: The dispatcher outcome to encode.

    Returns:
        A plain dict matching the CLI JSON shape.
    """
    all_encoded_attempts = [
        {
            ATTEMPT_KEY_TIER: each_attempt.tier,
            ATTEMPT_KEY_OK: each_attempt.is_ok,
            ATTEMPT_KEY_REASON: each_attempt.reason,
        }
        for each_attempt in spawn_outcome.all_attempts
    ]
    return {
        RESULT_KEY_TIER_USED: spawn_outcome.tier_used,
        RESULT_KEY_OK: spawn_outcome.is_ok,
        RESULT_KEY_ATTEMPTS: all_encoded_attempts,
        RESULT_KEY_OUTPUT: spawn_outcome.captured_stdout,
        RESULT_KEY_RETURNCODE: spawn_outcome.returncode,
    }


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dispatch a worker role through the grok then claude tiers."
    )
    parser.add_argument(
        CLI_ROLE_FLAG,
        default=DEFAULT_ROLE,
        help="Worker role name for preflight; mapped to a primary agent for grok.",
    )
    parser.add_argument(
        PROMPT_FILE_FLAG,
        dest="prompt_file",
        required=True,
        type=Path,
        help="Path to the prompt file for headless workers.",
    )
    parser.add_argument(
        CWD_FLAG,
        dest="working_directory",
        required=True,
        type=Path,
        help="Working directory for headless grok and claude workers.",
    )
    parser.add_argument(
        CLI_TIMEOUT_FLAG,
        dest="timeout_seconds",
        type=int,
        default=DEFAULT_WORKER_TIMEOUT_SECONDS,
        help="Timeout in seconds applied to each tier invocation.",
    )
    parser.add_argument(
        CLI_ENABLE_CLAUDE_TIER_FLAG,
        dest="is_claude_tier_enabled",
        action="store_true",
        default=False,
        help="Enable the headless claude chain tier on a Claude host.",
    )
    parser.add_argument(
        CLI_RUN_STATE_DIR_FLAG,
        dest="run_state_directory",
        required=True,
        type=Path,
        help="Run-scoped state directory for leader sockets and cache.",
    )
    return parser


def _exit_code_for_outcome(
    spawn_outcome: SpawnOutcome, *, is_config_error: bool
) -> int:
    if is_config_error or spawn_outcome.is_config_error:
        return SPAWN_CONFIG_ERROR_EXIT_CODE
    if spawn_outcome.tier_used is None:
        return SPAWN_EXHAUSTED_EXIT_CODE
    return SPAWN_SERVED_EXIT_CODE


def _config_error_outcome(configuration_error: ChainConfigurationError) -> SpawnOutcome:
    return SpawnOutcome(
        tier_used=None,
        is_ok=False,
        all_attempts=(),
        captured_stdout=str(configuration_error),
        returncode=SPAWN_CONFIG_ERROR_EXIT_CODE,
        is_config_error=True,
    )


def _missing_prompt_file_outcome() -> SpawnOutcome:
    return SpawnOutcome(
        tier_used=None,
        is_ok=False,
        all_attempts=(),
        captured_stdout=REASON_PROMPT_FILE_MISSING,
        returncode=SPAWN_CONFIG_ERROR_EXIT_CODE,
        is_config_error=True,
    )


def _write_spawn_outcome_and_exit_code(
    spawn_outcome: SpawnOutcome, *, is_config_error: bool
) -> int:
    encoded_payload = encode_spawn_outcome(spawn_outcome)
    sys.stdout.write(json.dumps(encoded_payload) + "\n")
    return _exit_code_for_outcome(
        spawn_outcome,
        is_config_error=is_config_error or spawn_outcome.is_config_error,
    )


def main(all_command_arguments: list[str]) -> int:
    """Run the dispatcher for CLI arguments and print the JSON outcome.

    Args:
        all_command_arguments: The argument vector after the program name.

    Returns:
        ``0`` when a tier served, ``2`` when exhausted, ``3`` on config error.
    """
    parser = _build_argument_parser()
    parsed_arguments = parser.parse_args(all_command_arguments)
    run_state_directory = parsed_arguments.run_state_directory
    run_state_directory.mkdir(parents=True, exist_ok=True)
    if not parsed_arguments.prompt_file.is_file():
        return _write_spawn_outcome_and_exit_code(
            _missing_prompt_file_outcome(),
            is_config_error=True,
        )
    is_config_error = False
    try:
        spawn_outcome = resolve_worker_spawn(
            role=parsed_arguments.role,
            prompt_file=parsed_arguments.prompt_file,
            working_directory=parsed_arguments.working_directory,
            timeout_seconds=parsed_arguments.timeout_seconds,
            is_claude_tier_enabled=parsed_arguments.is_claude_tier_enabled,
            run_state_directory=run_state_directory,
            max_turns=DEFAULT_SPAWN_MAX_TURNS,
        )
    except ChainConfigurationError as configuration_error:
        is_config_error = True
        spawn_outcome = _config_error_outcome(configuration_error)
    return _write_spawn_outcome_and_exit_code(
        spawn_outcome, is_config_error=is_config_error
    )


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
