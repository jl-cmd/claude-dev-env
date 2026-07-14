#!/usr/bin/env python3
"""Report remaining weekly Codex usage as machine-readable JSON.

Discovery (codex-cli 0.144.3): no dedicated ``codex usage`` subcommand.
``codex login status`` prints auth only. Weekly meters come from the
app-server JSON-RPC method ``account/rateLimits/read`` via
``codex app-server --listen stdio://``. The weekly window is the rate-limit
window whose ``windowDurationMins`` is 10080 (seven days), preferring
``secondary`` when both primary and secondary carry that duration.

stdout is one JSON object ``{percent_left, window_reset, source}``.
``percent_left`` is 0-100, or null when the binary offers no usage data.
Exit 0 when the probe completed against a reachable CLI (including null
data). Exit non-zero when the Codex CLI is missing or broken, or when the
probe itself crashes — consumers must not treat that as a usage-threshold
skip.

Gate rule for consumers: null or unknown ``percent_left`` on exit 0 counts
as at-or-below ``WEEKLY_USAGE_GATE_THRESHOLD_PERCENT`` — the gate may skip
and never blocks on missing meters. A non-zero probe exit is CLI failure
(classify ``codex_down`` or fail closed), not a threshold skip. Require
review only when exit 0 and ``is_codex_review_required(percent_left)``.

::

    python codex_usage_probe.py
    {"percent_left": 5, "window_reset": "2026-07-19T23:49:08+00:00",
     "source": "codex app-server account/rateLimits/read"}
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import sys
import threading
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import IO, Protocol

from codex_review_scripts_constants.codex_usage_probe_constants import (
    ALL_APP_SERVER_COMMAND_PARTS,
    ALL_WINDOWS_SCRIPT_SUFFIXES,
    APP_SERVER_TIMEOUT_SECONDS,
    CAPABILITIES_KEY,
    CLIENT_INFO_KEY,
    CLIENT_INFO_NAME,
    CLIENT_INFO_NAME_KEY,
    CLIENT_INFO_VERSION,
    CLIENT_INFO_VERSION_KEY,
    CODEX_BINARY_NAME,
    EXIT_CODE_CRASH,
    EXIT_CODE_SUCCESS,
    EXPERIMENTAL_API_KEY,
    INITIALIZE_REQUEST_ID,
    JSONRPC_KEY_ERROR,
    JSONRPC_KEY_ID,
    JSONRPC_KEY_METHOD,
    JSONRPC_KEY_PARAMS,
    JSONRPC_KEY_REPLY_BODY,
    JSONRPC_KEY_VERSION,
    JSONRPC_VERSION,
    METHOD_INITIALIZE,
    METHOD_INITIALIZED,
    METHOD_RATE_LIMITS_READ,
    NEWLINE,
    PERCENT_EMPTY,
    PERCENT_FULL,
    PRIMARY_WINDOW_KEY,
    PROCESS_TREE_WAIT_TIMEOUT_SECONDS,
    RATE_LIMITS_KEY,
    RATE_LIMITS_REQUEST_ID,
    READER_THREAD_JOIN_TIMEOUT_SECONDS,
    RESETS_AT_KEY,
    SECONDARY_WINDOW_KEY,
    SOURCE_APP_SERVER_RATE_LIMITS,
    SOURCE_NO_USAGE_SURFACE,
    SOURCE_TEXT_STATUS,
    TEXT_WEEKLY_PERCENT_LEFT_PATTERN,
    TEXT_WEEKLY_USED_PERCENT_PATTERN,
    TEXT_WINDOW_RESET_PATTERN,
    USAGE_REPORT_KEY_PERCENT_LEFT,
    USAGE_REPORT_KEY_SOURCE,
    USAGE_REPORT_KEY_WINDOW_RESET,
    USED_PERCENT_KEY,
    UTF8_ENCODING,
    WEEKLY_USAGE_GATE_THRESHOLD_PERCENT,
    WEEKLY_WINDOW_DURATION_MINUTES,
    WINDOW_DURATION_MINS_KEY,
    WINDOWS_COMMAND_SHELL,
    WINDOWS_COMMAND_SHELL_RUN_FLAG,
    WINDOWS_OS_NAME,
    WINDOWS_TASKKILL_COMMAND,
    WINDOWS_TASKKILL_FORCE_FLAG,
    WINDOWS_TASKKILL_PID_FLAG,
    WINDOWS_TASKKILL_TREE_FLAG,
)


class AppServerExchange(Protocol):
    """Callable that sends JSON-RPC request objects and returns stdout lines."""

    def __call__(
        self, all_request_messages: list[dict[str, object]]
    ) -> list[str]:
        """Exchange request messages for server stdout lines.

        Args:
            all_request_messages: JSON-RPC request/notification objects to send.

        Returns:
            Raw stdout lines from the app-server process.
        """


UsageReport = dict[str, float | str | None]


def is_codex_review_required(percent_left: float | None) -> bool:
    """Return whether the weekly gate should require a Codex review pass.

    ::

        None -> False   # missing data never blocks
        10.0 -> False   # at threshold: skip
        10.1 -> True    # above threshold: require

    Args:
        percent_left: Weekly percent remaining, or None when unknown.

    Returns:
        True only when percent_left is known and strictly greater than
        WEEKLY_USAGE_GATE_THRESHOLD_PERCENT.
    """
    if percent_left is None:
        return False
    return percent_left > WEEKLY_USAGE_GATE_THRESHOLD_PERCENT


def _null_usage_report() -> UsageReport:
    return {
        USAGE_REPORT_KEY_PERCENT_LEFT: None,
        USAGE_REPORT_KEY_WINDOW_RESET: None,
        USAGE_REPORT_KEY_SOURCE: SOURCE_NO_USAGE_SURFACE,
    }


def _clamp_percent(raw_percent: float) -> float:
    return max(float(PERCENT_EMPTY), min(float(PERCENT_FULL), raw_percent))


def _format_resets_at(raw_resets_at: object) -> str | None:
    if isinstance(raw_resets_at, bool):
        return None
    if isinstance(raw_resets_at, (int, float)):
        if not math.isfinite(raw_resets_at):
            return None
        try:
            return datetime.fromtimestamp(
                float(raw_resets_at), tz=timezone.utc
            ).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(raw_resets_at, str):
        stripped = raw_resets_at.strip()
        return stripped or None
    return None


def _window_used_percent(all_window_fields: Mapping[str, object]) -> float | None:
    raw_used_percent = all_window_fields.get(USED_PERCENT_KEY)
    if isinstance(raw_used_percent, bool):
        return None
    if isinstance(raw_used_percent, (int, float)):
        if not math.isfinite(raw_used_percent):
            return None
        return float(raw_used_percent)
    return None


def _window_duration_minutes(
    all_window_fields: Mapping[str, object],
) -> int | None:
    raw_duration = all_window_fields.get(WINDOW_DURATION_MINS_KEY)
    if isinstance(raw_duration, bool):
        return None
    if isinstance(raw_duration, (int, float)):
        if not math.isfinite(raw_duration):
            return None
        return int(raw_duration)
    return None


def _select_weekly_window(
    all_rate_limit_fields: Mapping[str, object],
) -> Mapping[str, object] | None:
    primary_payload = all_rate_limit_fields.get(PRIMARY_WINDOW_KEY)
    secondary_payload = all_rate_limit_fields.get(SECONDARY_WINDOW_KEY)
    all_candidate_windows: list[Mapping[str, object]] = []
    if isinstance(secondary_payload, Mapping):
        all_candidate_windows.append(secondary_payload)
    if isinstance(primary_payload, Mapping):
        all_candidate_windows.append(primary_payload)
    if not all_candidate_windows:
        return None
    for each_window in all_candidate_windows:
        if _window_duration_minutes(each_window) == WEEKLY_WINDOW_DURATION_MINUTES:
            return each_window
    return None


def _usage_report_from_window(
    all_weekly_window_fields: Mapping[str, object],
    source: str,
) -> UsageReport:
    used_percent = _window_used_percent(all_weekly_window_fields)
    if used_percent is None:
        return _null_usage_report()
    percent_left = _clamp_percent(float(PERCENT_FULL) - used_percent)
    return {
        USAGE_REPORT_KEY_PERCENT_LEFT: percent_left,
        USAGE_REPORT_KEY_WINDOW_RESET: _format_resets_at(
            all_weekly_window_fields.get(RESETS_AT_KEY)
        ),
        USAGE_REPORT_KEY_SOURCE: source,
    }


def _parse_rate_limits_snapshot(
    all_rate_limit_fields: Mapping[str, object],
) -> UsageReport:
    weekly_window = _select_weekly_window(all_rate_limit_fields)
    if weekly_window is None:
        return _null_usage_report()
    return _usage_report_from_window(weekly_window, SOURCE_APP_SERVER_RATE_LIMITS)


def parse_rate_limits_message(message_text: str) -> UsageReport:
    """Parse one JSON-RPC reply line that may carry rateLimits.

    Args:
        message_text: A single stdout line from ``codex app-server``.

    Returns:
        The usage report, or a null report when the line has no usable meters.
    """
    try:
        message_payload = json.loads(message_text)
    except json.JSONDecodeError:
        return _null_usage_report()
    if not isinstance(message_payload, dict):
        return _null_usage_report()
    if message_payload.get(JSONRPC_KEY_ERROR) is not None:
        return _null_usage_report()
    reply_body = message_payload.get(JSONRPC_KEY_REPLY_BODY)
    if not isinstance(reply_body, dict):
        return _null_usage_report()
    all_rate_limit_fields = reply_body.get(RATE_LIMITS_KEY)
    if not isinstance(all_rate_limit_fields, dict):
        return _null_usage_report()
    return _parse_rate_limits_snapshot(all_rate_limit_fields)


def _text_status_report(
    percent_left: float,
    status_text: str,
    search_from_index: int,
) -> UsageReport:
    weekly_scoped_text = status_text[search_from_index:]
    reset_match = re.search(TEXT_WINDOW_RESET_PATTERN, weekly_scoped_text)
    window_reset = (
        reset_match.group("reset").strip() if reset_match is not None else None
    )
    return {
        USAGE_REPORT_KEY_PERCENT_LEFT: percent_left,
        USAGE_REPORT_KEY_WINDOW_RESET: window_reset,
        USAGE_REPORT_KEY_SOURCE: SOURCE_TEXT_STATUS,
    }


def parse_text_usage_status(status_text: str) -> UsageReport:
    """Parse human status text for a weekly percent remaining.

    Args:
        status_text: Captured CLI or TUI status text.

    Returns:
        The usage report when a weekly percent pattern matches, else null.
    """
    left_match = re.search(TEXT_WEEKLY_PERCENT_LEFT_PATTERN, status_text)
    if left_match is not None:
        percent_left = _clamp_percent(float(left_match.group("percent")))
        return _text_status_report(
            percent_left,
            status_text,
            search_from_index=left_match.start(),
        )
    used_match = re.search(TEXT_WEEKLY_USED_PERCENT_PATTERN, status_text)
    if used_match is not None:
        percent_left = _clamp_percent(
            float(PERCENT_FULL) - float(used_match.group("percent"))
        )
        return _text_status_report(
            percent_left,
            status_text,
            search_from_index=used_match.start(),
        )
    return _null_usage_report()


def _build_app_server_request_messages() -> list[dict[str, object]]:
    initialize_request: dict[str, object] = {
        JSONRPC_KEY_VERSION: JSONRPC_VERSION,
        JSONRPC_KEY_ID: INITIALIZE_REQUEST_ID,
        JSONRPC_KEY_METHOD: METHOD_INITIALIZE,
        JSONRPC_KEY_PARAMS: {
            CLIENT_INFO_KEY: {
                CLIENT_INFO_NAME_KEY: CLIENT_INFO_NAME,
                CLIENT_INFO_VERSION_KEY: CLIENT_INFO_VERSION,
            },
            CAPABILITIES_KEY: {EXPERIMENTAL_API_KEY: True},
        },
    }
    initialized_notification: dict[str, object] = {
        JSONRPC_KEY_VERSION: JSONRPC_VERSION,
        JSONRPC_KEY_METHOD: METHOD_INITIALIZED,
        JSONRPC_KEY_PARAMS: {},
    }
    rate_limits_request: dict[str, object] = {
        JSONRPC_KEY_VERSION: JSONRPC_VERSION,
        JSONRPC_KEY_ID: RATE_LIMITS_REQUEST_ID,
        JSONRPC_KEY_METHOD: METHOD_RATE_LIMITS_READ,
        JSONRPC_KEY_PARAMS: {},
    }
    return [initialize_request, initialized_notification, rate_limits_request]


def _resolve_codex_command() -> list[str]:
    codex_path = shutil.which(CODEX_BINARY_NAME)
    if codex_path is None:
        raise FileNotFoundError(f"{CODEX_BINARY_NAME} binary not found on PATH")
    lower_path = codex_path.lower()
    if os.name == WINDOWS_OS_NAME and lower_path.endswith(
        ALL_WINDOWS_SCRIPT_SUFFIXES
    ):
        return [
            WINDOWS_COMMAND_SHELL,
            WINDOWS_COMMAND_SHELL_RUN_FLAG,
            codex_path,
            *ALL_APP_SERVER_COMMAND_PARTS,
        ]
    return [codex_path, *ALL_APP_SERVER_COMMAND_PARTS]


def _is_rate_limits_reply(message_text: str) -> bool:
    """Return whether a stdout line is the reply to our rate-limits request."""
    try:
        message_payload = json.loads(message_text)
    except json.JSONDecodeError:
        return False
    if not isinstance(message_payload, dict):
        return False
    return message_payload.get(JSONRPC_KEY_ID) == RATE_LIMITS_REQUEST_ID


def _collect_server_lines(
    server_stdout: IO[str],
    all_server_lines: list[str],
    is_exchange_over: threading.Event,
) -> None:
    """Append server stdout lines until the rate-limits reply lands or stdout ends."""
    try:
        for each_line in server_stdout:
            stripped_line = each_line.strip()
            if not stripped_line:
                continue
            all_server_lines.append(stripped_line)
            if _is_rate_limits_reply(stripped_line):
                break
    except (OSError, ValueError):
        pass
    is_exchange_over.set()


def _terminate_process_tree(server_process: subprocess.Popen[str]) -> None:
    """Stop the app-server process and any children it launched.

    On Windows the probe may wrap a ``.cmd``/``.bat`` shim as ``cmd /c``, so
    ``Popen.pid`` is ``cmd.exe``. Killing only that process leaves the real
    Codex app-server grandchild alive and holding stdout. ``taskkill /T``
    tears down the whole tree; other platforms use ``kill()``.
    """
    if server_process.poll() is not None:
        return
    process_id = server_process.pid
    if process_id is None:
        return
    if os.name == WINDOWS_OS_NAME:
        subprocess.run(
            [
                WINDOWS_TASKKILL_COMMAND,
                WINDOWS_TASKKILL_FORCE_FLAG,
                WINDOWS_TASKKILL_TREE_FLAG,
                WINDOWS_TASKKILL_PID_FLAG,
                str(process_id),
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            server_process.wait(timeout=PROCESS_TREE_WAIT_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            server_process.kill()
        return
    server_process.kill()
    try:
        server_process.wait(timeout=PROCESS_TREE_WAIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        pass


def _teardown_app_server_exchange(
    server_process: subprocess.Popen[str],
    reader_thread: threading.Thread,
) -> None:
    """Terminate the process tree, then join the stdout reader before return."""
    _terminate_process_tree(server_process)
    reader_thread.join(timeout=READER_THREAD_JOIN_TIMEOUT_SECONDS)


def _exchange_app_server_messages_via_subprocess(
    all_request_messages: list[dict[str, object]],
) -> list[str]:
    """Run ``codex app-server`` and collect its replies to the probe's requests.

    ::

        write requests -> stdin stays OPEN -> server answers -> read reply -> close

    The server treats end-of-input on stdin as a shutdown signal, so it exits
    without answering when stdin closes right after the requests are written.
    Stdin is held open until the rate-limits reply arrives or the timeout runs
    out, then the process tree is torn down and the stdout reader is joined.

    Args:
        all_request_messages: JSON-RPC request/notification objects to send.

    Returns:
        The non-empty stdout lines the server emitted before the exchange ended.
    """
    all_command_parts = _resolve_codex_command()
    stdin_text = NEWLINE.join(
        json.dumps(each_message) for each_message in all_request_messages
    ) + NEWLINE
    all_server_lines: list[str] = []
    is_exchange_over = threading.Event()
    with subprocess.Popen(
        all_command_parts,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding=UTF8_ENCODING,
        shell=False,
    ) as server_process:
        server_stdin = server_process.stdin
        server_stdout = server_process.stdout
        if server_stdin is None or server_stdout is None:
            _terminate_process_tree(server_process)
            raise OSError("codex app-server offered no stdio pipes")
        reader_thread = threading.Thread(
            target=_collect_server_lines,
            args=(server_stdout, all_server_lines, is_exchange_over),
            daemon=True,
        )
        reader_thread.start()
        try:
            server_stdin.write(stdin_text)
            server_stdin.flush()
            is_exchange_over.wait(timeout=APP_SERVER_TIMEOUT_SECONDS)
        finally:
            _teardown_app_server_exchange(
                server_process=server_process,
                reader_thread=reader_thread,
            )
    return list(all_server_lines)


def _usage_report_from_server_lines(all_server_lines: Sequence[str]) -> UsageReport:
    for each_line in all_server_lines:
        usage_report = parse_rate_limits_message(each_line)
        if usage_report[USAGE_REPORT_KEY_PERCENT_LEFT] is not None:
            return usage_report
    return _null_usage_report()


def probe_weekly_usage(
    exchange_app_server_messages: AppServerExchange,
) -> UsageReport:
    """Probe weekly Codex usage through the app-server rate-limits surface.

    Args:
        exchange_app_server_messages: JSON-RPC exchange seam. Production passes
            the real subprocess exchange; tests inject a fake.

    Returns:
        The usage report with percent_left, window_reset, and source.
    """
    all_request_messages = _build_app_server_request_messages()
    all_server_lines = exchange_app_server_messages(all_request_messages)
    return _usage_report_from_server_lines(all_server_lines)


def probe_weekly_usage_via_subprocess() -> UsageReport:
    """Probe weekly usage against the real ``codex app-server`` subprocess.

    ::

        probe_weekly_usage_via_subprocess()
        # ok: {"percent_left": 62.0, "window_reset": ..., "source": ...}

    The production entry point for every caller that has no exchange seam of
    its own to inject.

    Returns:
        The usage report with percent_left, window_reset, and source.
    """
    return probe_weekly_usage(
        exchange_app_server_messages=_exchange_app_server_messages_via_subprocess
    )


def main() -> int:
    """Run the probe and print one JSON object on stdout.

    ::

        reachable CLI, meters present  -> exit 0, percent_left number
        reachable CLI, no meters       -> exit 0, percent_left null  (usage skip ok)
        missing or broken CLI          -> exit non-zero  (not a usage skip)

    Returns:
        EXIT_CODE_SUCCESS on a completed probe against a reachable CLI
        (including null data), or EXIT_CODE_CRASH when the Codex CLI is
        missing or broken or the probe itself fails.
    """
    try:
        usage_report = probe_weekly_usage(
            exchange_app_server_messages=_exchange_app_server_messages_via_subprocess
        )
    except (
        FileNotFoundError,
        OSError,
        subprocess.TimeoutExpired,
        subprocess.SubprocessError,
        UnicodeDecodeError,
    ):
        print(json.dumps(_null_usage_report()))
        return EXIT_CODE_CRASH
    except (json.JSONDecodeError, ValueError, TypeError, KeyError):
        print(json.dumps(_null_usage_report()))
        return EXIT_CODE_CRASH
    print(json.dumps(usage_report))
    return EXIT_CODE_SUCCESS


if __name__ == "__main__":
    sys.exit(main())
