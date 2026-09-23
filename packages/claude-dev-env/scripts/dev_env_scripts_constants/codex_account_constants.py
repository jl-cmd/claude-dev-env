"""Named constants for the Codex accounts a runner job picks between.

Each account signs in under its own Codex home. The picker reads every
account's rate-limit windows through ``codex app-server`` and names the account
a job runs on, trying the accounts in one fixed order.
"""

from __future__ import annotations

ALL_CODEX_ACCOUNT_NAMES: tuple[str, ...] = ("codex-1", "codex-2", "codex-3", "codex-4")
"""Codex accounts in the order jobs try them. The names say nothing about a plan."""

CODEX_PROFILES_ROOT_DIRECTORY_NAME: str = ".codex-profiles"
"""Directory under the user home that holds one Codex home per account."""

CODEX_PROFILES_ROOT_ENVIRONMENT_VARIABLE: str = "CODEX_PROFILES_ROOT"
"""Environment variable that relocates the Codex profiles root."""

MAIN_CODEX_HOME_DIRECTORY_NAME: str = ".codex"
"""Directory under the user home that holds the shared Codex setup."""

CODEX_HOME_ENVIRONMENT_VARIABLE: str = "CODEX_HOME"
"""Environment variable that points Codex at one account's home."""

CODEX_AUTH_FILE_NAME: str = "auth.json"
"""File in a Codex home that holds that account's sign-in."""

ALL_SHARED_CODEX_HOME_NAMES: frozenset[str] = frozenset(
    {
        "AGENTS.md",
        "config.toml",
        "hooks",
        "hooks.json",
        "plugins",
        "prompts",
        "rules",
        "skills",
    }
)
"""Codex home entries every account shares. Every other entry stays per account."""

NORMAL_TIER_MINIMUM_PERCENT_LEFT: float = 10.0
"""An account runs a job at its normal model only above this percent left."""

LUNA_TIER_STOP_PERCENT_LEFT: float = 1.0
"""A Luna fallback job stops once its account is at or below this percent left."""

FULL_PERCENT: float = 100.0
"""Percent scale ceiling, so percent left is this minus percent used."""

TIER_NORMAL: str = "normal"
"""Picker answer: run the job at its normal model on the named account."""

TIER_LUNA: str = "luna"
"""Picker answer: every account is at or under the bar, so Luna runs the job."""

TIER_WAIT: str = "wait"
"""Picker answer: no account has room, so the job waits."""

ALL_CODEX_BINARY_CANDIDATE_RELATIVE_PARTS: tuple[tuple[str, ...], ...] = (
    ("AppData", "Local", "Programs", "OpenAI", "Codex", "bin", "codex.exe"),
)
"""Install paths under the user home tried when ``codex`` is not on PATH."""

CODEX_BINARY_NAME: str = "codex"
"""Codex command name looked up on PATH."""

ALL_APP_SERVER_ARGUMENTS: tuple[str, ...] = ("app-server", "--listen", "stdio://")
"""Arguments that start Codex as a JSON-RPC server on standard input and output."""

APP_SERVER_TIMEOUT_SECONDS: float = 30.0
"""Longest wait for the rate-limit reply before the read counts as failed."""

READER_JOIN_TIMEOUT_SECONDS: float = 2.0
"""Longest wait for the output reader to finish after the server stops."""

PROCESS_WAIT_TIMEOUT_SECONDS: float = 5.0
"""Longest wait to reap the server after its process tree is stopped."""

JSONRPC_VERSION: str = "2.0"
"""JSON-RPC protocol version on every message."""

INITIALIZE_REQUEST_ID: int = 1
"""Request id of the initialize handshake."""

RATE_LIMITS_REQUEST_ID: int = 2
"""Request id of the rate-limit read."""

METHOD_INITIALIZE: str = "initialize"
"""JSON-RPC method that opens the session."""

METHOD_INITIALIZED: str = "initialized"
"""JSON-RPC notification that confirms the session opened."""

METHOD_RATE_LIMITS_READ: str = "account/rateLimits/read"
"""JSON-RPC method that returns the account's rate-limit windows."""

CLIENT_NAME: str = "codex-account-choice"
"""Client name the handshake reports."""

CLIENT_VERSION: str = "1.0.0"
"""Client version the handshake reports."""

ALL_WINDOW_KEYS: tuple[str, ...] = ("primary", "secondary")
"""Keys under ``rateLimits`` that each hold one usage window."""

EXIT_CODE_ROOM: int = 0
"""Check answer: the account is above the floor."""

EXIT_CODE_NO_ROOM: int = 3
"""Check answer: the account is at or below the floor, or its meter is unread."""

REASON_NORMAL_TEMPLATE: str = "{account} has {percent_left:.0f}% left"
"""Reason when an account takes the job at its normal model."""

REASON_LUNA_TEMPLATE: str = (
    "every account is at or under {bar:.0f}% left; {account} has"
    " {percent_left:.0f}% and runs Luna until {stop:.0f}%"
)
"""Reason when the job falls back to Luna."""

REASON_WAIT_TEMPLATE: str = "no account has room; {account} resets first, at {reset}"
"""Reason when every account is out of room."""

REASON_WAIT_UNREAD: str = "no account meter could be read"
"""Reason when no account's meter reads at all."""

UNREAD_NOT_SIGNED_IN: str = "not signed in"
"""Unread reason when the account's Codex home holds no sign-in."""

UNKNOWN_RESET_TEXT: str = "an unknown time"
"""Reset text when no blocking window carries a reset time."""

TEXT_ENCODING: str = "utf-8"
"""Encoding for the server pipes and the JSON reports."""
