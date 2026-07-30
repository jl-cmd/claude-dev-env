#!/usr/bin/env python3
"""Run a ``claude`` invocation through a fallback chain of account binaries.

An automation that shells out to a single ``claude -p ...`` fails outright when
that account hits a usage limit. Other logged-in installs sit idle meanwhile.
By default this module probes remaining weekly usage once per call, ranks chain
accounts highest remaining first, and tries that order. It falls over to the
next ranked binary only on a usage-limit failure. Every other outcome returns
to the caller unchanged.

Ordered-account mode (``--routing-mode ordered_account``) walks the chain in
config order instead, still falling over only on a usage-limit signature.
Authentication, timeout, and other non-usage failures stop immediately with
``terminal_status=advisor_blocked``.

The chain lives in ``~/.claude/claude-chain.json``. Copy the committed
``claude-chain.example.json`` template there and list your account binaries.
Default try order comes from weekly remaining via ``claude_chain_usage``
(usage-pause OAuth probe), not from list position alone::

    {"chain": [{"command": "claude", "extra_args": []},
               {"command": "claude-ev", "extra_args": []}]}

A usage-limited first try falls over to the next ranked binary::

    first try (highest remaining)  -> exit 1, "usage limit reached"  (falls over)
    next ranked binary             -> exit 0                          (served)

When stdin is piped (not a TTY), the runner reads it once and forwards the
same text to every chain attempt so a piped ``-p`` charter body reaches each
binary in the walk::

    cat charter.md | python claude_chain_runner.py -- -p --strict-mcp-config

Import ``run_claude`` for the outcome object, or run the module as a CLI::

    python claude_chain_runner.py [--timeout-seconds N]
        [--routing-mode usage_ranked|ordered_account] -- <claude args...>
"""

from __future__ import annotations

import argparse
import importlib
import io
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Protocol, TextIO

if __name__ == "__main__":
    sys.modules.setdefault("claude_chain_runner", sys.modules[__name__])

from dev_env_scripts_constants.claude_chain_constants import (
    AFFINITY_BINDING_COMMAND_MISSING_REASON,
    AFFINITY_BINDING_NOT_OBJECT_REASON,
    AFFINITY_BINDING_SESSION_ID_MISSING_REASON,
    AFFINITY_BINDINGS_MISSING_OR_NOT_LIST_REASON,
    AFFINITY_CORRUPT_MESSAGE_TEMPLATE,
    AFFINITY_JSON_INDENT_SPACES,
    AFFINITY_KEY_ALL_BINDINGS,
    AFFINITY_KEY_COMMAND,
    AFFINITY_KEY_SCHEMA_VERSION,
    AFFINITY_KEY_SESSION_ID,
    AFFINITY_MAXIMUM_ENTRIES,
    AFFINITY_MAXIMUM_ENTRIES_MINIMUM_MESSAGE,
    AFFINITY_SESSION_ID_AND_COMMAND_REQUIRED_MESSAGE,
    AFFINITY_STATE_FILENAME,
    AFFINITY_STATE_SCHEMA_VERSION,
    AFFINITY_TEMP_SUFFIX,
    AFFINITY_TOP_LEVEL_NOT_OBJECT_REASON,
    AFFINITY_UNSUPPORTED_SCHEMA_VERSION_REASON_TEMPLATE,
    AFFINITY_WRITE_FAILED_MESSAGE_TEMPLATE,
    ALL_ROUTING_MODES,
    ALL_USAGE_LIMIT_SIGNATURES,
    ATTEMPT_STATUS_EXECUTABLE_NOT_FOUND,
    ATTEMPT_STATUS_NONZERO_EXIT,
    ATTEMPT_STATUS_SERVED,
    ATTEMPT_STATUS_TIMEOUT,
    ATTEMPT_STATUS_USAGE_LIMITED,
    ATTEMPT_SUMMARY_ENTRY_TEMPLATE,
    ATTEMPT_SUMMARY_JOIN_SEPARATOR,
    CARRIAGE_RETURN,
    CHAIN_ADVISOR_BLOCKED_EXIT_CODE,
    CHAIN_CONFIG_ERROR_EXIT_CODE,
    CHAIN_EXHAUSTED_EXIT_CODE,
    CHAIN_EXHAUSTED_MESSAGE_TEMPLATE,
    CHAIN_USAGE_MODULE_NAME,
    CLAUDE_HOME_SUBDIRECTORY,
    CLI_ARGUMENTS_SEPARATOR,
    CLI_ROUTING_MODE_FLAG,
    CLI_TIMEOUT_FLAG,
    CODEC_ERROR_STRATEGY,
    CONFIG_CHAIN_EMPTY_REASON,
    CONFIG_CHAIN_KEY,
    CONFIG_CHAIN_NOT_LIST_REASON,
    CONFIG_COMMAND_KEY,
    CONFIG_CREDENTIALS_PATH_KEY,
    CONFIG_ENTRY_COMMAND_MISSING_REASON,
    CONFIG_ENTRY_CREDENTIALS_PATH_INVALID_REASON,
    CONFIG_ENTRY_EXTRA_ARGS_INVALID_REASON,
    CONFIG_ENTRY_NOT_OBJECT_REASON,
    CONFIG_EXTRA_ARGS_KEY,
    CONFIG_FILENAME,
    CONFIG_INVALID_SHAPE_MESSAGE_TEMPLATE,
    CONFIG_MALFORMED_MESSAGE_TEMPLATE,
    CONFIG_MISSING_MESSAGE_TEMPLATE,
    CONFIG_NOT_OBJECT_REASON,
    CONFIG_UNREADABLE_MESSAGE_TEMPLATE,
    CRLF_NEWLINE,
    DEFAULT_ROUTING_MODE,
    DEFAULT_TIMEOUT_SECONDS,
    EXAMPLE_CONFIG_FILENAME,
    LINE_FEED,
    NO_COMPLETED_PROCESS_RETURN_CODE,
    ROUTING_MODE_ORDERED_ACCOUNT,
    SESSION_ID_JSON_KEY,
    TERMINAL_STATUS_ADVISOR_BLOCKED,
    TERMINAL_STATUS_CHAIN_EXHAUSTED,
    TERMINAL_STATUS_SERVED,
    TERMINAL_STATUS_TIMEOUT,
    UTF8_ENCODING,
)


def _decode_captured_stream(raw_bytes: bytes, encoding: str, errors: str) -> str:
    """Decode captured *raw_bytes* with ``text=True`` universal-newline semantics.

    Spool capture writes binary temp files, so a bare ``.decode`` leaves CRLF and
    bare CR intact. ``subprocess.run(..., text=True)`` normalized those to LF;
    this helper restores that contract for Windows children that emit ``\\r\\n``.
    """
    decoded_text = raw_bytes.decode(encoding, errors)
    return decoded_text.replace(CRLF_NEWLINE, LINE_FEED).replace(
        CARRIAGE_RETURN, LINE_FEED
    )


class _SpooledByteStream(Protocol):
    """Binary spool with seek/read — TemporaryFile wrappers and BufferedIO."""

    def seek(self, target: int, whence: int = 0, /) -> int: ...

    def read(self, size: int | None = -1, /) -> bytes: ...


def _decoded_spooled_streams(
    stdout_file: _SpooledByteStream,
    stderr_file: _SpooledByteStream,
    encoding: str,
    errors: str,
) -> tuple[str, str]:
    """Seek both spool files to the start and decode their full contents."""
    stdout_file.seek(0)
    stderr_file.seek(0)
    return (
        _decode_captured_stream(stdout_file.read(), encoding, errors),
        _decode_captured_stream(stderr_file.read(), encoding, errors),
    )


def _attach_partial_timeout_streams(
    timeout_error: subprocess.TimeoutExpired,
    stdout_file: _SpooledByteStream,
    stderr_file: _SpooledByteStream,
    encoding: str,
    errors: str,
) -> None:
    """Decode partial spool contents onto *timeout_error* before re-raise."""
    captured_stdout, captured_stderr = _decoded_spooled_streams(
        stdout_file, stderr_file, encoding, errors
    )
    timeout_error.stdout = captured_stdout
    timeout_error.stderr = captured_stderr


# Capturing a large-output child through OS pipes (``capture_output=True``)
# deadlocks on Windows: the child buffers its whole response and flushes it at
# once, the pipe buffer fills before the parent drains it, and both sides block.
# Redirecting each stream to a temporary file removes the pipe, so the child
# writes freely; the files are then read back and decoded the way a pipe capture
# would. ``capture_output``, ``text``, and ``env`` are ignored in favor of file
# redirection and the parent environment; ``timeout``, ``check``, ``cwd``,
# ``stdin``, ``input``, ``encoding``, and ``errors`` are honored. On timeout,
# partial stdout/stderr are decoded from the temp files and attached to the
# raised ``TimeoutExpired``. When ``check=True`` and the child exits non-zero,
# ``CalledProcessError.stdout`` / ``.stderr`` stay unset (temp files are not
# attached to that raised error).
def _run_captured_subprocess(
    all_invocation_tokens: list[str],
    **all_subprocess_options: object,
) -> subprocess.CompletedProcess[str]:
    """Run *all_invocation_tokens*, spooling stdout and stderr to temp files."""
    encoding = str(all_subprocess_options.get("encoding") or UTF8_ENCODING)
    errors = str(all_subprocess_options.get("errors") or CODEC_ERROR_STRATEGY)
    input_bytes = _captured_stdin_bytes(all_subprocess_options, encoding, errors)
    working_directory = all_subprocess_options.get("cwd")
    timeout_seconds = all_subprocess_options.get("timeout")
    with (
        tempfile.TemporaryFile() as stdout_file,
        tempfile.TemporaryFile() as stderr_file,
    ):
        try:
            completion = subprocess.run(
                all_invocation_tokens,
                stdout=stdout_file,
                stderr=stderr_file,
                cwd=working_directory if isinstance(working_directory, str) else None,
                check=bool(all_subprocess_options.get("check", False)),
                timeout=(
                    float(timeout_seconds)
                    if isinstance(timeout_seconds, (int, float))
                    else None
                ),
                input=input_bytes,
            )
        except subprocess.TimeoutExpired as timeout_error:
            _attach_partial_timeout_streams(
                timeout_error, stdout_file, stderr_file, encoding, errors
            )
            raise
        captured_stdout, captured_stderr = _decoded_spooled_streams(
            stdout_file, stderr_file, encoding, errors
        )
        return subprocess.CompletedProcess(
            all_invocation_tokens,
            completion.returncode,
            captured_stdout,
            captured_stderr,
        )


def _captured_stdin_bytes(
    all_subprocess_options: dict[str, object], encoding: str, errors: str
) -> bytes | None:
    """Return the bytes to feed the child's stdin for a spooled run.

    ::

        stdin=<open prompt file>  -> the file's bytes
        stdin=subprocess.DEVNULL  -> b"" (an immediate EOF)
        input="charter text"      -> the encoded text

    A wrapper hands the runner a ``stdin`` stream or a ``DEVNULL`` sentinel; the
    spooled run reads from an ``input`` pipe rather than the caller's handle, so
    the stream is read into bytes here to deliver the same stdin a direct pipe
    would. When no ``stdin`` is given, the ``input`` text is encoded instead.
    """
    stdin_source = all_subprocess_options.get("stdin")
    if isinstance(stdin_source, io.TextIOBase):
        return stdin_source.read().encode(encoding, errors)
    if isinstance(stdin_source, (io.RawIOBase, io.BufferedIOBase)):
        return stdin_source.read() or b""
    if isinstance(stdin_source, int):
        return b""
    input_text = all_subprocess_options.get("input")
    if input_text is None:
        return None
    return str(input_text).encode(encoding, errors)


class ChainConfigurationError(Exception):
    """Raised when the chain configuration is missing, unreadable, or malformed."""


@dataclass(frozen=True)
class ChainEntry:
    """One binary in the fallback chain and its per-account extra arguments.

    ``credentials_path`` is an optional path to that account's OAuth credentials
    file. The subprocess walk does not pass it; weekly-usage ranking reads it
    when present.
    """

    command: str
    extra_args: tuple[str, ...]
    credentials_path: str | None = None


@dataclass(frozen=True)
class ChainAttempt:
    """Record of one binary invocation and how it resolved."""

    command: str
    status: str


@dataclass(frozen=True)
class ChainInvocationOutcome:
    """Outcome of one chain walk: who served, how it ended, optional session id.

    ::

        zero exit with JSON session_id
            -> served_command set, terminal_status=served, session_id filled
        ordered_account auth/timeout/generic process error
            -> served_command=None, terminal_status=advisor_blocked
        usage_ranked TimeoutExpired mid-walk
            -> served_command=None, terminal_status=timeout
        every entry usage-limited or missing
            -> served_command=None, terminal_status=chain_exhausted

    ``attempts`` lists every binary tried. Callers resume later consults with
    ``session_id`` when the bind returned one.
    """

    served_command: str | None
    returncode: int
    stdout: str
    stderr: str
    attempts: tuple[ChainAttempt, ...]
    terminal_status: str
    session_id: str | None = None


class WeeklyUsageAccountReport(Protocol):
    """Minimal account-report surface the runner needs for ranking and mapping."""

    command: str


chain_subprocess_runner = _run_captured_subprocess


def _load_chain_usage_module() -> ModuleType:
    return importlib.import_module(CHAIN_USAGE_MODULE_NAME)


def _default_chain_weekly_usage_reporter(
    *, config_path: Path
) -> list[WeeklyUsageAccountReport]:
    usage_module = _load_chain_usage_module()
    return usage_module.report_chain_weekly_usage(config_path=config_path)


chain_weekly_usage_reporter: Callable[..., list[WeeklyUsageAccountReport]] = (
    _default_chain_weekly_usage_reporter
)


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


def _coerce_credentials_path(
    raw_credentials_path: object, config_path: Path
) -> str | None:
    if raw_credentials_path is None:
        return None
    if not isinstance(raw_credentials_path, str) or not raw_credentials_path:
        raise _invalid_shape_error(
            config_path, CONFIG_ENTRY_CREDENTIALS_PATH_INVALID_REASON
        )
    return raw_credentials_path


def _parse_chain_entry(raw_entry: object, config_path: Path) -> ChainEntry:
    if not isinstance(raw_entry, dict):
        raise _invalid_shape_error(config_path, CONFIG_ENTRY_NOT_OBJECT_REASON)
    command = raw_entry.get(CONFIG_COMMAND_KEY)
    if not isinstance(command, str) or not command:
        raise _invalid_shape_error(config_path, CONFIG_ENTRY_COMMAND_MISSING_REASON)
    extra_args = _coerce_extra_args(
        raw_entry.get(CONFIG_EXTRA_ARGS_KEY, []), config_path
    )
    credentials_path = _coerce_credentials_path(
        raw_entry.get(CONFIG_CREDENTIALS_PATH_KEY), config_path
    )
    return ChainEntry(
        command=command,
        extra_args=extra_args,
        credentials_path=credentials_path,
    )


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


def _entries_ranked_by_weekly_remaining(
    all_entries: list[ChainEntry],
    all_usage_reports: Sequence[WeeklyUsageAccountReport],
) -> list[ChainEntry]:
    usage_module = _load_chain_usage_module()
    entries_by_command: dict[str, list[ChainEntry]] = {}
    for each_entry in all_entries:
        entries_by_command.setdefault(each_entry.command, []).append(each_entry)
    all_ranked_reports = usage_module.rank_accounts_by_weekly_remaining(
        list(all_usage_reports)
    )
    ranked_entries: list[ChainEntry] = []
    seen_commands: set[str] = set()
    for each_report in all_ranked_reports:
        if each_report.command in seen_commands:
            continue
        matched_entries = entries_by_command.get(each_report.command)
        if matched_entries is None:
            continue
        seen_commands.add(each_report.command)
        ranked_entries.extend(matched_entries)
    for each_entry in all_entries:
        if each_entry.command not in seen_commands:
            ranked_entries.append(each_entry)
    return ranked_entries


def _is_usage_limit_failure(completion: subprocess.CompletedProcess[str]) -> bool:
    combined_text = f"{completion.stdout}{completion.stderr}".lower()
    return any(
        each_signature in combined_text for each_signature in ALL_USAGE_LIMIT_SIGNATURES
    )


def extract_session_id_from_stdout(stdout_text: str) -> str | None:
    """Return the first ``session_id`` found in Claude JSON stdout.

    ::

        '{"type":"result","session_id":"abc","result":"ok"}'
            -> "abc"
        'not json'
            -> None

    Accepts a single JSON object or NDJSON event lines. The first non-empty
    string value under the ``session_id`` key wins.

    Args:
        stdout_text: Captured stdout from a Claude ``--output-format json`` run.

    Returns:
        The session id string, or ``None`` when none is present.
    """
    stripped_stdout = stdout_text.strip()
    if not stripped_stdout:
        return None
    maybe_session_id = _session_id_from_json_text(stripped_stdout)
    if maybe_session_id is not None:
        return maybe_session_id
    for each_line in stripped_stdout.splitlines():
        stripped_line = each_line.strip()
        if not stripped_line:
            continue
        maybe_session_id = _session_id_from_json_text(stripped_line)
        if maybe_session_id is not None:
            return maybe_session_id
    return None


def _session_id_from_json_text(json_text: str) -> str | None:
    try:
        parsed_payload = json.loads(json_text)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed_payload, dict):
        return None
    raw_session_id = parsed_payload.get(SESSION_ID_JSON_KEY)
    if isinstance(raw_session_id, str) and raw_session_id:
        return raw_session_id
    return None


@dataclass(frozen=True)
class AffinityBinding:
    """One session-id to chain-binary binding."""

    session_id: str
    command: str


@dataclass(frozen=True)
class AffinityStore:
    """Versioned, bounded session-to-binary affinity document."""

    schema_version: int = AFFINITY_STATE_SCHEMA_VERSION
    all_bindings: list[AffinityBinding] = field(default_factory=list)


def default_affinity_state_path(claude_home_directory: Path) -> Path:
    """Return the default affinity state path under a Claude home directory.

    Args:
        claude_home_directory: Claude configuration root (for example ``~/.claude``).

    Returns:
        Path to the affinity state JSON file.
    """
    return claude_home_directory / AFFINITY_STATE_FILENAME


def _affinity_corrupt_error(state_path: Path, error: object) -> ValueError:
    return ValueError(
        AFFINITY_CORRUPT_MESSAGE_TEMPLATE.format(
            state_path=state_path,
            error=error,
        )
    )


def _parse_affinity_binding(
    each_binding: object,
    *,
    state_path: Path,
) -> AffinityBinding:
    if not isinstance(each_binding, dict):
        raise _affinity_corrupt_error(state_path, AFFINITY_BINDING_NOT_OBJECT_REASON)
    session_id = each_binding.get(AFFINITY_KEY_SESSION_ID)
    command = each_binding.get(AFFINITY_KEY_COMMAND)
    if not isinstance(session_id, str) or not session_id:
        raise _affinity_corrupt_error(
            state_path, AFFINITY_BINDING_SESSION_ID_MISSING_REASON
        )
    if not isinstance(command, str) or not command:
        raise _affinity_corrupt_error(
            state_path, AFFINITY_BINDING_COMMAND_MISSING_REASON
        )
    return AffinityBinding(session_id=session_id, command=command)


def _bindings_from_payload(
    all_payload_fields: dict[str, object],
    *,
    state_path: Path,
) -> list[AffinityBinding]:
    schema_version = all_payload_fields.get(AFFINITY_KEY_SCHEMA_VERSION)
    if schema_version != AFFINITY_STATE_SCHEMA_VERSION:
        raise _affinity_corrupt_error(
            state_path,
            AFFINITY_UNSUPPORTED_SCHEMA_VERSION_REASON_TEMPLATE.format(
                schema_version=schema_version
            ),
        )
    raw_bindings = all_payload_fields.get(AFFINITY_KEY_ALL_BINDINGS)
    if not isinstance(raw_bindings, list):
        raise _affinity_corrupt_error(
            state_path, AFFINITY_BINDINGS_MISSING_OR_NOT_LIST_REASON
        )
    return [
        _parse_affinity_binding(each_binding, state_path=state_path)
        for each_binding in raw_bindings
    ]


def load_affinity_store(state_path: Path) -> AffinityStore:
    """Load a versioned affinity store, or an empty store when the file is absent.

    Args:
        state_path: Path to the affinity state JSON file.

    Returns:
        Parsed affinity store.

    Raises:
        ValueError: When the document is corrupt or uses an unsupported schema.
    """
    if not state_path.is_file():
        return AffinityStore()
    try:
        raw_text = state_path.read_text(encoding=UTF8_ENCODING)
        parsed_payload = json.loads(raw_text)
    except (OSError, json.JSONDecodeError, UnicodeError) as load_error:
        raise _affinity_corrupt_error(state_path, load_error) from load_error
    if not isinstance(parsed_payload, dict):
        raise _affinity_corrupt_error(
            state_path, AFFINITY_TOP_LEVEL_NOT_OBJECT_REASON
        )
    return AffinityStore(
        schema_version=AFFINITY_STATE_SCHEMA_VERSION,
        all_bindings=_bindings_from_payload(parsed_payload, state_path=state_path),
    )


def record_affinity_binding(
    store: AffinityStore,
    *,
    session_id: str,
    command: str,
    maximum_entries: int = AFFINITY_MAXIMUM_ENTRIES,
) -> AffinityStore:
    """Return a new store with ``session_id`` bound to ``command``, bounded.

    Re-binding an existing session moves it to the newest end. When the store
    exceeds ``maximum_entries``, the oldest bindings drop first.

    Args:
        store: Current affinity store.
        session_id: Claude session id to bind.
        command: Chain binary command that served the session.
        maximum_entries: Hard cap on retained bindings.

    Returns:
        Updated store (does not mutate ``store``).

    Raises:
        ValueError: When session_id, command, or maximum_entries is invalid.
    """
    if not session_id or not command:
        raise ValueError(AFFINITY_SESSION_ID_AND_COMMAND_REQUIRED_MESSAGE)
    if maximum_entries < 1:
        raise ValueError(AFFINITY_MAXIMUM_ENTRIES_MINIMUM_MESSAGE)
    all_remaining = [
        each_binding
        for each_binding in store.all_bindings
        if each_binding.session_id != session_id
    ]
    all_remaining.append(AffinityBinding(session_id=session_id, command=command))
    if len(all_remaining) > maximum_entries:
        all_remaining = all_remaining[-maximum_entries:]
    return AffinityStore(
        schema_version=AFFINITY_STATE_SCHEMA_VERSION,
        all_bindings=all_remaining,
    )


def save_affinity_store_atomic(state_path: Path, store: AffinityStore) -> None:
    """Atomically replace the affinity state file with ``store``.

    Creates a unique sibling temporary file via ``tempfile.mkstemp``, writes
    and flushes the document, then uses ``os.replace`` so readers never
    observe a partial document.

    Args:
        state_path: Destination affinity state path.
        store: Store document to persist.

    Raises:
        OSError: When the write or replace fails (message is actionable).
    """
    payload = {
        AFFINITY_KEY_SCHEMA_VERSION: store.schema_version,
        AFFINITY_KEY_ALL_BINDINGS: [
            {
                AFFINITY_KEY_SESSION_ID: each_binding.session_id,
                AFFINITY_KEY_COMMAND: each_binding.command,
            }
            for each_binding in store.all_bindings
        ],
    }
    serialized_document = (
        json.dumps(payload, indent=AFFINITY_JSON_INDENT_SPACES, sort_keys=True)
        + "\n"
    )
    state_path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{state_path.name}.",
        suffix=AFFINITY_TEMP_SUFFIX,
        dir=state_path.parent,
    )
    temporary_path = Path(temporary_name)
    owned_descriptor = file_descriptor
    try:
        with os.fdopen(file_descriptor, "w", encoding=UTF8_ENCODING) as temporary_file:
            owned_descriptor = -1
            temporary_file.write(serialized_document)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_path, state_path)
    except OSError as write_error:
        if owned_descriptor >= 0:
            try:
                os.close(owned_descriptor)
            except OSError:
                pass
        try:
            temporary_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise OSError(
            AFFINITY_WRITE_FAILED_MESSAGE_TEMPLATE.format(
                state_path=state_path,
                error=write_error,
            )
        ) from write_error


def _served_outcome(
    served_command: str,
    completion: subprocess.CompletedProcess[str],
    all_attempts: list[ChainAttempt],
) -> ChainInvocationOutcome:
    maybe_session_id = None
    if completion.returncode == 0:
        maybe_session_id = extract_session_id_from_stdout(completion.stdout)
    return ChainInvocationOutcome(
        served_command=served_command,
        returncode=completion.returncode,
        stdout=completion.stdout,
        stderr=completion.stderr,
        attempts=tuple(all_attempts),
        terminal_status=TERMINAL_STATUS_SERVED,
        session_id=maybe_session_id,
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
    *,
    terminal_status: str,
) -> ChainInvocationOutcome:
    captured_stdout, captured_stderr = _timeout_streams(timeout_error)
    return ChainInvocationOutcome(
        served_command=None,
        returncode=NO_COMPLETED_PROCESS_RETURN_CODE,
        stdout=captured_stdout,
        stderr=captured_stderr,
        attempts=tuple(all_attempts),
        terminal_status=terminal_status,
        session_id=None,
    )


def _advisor_blocked_outcome(
    completion: subprocess.CompletedProcess[str],
    all_attempts: list[ChainAttempt],
) -> ChainInvocationOutcome:
    return ChainInvocationOutcome(
        served_command=None,
        returncode=completion.returncode,
        stdout=completion.stdout,
        stderr=completion.stderr,
        attempts=tuple(all_attempts),
        terminal_status=TERMINAL_STATUS_ADVISOR_BLOCKED,
        session_id=None,
    )


def _exhausted_outcome(
    all_attempts: list[ChainAttempt],
    last_usage_limited: subprocess.CompletedProcess[str] | None,
) -> ChainInvocationOutcome:
    if last_usage_limited is None:
        return _no_process_outcome(
            all_attempts,
            None,
            terminal_status=TERMINAL_STATUS_CHAIN_EXHAUSTED,
        )
    return ChainInvocationOutcome(
        served_command=None,
        returncode=last_usage_limited.returncode,
        stdout=last_usage_limited.stdout,
        stderr=last_usage_limited.stderr,
        attempts=tuple(all_attempts),
        terminal_status=TERMINAL_STATUS_CHAIN_EXHAUSTED,
        session_id=None,
    )


def _classify_completion(
    entry: ChainEntry,
    completion: subprocess.CompletedProcess[str],
    all_attempts: list[ChainAttempt],
    *,
    routing_mode: str,
) -> ChainInvocationOutcome | None:
    if completion.returncode == 0:
        all_attempts.append(ChainAttempt(entry.command, ATTEMPT_STATUS_SERVED))
        return _served_outcome(entry.command, completion, all_attempts)
    if _is_usage_limit_failure(completion):
        all_attempts.append(ChainAttempt(entry.command, ATTEMPT_STATUS_USAGE_LIMITED))
        return None
    all_attempts.append(ChainAttempt(entry.command, ATTEMPT_STATUS_NONZERO_EXIT))
    if routing_mode == ROUTING_MODE_ORDERED_ACCOUNT:
        return _advisor_blocked_outcome(completion, all_attempts)
    return _served_outcome(entry.command, completion, all_attempts)


def _ranked_entries_or_config_order(
    all_entries: list[ChainEntry],
    config_path: Path,
) -> list[ChainEntry]:
    try:
        all_usage_reports = chain_weekly_usage_reporter(config_path=config_path)
        return _entries_ranked_by_weekly_remaining(
            all_entries, all_usage_reports
        )
    except (ImportError, AttributeError):
        return list(all_entries)


def _resolve_walk_entries(
    all_entries: list[ChainEntry],
    config_path: Path,
    routing_mode: str,
) -> list[ChainEntry]:
    if routing_mode == ROUTING_MODE_ORDERED_ACCOUNT:
        return list(all_entries)
    return _ranked_entries_or_config_order(all_entries, config_path)


def _require_known_routing_mode(routing_mode: str) -> str:
    if routing_mode not in ALL_ROUTING_MODES:
        raise ValueError(
            f"Unknown routing_mode {routing_mode!r}; "
            f"expected one of {sorted(ALL_ROUTING_MODES)}"
        )
    return routing_mode


def run_claude(
    all_claude_arguments: list[str],
    *,
    timeout_seconds: int,
    stdin_text: str | None = None,
    routing_mode: str = DEFAULT_ROUTING_MODE,
) -> ChainInvocationOutcome:
    """Run *all_claude_arguments* through the fallback chain.

    ::

        usage_ranked (default): highest remaining first
        ordered_account: config order; usage-limit-only fallover
        ordered_account + auth/timeout/generic process error
            -> terminal_status=advisor_blocked (no fallover)
        zero exit with JSON session_id
            -> outcome.session_id set for later --resume

    Default mode probes weekly remaining once, ranks highest first, then walks
    that order. Ordered-account mode walks config order and never probes usage.
    Only a usage-limit failure falls over. Missing binaries are skipped and the
    walk continues; timeout and other nonzero exits stop. In ordered-account
    mode those non-usage stops report ``advisor_blocked``. When usage ranking
    infrastructure fails to load under usage-ranked mode, the walk uses config
    order instead.

    Args:
        all_claude_arguments: Arguments passed after the binary name, such as
            ``["-p", prompt, "--strict-mcp-config"]``.
        timeout_seconds: Timeout applied to each binary invocation.
        stdin_text: Optional UTF-8 text forwarded as stdin to every binary.
            ``None`` leaves the subprocess without a piped stdin body.
        routing_mode: ``usage_ranked`` (default) or ``ordered_account``.

    Returns:
        The outcome of the walk, naming the serving binary, terminal status,
        optional session id, and the full attempt trail.

    Raises:
        ChainConfigurationError: When the chain configuration cannot be loaded.
        ValueError: When *routing_mode* is not a known mode.
    """
    selected_routing_mode = _require_known_routing_mode(routing_mode)
    config_path = chain_config_path()
    all_entries = load_chain(config_path)
    all_walk_entries = _resolve_walk_entries(
        all_entries, config_path, selected_routing_mode
    )
    all_attempts: list[ChainAttempt] = []
    last_usage_limited: subprocess.CompletedProcess[str] | None = None
    for each_entry in all_walk_entries:
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
            timeout_terminal_status = (
                TERMINAL_STATUS_ADVISOR_BLOCKED
                if selected_routing_mode == ROUTING_MODE_ORDERED_ACCOUNT
                else TERMINAL_STATUS_TIMEOUT
            )
            return _no_process_outcome(
                all_attempts,
                timeout_error,
                terminal_status=timeout_terminal_status,
            )
        except FileNotFoundError:
            all_attempts.append(
                ChainAttempt(each_entry.command, ATTEMPT_STATUS_EXECUTABLE_NOT_FOUND)
            )
            continue
        terminal_outcome = _classify_completion(
            each_entry,
            completion,
            all_attempts,
            routing_mode=selected_routing_mode,
        )
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
    parser.add_argument(
        CLI_ROUTING_MODE_FLAG,
        dest="routing_mode",
        choices=sorted(ALL_ROUTING_MODES),
        default=DEFAULT_ROUTING_MODE,
        help=(
            "Chain routing: usage_ranked (default) or ordered_account "
            "(config order, usage-limit-only fallover)."
        ),
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

    ::

        main(["--", "-p", "hi"])
        main(["--routing-mode", "ordered_account", "--", "-p", "hi"])

    Args:
        all_command_arguments: The argument vector after the program name.

    Returns:
        The served binary's return code, a distinct code when the chain is
        exhausted or advisor-blocked, or a distinct code when the configuration
        cannot be loaded.
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
            routing_mode=parsed_arguments.routing_mode,
        )
    except ChainConfigurationError as configuration_error:
        print(str(configuration_error), file=sys.stderr)
        return CHAIN_CONFIG_ERROR_EXIT_CODE
    if chain_outcome.terminal_status == TERMINAL_STATUS_ADVISOR_BLOCKED:
        sys.stdout.write(chain_outcome.stdout)
        sys.stderr.write(chain_outcome.stderr)
        return CHAIN_ADVISOR_BLOCKED_EXIT_CODE
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
