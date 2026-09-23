#!/usr/bin/env python3
"""Read one Codex account's rate-limit windows from its own Codex home.

Codex reports usage through ``codex app-server`` and the JSON-RPC method
``account/rateLimits/read``. The reply names up to two windows, a short one
(5 hours) and a weekly one. The account's room is the smaller of the two::

    5-hour window 30% used, week 85% used  -> 15% left
    week window only, 40% used             -> 60% left
    no window, error reply, no reply       -> CodexMeterUnreadError

Every failure raises ``CodexMeterUnreadError``. The caller decides what an
unread account means; this module never guesses a number.
"""

from __future__ import annotations

import importlib
import json
import math
import os
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import IO

from dev_env_scripts_constants.codex_account_constants import (
    ALL_APP_SERVER_ARGUMENTS,
    ALL_CODEX_BINARY_CANDIDATE_RELATIVE_PARTS,
    ALL_WINDOW_KEYS,
    APP_SERVER_TIMEOUT_SECONDS,
    CLIENT_NAME,
    CLIENT_VERSION,
    CODEX_BINARY_NAME,
    CODEX_HOME_ENVIRONMENT_VARIABLE,
    FULL_PERCENT,
    INITIALIZE_REQUEST_ID,
    JSONRPC_VERSION,
    METHOD_INITIALIZE,
    METHOD_INITIALIZED,
    METHOD_RATE_LIMITS_READ,
    PROCESS_WAIT_TIMEOUT_SECONDS,
    RATE_LIMITS_REQUEST_ID,
    READER_JOIN_TIMEOUT_SECONDS,
    TEXT_ENCODING,
)
from shared_tree_paths import resolve_shared_process_tree_scripts_directory

_shared_process_tree_scripts_directory = resolve_shared_process_tree_scripts_directory(
    __file__,
    all_environment=os.environ,
)
if str(_shared_process_tree_scripts_directory) not in sys.path:
    sys.path.insert(0, str(_shared_process_tree_scripts_directory))

_process_tree_kill = importlib.import_module("process_tree_kill")
_subprocess_window_access = importlib.import_module("subprocess_window_access")

ServerExchange = Callable[[Path, Path, Sequence[Mapping[str, object]]], list[str]]


class CodexMeterUnreadError(Exception):
    """Raised when one account's rate-limit windows cannot be read."""


@dataclass(frozen=True)
class UsageWindow:
    """One rate-limit window: its length, the percent used, and when it resets."""

    duration_minutes: int | None
    used_percent: float
    resets_at: datetime | None


@dataclass(frozen=True)
class CodexAccountMeters:
    """One account's windows, with percent_left and resets_before_room read from them."""

    all_windows: tuple[UsageWindow, ...]

    @property
    def percent_left(self) -> float:
        """Room left in the tightest window, from 0 to 100."""
        most_used = max(each_window.used_percent for each_window in self.all_windows)
        return max(0.0, FULL_PERCENT - most_used)

    def resets_before_room(self, minimum_percent_left: float) -> datetime | None:
        """When every window that holds the account at or under a bar has reset.

        Args:
            minimum_percent_left: The percent left the account must pass.

        Returns:
            The latest reset among the blocking windows, or None when one
            carries no reset time or none blocks.
        """
        all_blocking = [
            each_window
            for each_window in self.all_windows
            if FULL_PERCENT - each_window.used_percent <= minimum_percent_left
        ]
        if not all_blocking or any(
            each_window.resets_at is None for each_window in all_blocking
        ):
            return None
        return max(
            each_window.resets_at
            for each_window in all_blocking
            if each_window.resets_at is not None
        )


def _finite_number(raw_number: object) -> float | None:
    if isinstance(raw_number, bool) or not isinstance(raw_number, (int, float)):
        return None
    if not math.isfinite(raw_number):
        return None
    return float(raw_number)


def _parse_resets_at(raw_resets_at: object) -> datetime | None:
    seconds = _finite_number(raw_resets_at)
    if seconds is None:
        return None
    try:
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def _parse_window(raw_window: object) -> UsageWindow | None:
    if not isinstance(raw_window, Mapping):
        return None
    used_percent = _finite_number(raw_window.get("usedPercent"))
    if used_percent is None:
        return None
    duration = _finite_number(raw_window.get("windowDurationMins"))
    return UsageWindow(
        duration_minutes=None if duration is None else int(duration),
        used_percent=min(FULL_PERCENT, max(0.0, used_percent)),
        resets_at=_parse_resets_at(raw_window.get("resetsAt")),
    )


def _rate_limits_mapping(reply_text: str) -> Mapping[str, object]:
    try:
        reply = json.loads(reply_text)
    except json.JSONDecodeError as error:
        raise CodexMeterUnreadError("rate-limit reply is not JSON") from error
    if not isinstance(reply, dict):
        raise CodexMeterUnreadError("rate-limit reply is not an object")
    if reply.get("error") is not None:
        raise CodexMeterUnreadError(f"rate-limit read failed: {reply['error']}")
    body = reply.get("result")
    rate_limits = body.get("rateLimits") if isinstance(body, dict) else None
    if not isinstance(rate_limits, dict):
        raise CodexMeterUnreadError("rate-limit reply names no rateLimits")
    return rate_limits


def parse_rate_limits_reply(reply_text: str) -> CodexAccountMeters:
    """Parse the server's reply to the rate-limit read.

    ::

        {"id": 2, "result": {"rateLimits": {"primary": {"usedPercent": 30, ...},
                                            "secondary": {"usedPercent": 85, ...}}}}
        -> CodexAccountMeters with two windows, 15% left

    Args:
        reply_text: One line the ``codex app-server`` process wrote.

    Returns:
        The windows the reply carries.

    Raises:
        CodexMeterUnreadError: The line is no reply, an error reply, or names
            no window with a used percent.
    """
    rate_limits = _rate_limits_mapping(reply_text)
    all_windows = tuple(
        each_window
        for each_key in ALL_WINDOW_KEYS
        if (each_window := _parse_window(rate_limits.get(each_key))) is not None
    )
    if not all_windows:
        raise CodexMeterUnreadError("rate-limit reply names no usage window")
    return CodexAccountMeters(all_windows=all_windows)


def request_messages() -> list[dict[str, object]]:
    """Build the handshake and the rate-limit read, in send order.

    Returns:
        The initialize request, the initialized notice, and the read request.
    """
    return [
        {
            "jsonrpc": JSONRPC_VERSION,
            "id": INITIALIZE_REQUEST_ID,
            "method": METHOD_INITIALIZE,
            "params": {
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
                "capabilities": {"experimentalApi": True},
            },
        },
        {"jsonrpc": JSONRPC_VERSION, "method": METHOD_INITIALIZED, "params": {}},
        {
            "jsonrpc": JSONRPC_VERSION,
            "id": RATE_LIMITS_REQUEST_ID,
            "method": METHOD_RATE_LIMITS_READ,
            "params": {},
        },
    ]


def _is_rate_limits_reply(line: str) -> bool:
    try:
        message = json.loads(line)
    except json.JSONDecodeError:
        return False
    return isinstance(message, dict) and message.get("id") == RATE_LIMITS_REQUEST_ID


def _read_until_reply(server_stdout: IO[str], all_lines: list[str]) -> None:
    for each_line in server_stdout:
        stripped = each_line.strip()
        if stripped:
            all_lines.append(stripped)
        if _is_rate_limits_reply(stripped):
            return


def _collect_lines(
    server_stdout: IO[str], all_lines: list[str], is_done: threading.Event
) -> None:
    try:
        _read_until_reply(server_stdout, all_lines)
    except (OSError, ValueError):
        pass
    is_done.set()


def _stop_server(server: subprocess.Popen[str]) -> None:
    _process_tree_kill.terminate_process_tree(server)
    try:
        server.wait(timeout=PROCESS_WAIT_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        return


def _send_and_collect(server: subprocess.Popen[str], input_text: str) -> list[str]:
    if server.stdin is None or server.stdout is None:
        _stop_server(server)
        raise OSError("codex app-server offered no stdio pipes")
    all_lines: list[str] = []
    is_done = threading.Event()
    reader = threading.Thread(
        target=_collect_lines, args=(server.stdout, all_lines, is_done), daemon=True
    )
    reader.start()
    try:
        server.stdin.write(input_text)
        server.stdin.flush()
        is_done.wait(timeout=APP_SERVER_TIMEOUT_SECONDS)
    finally:
        _stop_server(server)
        reader.join(timeout=READER_JOIN_TIMEOUT_SECONDS)
    return list(all_lines)


def exchange_with_app_server(
    codex_path: Path,
    codex_home: Path,
    all_messages: Sequence[Mapping[str, object]],
) -> list[str]:
    """Run ``codex app-server`` under one Codex home and collect the lines it writes.

    Input stays open until the reply lands, since the server quits unanswered on end of input.

    Args:
        codex_path: The Codex executable.
        codex_home: The account's Codex home, passed as ``CODEX_HOME``.
        all_messages: JSON-RPC messages to send.

    Returns:
        The non-empty lines, ending with the rate-limit reply when it came.
    """
    input_text = "".join(json.dumps(each_message) + "\n" for each_message in all_messages)
    with subprocess.Popen(
        [str(codex_path), *ALL_APP_SERVER_ARGUMENTS],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding=TEXT_ENCODING,
        env={**os.environ, CODEX_HOME_ENVIRONMENT_VARIABLE: str(codex_home)},
        start_new_session=_process_tree_kill.should_start_new_session(),
        creationflags=_subprocess_window_access.hidden_window_creation_flags(),
    ) as server:
        return _send_and_collect(server, input_text)


def read_codex_meters(
    codex_path: Path,
    codex_home: Path,
    exchange: ServerExchange = exchange_with_app_server,
) -> CodexAccountMeters:
    """Read one account's windows through the app server under its Codex home.

    Args:
        codex_path: The Codex executable.
        codex_home: The account's Codex home.
        exchange: Sends messages and returns output lines; tests pass a fake.

    Returns:
        The account's windows.

    Raises:
        CodexMeterUnreadError: The server failed, timed out, or sent no usable reply.
    """
    try:
        all_lines = exchange(codex_path, codex_home, request_messages())
    except (OSError, subprocess.SubprocessError, UnicodeDecodeError) as error:
        raise CodexMeterUnreadError(f"codex app-server failed: {error}") from error
    for each_line in all_lines:
        if _is_rate_limits_reply(each_line):
            return parse_rate_limits_reply(each_line)
    raise CodexMeterUnreadError("codex app-server sent no rate-limit reply")


def resolve_codex_path(explicit_path: Path | None) -> Path:
    """Find the Codex executable.

    Args:
        explicit_path: A path the caller named, used as given.

    Returns:
        The named path, else ``codex`` on PATH, else a known install path.

    Raises:
        FileNotFoundError: No Codex executable was found.
    """
    if explicit_path is not None:
        return explicit_path
    on_path = shutil.which(CODEX_BINARY_NAME)
    if on_path is not None:
        return Path(on_path)
    for each_parts in ALL_CODEX_BINARY_CANDIDATE_RELATIVE_PARTS:
        candidate = Path.home().joinpath(*each_parts)
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("no codex executable on PATH or at its install path")
