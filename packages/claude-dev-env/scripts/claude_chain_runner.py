#!/usr/bin/env python3
"""Run a ``claude`` invocation through a config-driven fallback chain.

An automation that shells out to a single ``claude -p ...`` fails outright when
that account hits a usage limit. Other logged-in installs sit idle meanwhile.
This module runs the leading binary in the chain. It falls over to the next
binary only on a usage-limit failure. Every other outcome returns to the caller
unchanged.

The chain lives in ``~/.claude/claude-chain.json``. Copy the committed
``claude-chain.example.json`` template there and list your binaries in fallback
order::

    {"chain": [{"command": "claude", "extra_args": []},
               {"command": "claude-ev", "extra_args": []}]}

A usage-limited primary falls over to the second binary::

    primary claude     -> exit 1, "usage limit reached"  (falls over)
    fallback claude-ev -> exit 0                          (served)

When stdin is piped (not a TTY), the runner reads it once and forwards the
same text to every chain attempt so a piped ``-p`` charter body reaches each
binary in the walk::

    cat charter.md | python claude_chain_runner.py -- -p --strict-mcp-config

Import ``run_claude`` for the outcome object, or run the module as a CLI::

    python claude_chain_runner.py [--timeout-seconds N] -- <claude args...>
"""

from __future__ import annotations

import argparse
import io
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from dev_env_scripts_constants.claude_chain_constants import (
    ALL_USAGE_LIMIT_SIGNATURES,
    ATTEMPT_STATUS_EXECUTABLE_NOT_FOUND,
    ATTEMPT_STATUS_NONZERO_EXIT,
    ATTEMPT_STATUS_SERVED,
    ATTEMPT_STATUS_TIMEOUT,
    ATTEMPT_STATUS_USAGE_LIMITED,
    ATTEMPT_SUMMARY_ENTRY_TEMPLATE,
    ATTEMPT_SUMMARY_JOIN_SEPARATOR,
    CHAIN_CONFIG_ERROR_EXIT_CODE,
    CHAIN_EXHAUSTED_EXIT_CODE,
    CHAIN_EXHAUSTED_MESSAGE_TEMPLATE,
    CLAUDE_HOME_SUBDIRECTORY,
    CLI_ARGUMENTS_SEPARATOR,
    CLI_TIMEOUT_FLAG,
    CODEC_ERROR_STRATEGY,
    CONFIG_CHAIN_EMPTY_REASON,
    CONFIG_CHAIN_KEY,
    CONFIG_CHAIN_NOT_LIST_REASON,
    CONFIG_COMMAND_KEY,
    CONFIG_ENTRY_COMMAND_MISSING_REASON,
    CONFIG_ENTRY_EXTRA_ARGS_INVALID_REASON,
    CONFIG_ENTRY_NOT_OBJECT_REASON,
    CONFIG_EXTRA_ARGS_KEY,
    CONFIG_FILENAME,
    CONFIG_INVALID_SHAPE_MESSAGE_TEMPLATE,
    CONFIG_MALFORMED_MESSAGE_TEMPLATE,
    CONFIG_MISSING_MESSAGE_TEMPLATE,
    CONFIG_NOT_OBJECT_REASON,
    CONFIG_UNREADABLE_MESSAGE_TEMPLATE,
    DEFAULT_TIMEOUT_SECONDS,
    EXAMPLE_CONFIG_FILENAME,
    NO_COMPLETED_PROCESS_RETURN_CODE,
    UTF8_ENCODING,
)

import tempfile


def _decode_captured_stream(raw_bytes: bytes, encoding: str, errors: str) -> str:
    """Decode captured *raw_bytes* using *encoding* and *errors*."""
    return raw_bytes.decode(encoding, errors)


def _optional_timeout(value: object) -> float | None:
    """Return *value* as a timeout in seconds, or None when it is not numeric."""
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _optional_cwd(value: object) -> str | None:
    """Return *value* as a working-directory string, or None when unset."""
    if value is None:
        return None
    return str(value)


def _optional_stdin_fd(value: object, input_bytes: bytes | None) -> int | None:
    """Return the stdin descriptor to use, or None when stdin text is supplied."""
    if input_bytes is not None:
        return None
    if isinstance(value, int):
        return value
    return None


def _stdin_bytes(value: object, encoding: str, errors: str) -> bytes | None:
    """Encode stdin text *value* to bytes, or None when no text is given."""
    if value is None:
        return None
    return str(value).encode(encoding, errors)


# Capturing a large-output child through OS pipes (``capture_output=True``)
# deadlocks on Windows: the child buffers its whole response and flushes it at
# once, the pipe buffer fills before the parent drains it, and both sides block.
# Redirecting each stream to a temporary file removes the pipe, so the child
# writes freely; the files are then read back and decoded the way a pipe capture
# would. ``capture_output`` and ``text`` are ignored in favor of file
# redirection; ``timeout``, ``check``, ``input``, ``stdin``, ``cwd``,
# ``encoding``, and ``errors`` are honored.
def _run_captured_subprocess(
    all_invocation_tokens: list[str],
    **all_subprocess_options: object,
) -> subprocess.CompletedProcess[str]:
    """Run *all_invocation_tokens*, spooling stdout and stderr to temp files."""
    encoding = str(all_subprocess_options.get("encoding") or UTF8_ENCODING)
    errors = str(all_subprocess_options.get("errors") or CODEC_ERROR_STRATEGY)
    stdin_input = all_subprocess_options.get("input")
    input_bytes = _stdin_bytes(stdin_input, encoding, errors)
    with (
        tempfile.TemporaryFile() as stdout_file,
        tempfile.TemporaryFile() as stderr_file,
    ):
        completion = subprocess.run(
            all_invocation_tokens, stdout=stdout_file, stderr=stderr_file,
            check=bool(all_subprocess_options.get("check", False)),
            timeout=_optional_timeout(all_subprocess_options.get("timeout")),
            cwd=_optional_cwd(all_subprocess_options.get("cwd")),
            input=input_bytes,
            stdin=_optional_stdin_fd(all_subprocess_options.get("stdin"), input_bytes),
        )
        stdout_file.seek(0)
        stderr_file.seek(0)
        return subprocess.CompletedProcess(
            all_invocation_tokens,
            completion.returncode,
            _decode_captured_stream(stdout_file.read(), encoding, errors),
            _decode_captured_stream(stderr_file.read(), encoding, errors),
        )


class ChainConfigurationError(Exception):
    """Raised when the chain configuration is missing, unreadable, or malformed."""


@dataclass(frozen=True)
class ChainEntry:
    """One binary in the fallback chain and its per-account extra arguments."""

    command: str
    extra_args: tuple[str, ...]


@dataclass(frozen=True)
class ChainAttempt:
    """Record of one binary invocation and how it resolved."""

    command: str
    status: str


@dataclass(frozen=True)
class ChainInvocationOutcome:
    """Outcome of walking the chain for one call.

    ``served_command`` names the binary whose response is returned. It is
    ``None`` when no binary served the call: every entry was usage-limited or
    missing, the invocation timed out, or the primary binary was absent. The
    ``attempts`` trail records every binary tried and how it resolved.
    """

    served_command: str | None
    returncode: int
    stdout: str
    stderr: str
    attempts: tuple[ChainAttempt, ...]


chain_subprocess_runner = _run_captured_subprocess


def chain_config_path() -> Path:
    """Return the path to the per-user chain configuration file."""
    return Path.home() / CLAUDE_HOME_SUBDIRECTORY / CONFIG_FILENAME


def _invalid_shape_error(config_path: Path, reason: str) -> ChainConfigurationError:
    return ChainConfigurationError(
        CONFIG_INVALID_SHAPE_MESSAGE_TEMPLATE.format(
            config_path=config_path,
            reason=reason,
            example_filename=EXAMPLE_CONFIG_FILENAME,
        )
    )


def _coerce_extra_args(raw_extra_args: object, config_path: Path) -> tuple[str, ...]:
    if not isinstance(raw_extra_args, list) or not all(
        isinstance(each_argument, str) for each_argument in raw_extra_args
    ):
        raise _invalid_shape_error(config_path, CONFIG_ENTRY_EXTRA_ARGS_INVALID_REASON)
    return tuple(raw_extra_args)


def _parse_chain_entry(raw_entry: object, config_path: Path) -> ChainEntry:
    if not isinstance(raw_entry, dict):
        raise _invalid_shape_error(config_path, CONFIG_ENTRY_NOT_OBJECT_REASON)
    command = raw_entry.get(CONFIG_COMMAND_KEY)
    if not isinstance(command, str) or not command:
        raise _invalid_shape_error(config_path, CONFIG_ENTRY_COMMAND_MISSING_REASON)
    extra_args = _coerce_extra_args(
        raw_entry.get(CONFIG_EXTRA_ARGS_KEY, []), config_path
    )
    return ChainEntry(command=command, extra_args=extra_args)


def _parse_chain_entries(parsed_config: object, config_path: Path) -> list[ChainEntry]:
    if not isinstance(parsed_config, dict):
        raise _invalid_shape_error(config_path, CONFIG_NOT_OBJECT_REASON)
    raw_chain = parsed_config.get(CONFIG_CHAIN_KEY)
    if not isinstance(raw_chain, list):
        raise _invalid_shape_error(config_path, CONFIG_CHAIN_NOT_LIST_REASON)
    if not raw_chain:
        raise _invalid_shape_error(config_path, CONFIG_CHAIN_EMPTY_REASON)
    return [
        _parse_chain_entry(each_raw_entry, config_path) for each_raw_entry in raw_chain
    ]


def load_chain(config_path: Path) -> list[ChainEntry]:
    """Load the ordered fallback chain from *config_path*.

    Args:
        config_path: Path to the chain configuration JSON file.

    Returns:
        The ordered list of chain entries the file declares.

    Raises:
        ChainConfigurationError: When the file is absent, unreadable, not valid
            JSON, or does not match the expected shape.
    """
    if not config_path.is_file():
        raise ChainConfigurationError(
            CONFIG_MISSING_MESSAGE_TEMPLATE.format(
                config_path=config_path, example_filename=EXAMPLE_CONFIG_FILENAME
            )
        )
    try:
        raw_text = config_path.read_text(encoding=UTF8_ENCODING)
    except OSError as read_error:
        raise ChainConfigurationError(
            CONFIG_UNREADABLE_MESSAGE_TEMPLATE.format(
                config_path=config_path,
                error=read_error,
                example_filename=EXAMPLE_CONFIG_FILENAME,
            )
        ) from read_error
    try:
        parsed_config = json.loads(raw_text)
    except json.JSONDecodeError as decode_error:
        raise ChainConfigurationError(
            CONFIG_MALFORMED_MESSAGE_TEMPLATE.format(
                config_path=config_path,
                error=decode_error,
                example_filename=EXAMPLE_CONFIG_FILENAME,
            )
        ) from decode_error
    return _parse_chain_entries(parsed_config, config_path)


def _build_invocation(entry: ChainEntry, all_claude_arguments: list[str]) -> list[str]:
    return [entry.command, *all_claude_arguments, *entry.extra_args]


def _is_usage_limit_failure(completion: subprocess.CompletedProcess[str]) -> bool:
    combined_text = f"{completion.stdout}{completion.stderr}".lower()
    return any(
        each_signature in combined_text for each_signature in ALL_USAGE_LIMIT_SIGNATURES
    )


def _served_outcome(
    served_command: str,
    completion: subprocess.CompletedProcess[str],
    all_attempts: list[ChainAttempt],
) -> ChainInvocationOutcome:
    return ChainInvocationOutcome(
        served_command=served_command,
        returncode=completion.returncode,
        stdout=completion.stdout,
        stderr=completion.stderr,
        attempts=tuple(all_attempts),
    )


def _timeout_streams(
    timeout_error: subprocess.TimeoutExpired | None,
) -> tuple[str, str]:
    if timeout_error is None:
        return "", ""
    captured_stdout = (
        timeout_error.stdout if isinstance(timeout_error.stdout, str) else ""
    )
    captured_stderr = (
        timeout_error.stderr if isinstance(timeout_error.stderr, str) else ""
    )
    return captured_stdout, captured_stderr


def _no_process_outcome(
    all_attempts: list[ChainAttempt],
    timeout_error: subprocess.TimeoutExpired | None,
) -> ChainInvocationOutcome:
    captured_stdout, captured_stderr = _timeout_streams(timeout_error)
    return ChainInvocationOutcome(
        served_command=None,
        returncode=NO_COMPLETED_PROCESS_RETURN_CODE,
        stdout=captured_stdout,
        stderr=captured_stderr,
        attempts=tuple(all_attempts),
    )


def _exhausted_outcome(
    all_attempts: list[ChainAttempt],
    last_usage_limited: subprocess.CompletedProcess[str] | None,
) -> ChainInvocationOutcome:
    if last_usage_limited is None:
        return _no_process_outcome(all_attempts, None)
    return ChainInvocationOutcome(
        served_command=None,
        returncode=last_usage_limited.returncode,
        stdout=last_usage_limited.stdout,
        stderr=last_usage_limited.stderr,
        attempts=tuple(all_attempts),
    )


def _classify_completion(
    entry: ChainEntry,
    completion: subprocess.CompletedProcess[str],
    all_attempts: list[ChainAttempt],
) -> ChainInvocationOutcome | None:
    if completion.returncode == 0:
        all_attempts.append(ChainAttempt(entry.command, ATTEMPT_STATUS_SERVED))
        return _served_outcome(entry.command, completion, all_attempts)
    if _is_usage_limit_failure(completion):
        all_attempts.append(ChainAttempt(entry.command, ATTEMPT_STATUS_USAGE_LIMITED))
        return None
    all_attempts.append(ChainAttempt(entry.command, ATTEMPT_STATUS_NONZERO_EXIT))
    return _served_outcome(entry.command, completion, all_attempts)


def run_claude(
    all_claude_arguments: list[str],
    *,
    timeout_seconds: int,
    stdin_text: str | None = None,
) -> ChainInvocationOutcome:
    """Run *all_claude_arguments* through the configured fallback chain.

    The leading binary serves; only a usage-limit failure falls over to the
    next. A timeout, a missing primary, or a non-usage-limit non-zero exit stops
    the walk. *stdin_text*, when set, is forwarded as stdin on every attempt.

    ::

        # primary usage-limited, fallback serves
        claude     -> exit 1 "usage limit reached"  # flag: falls over
        claude-ev  -> exit 0                         # ok: served

    Args:
        all_claude_arguments: Arguments passed after the binary name, such as
            ``["-p", prompt, "--strict-mcp-config"]``.
        timeout_seconds: Timeout applied to each binary invocation.
        stdin_text: Optional UTF-8 text forwarded as stdin to every binary.
            ``None`` leaves the subprocess without a piped stdin body.

    Returns:
        The outcome of the walk, naming the serving binary and the full
        attempt trail.

    Raises:
        ChainConfigurationError: When the chain configuration cannot be loaded.
    """
    all_entries = load_chain(chain_config_path())
    all_attempts: list[ChainAttempt] = []
    last_usage_limited: subprocess.CompletedProcess[str] | None = None
    for each_index, each_entry in enumerate(all_entries):
        is_primary = each_index == 0
        try:
            completion = chain_subprocess_runner(
                _build_invocation(each_entry, all_claude_arguments),
                capture_output=True,
                text=True,
                encoding=UTF8_ENCODING,
                errors=CODEC_ERROR_STRATEGY,
                timeout=timeout_seconds,
                check=False,
                input=stdin_text,
            )
        except subprocess.TimeoutExpired as timeout_error:
            all_attempts.append(
                ChainAttempt(each_entry.command, ATTEMPT_STATUS_TIMEOUT)
            )
            return _no_process_outcome(all_attempts, timeout_error)
        except FileNotFoundError:
            all_attempts.append(
                ChainAttempt(each_entry.command, ATTEMPT_STATUS_EXECUTABLE_NOT_FOUND)
            )
            if is_primary:
                return _no_process_outcome(all_attempts, None)
            continue
        terminal_outcome = _classify_completion(each_entry, completion, all_attempts)
        if terminal_outcome is not None:
            return terminal_outcome
        last_usage_limited = completion
    return _exhausted_outcome(all_attempts, last_usage_limited)


def _build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a claude invocation through the fallback chain."
    )
    parser.add_argument(
        CLI_TIMEOUT_FLAG,
        dest="timeout_seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Timeout in seconds applied to each binary invocation.",
    )
    parser.add_argument("passthrough", nargs=argparse.REMAINDER)
    return parser


def _strip_leading_separator(all_passthrough: list[str]) -> list[str]:
    if all_passthrough and all_passthrough[0] == CLI_ARGUMENTS_SEPARATOR:
        return all_passthrough[1:]
    return all_passthrough


def _exhausted_message(all_attempts: tuple[ChainAttempt, ...]) -> str:
    attempt_summary = ATTEMPT_SUMMARY_JOIN_SEPARATOR.join(
        ATTEMPT_SUMMARY_ENTRY_TEMPLATE.format(
            command=each_attempt.command, status=each_attempt.status
        )
        for each_attempt in all_attempts
    )
    return CHAIN_EXHAUSTED_MESSAGE_TEMPLATE.format(attempt_summary=attempt_summary)


def _read_piped_stdin_text() -> str | None:
    if sys.stdin.isatty():
        return None
    return sys.stdin.read()


def main(all_command_arguments: list[str]) -> int:
    """Walk the chain for CLI arguments and return the process exit code.

    Args:
        all_command_arguments: The argument vector after the program name.

    Returns:
        The served binary's return code, a distinct code when the chain is
        exhausted, or a distinct code when the configuration cannot be loaded.
    """
    parser = _build_argument_parser()
    parsed_arguments = parser.parse_args(all_command_arguments)
    all_claude_arguments = _strip_leading_separator(parsed_arguments.passthrough)
    maybe_stdin_text = _read_piped_stdin_text()
    try:
        chain_outcome = run_claude(
            all_claude_arguments,
            timeout_seconds=parsed_arguments.timeout_seconds,
            stdin_text=maybe_stdin_text,
        )
    except ChainConfigurationError as configuration_error:
        print(str(configuration_error), file=sys.stderr)
        return CHAIN_CONFIG_ERROR_EXIT_CODE
    if chain_outcome.served_command is None:
        print(_exhausted_message(chain_outcome.attempts), file=sys.stderr)
        return CHAIN_EXHAUSTED_EXIT_CODE
    sys.stdout.write(chain_outcome.stdout)
    sys.stderr.write(chain_outcome.stderr)
    return chain_outcome.returncode


def _reconfigure_stream_to_utf8(stream: TextIO) -> None:
    """Reconfigure *stream* to emit UTF-8, replacing any unmappable character."""
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding=UTF8_ENCODING, errors=CODEC_ERROR_STRATEGY)


if __name__ == "__main__":
    _reconfigure_stream_to_utf8(sys.stdout)
    _reconfigure_stream_to_utf8(sys.stderr)
    sys.exit(main(sys.argv[1:]))
