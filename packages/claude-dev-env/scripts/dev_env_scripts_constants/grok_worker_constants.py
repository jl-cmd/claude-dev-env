"""Named constants for the grok worker preflight soft gate.

Per the project's configuration conventions, every scalar and structural
constant the preflight needs lives here rather than inline in the module.
"""

from __future__ import annotations

GROK_BINARY_NAME: str = "grok"
"""Executable name resolved on PATH for the headless grok tier."""

MODELS_SUBCOMMAND: str = "models"
"""Subcommand that prints login state and model list without agent tokens."""

LEADER_SOCKET_FLAG: str = "--leader-socket"
"""CLI flag that points grok at a dedicated leader socket path."""

SINGLE_TURN_FLAG: str = "-p"
"""CLI flag that runs one single-turn prompt and exits."""

MAX_TURNS_FLAG: str = "--max-turns"
"""CLI flag that caps agent turns for the opt-in live ping."""

PING_MAX_TURNS: str = "1"
"""Turn cap passed with the opt-in live ping so the call stays single-turn."""

AUTH_LEADER_SOCKET_FILENAME: str = "grok-preflight-auth.sock"
"""Leader socket filename used only by the auth ``models`` probe."""

PING_LEADER_SOCKET_FILENAME: str = "grok-preflight-ping.sock"
"""Leader socket filename used only by the opt-in live ping."""

PING_CACHE_FILENAME: str = "grok_preflight_ping_cache.json"
"""Cache file name under the caller-supplied run state directory."""

PING_CACHE_CHECKED_AT_KEY: str = "checked_at"
"""JSON key holding the unix timestamp of the last successful ping."""

PING_CACHE_IS_OK_KEY: str = "is_ok"
"""JSON key holding whether the last ping completed successfully."""

PING_TTL_SECONDS: int = 300
"""Run-scoped TTL for a successful ping cache entry, in seconds."""

PING_PROMPT: str = "reply with the single word ok"
"""Single-turn prompt text used by the opt-in live ping."""

DEFAULT_AUTH_TIMEOUT_SECONDS: int = 30
"""Timeout applied to the ``grok models`` auth probe."""

DEFAULT_PING_TIMEOUT_SECONDS: int = 120
"""Timeout applied to the opt-in live single-turn ping."""

CLAUDE_HOME_SUBDIRECTORY: str = ".claude"
"""Per-user directory under the home directory that holds Claude config."""

MANIFEST_FILENAME: str = ".claude-dev-env-manifest.json"
"""Install manifest written by ``claude-dev-env`` into the user Claude home."""

AGENTS_SUBDIRECTORY: str = "agents"
"""Subdirectory of the user Claude home that holds agent definition files."""

ROLE_BUGTEAM: str = "bugteam"
"""Role name whose agent definition set the preflight validates by default."""

DEFAULT_ROLE: str = ROLE_BUGTEAM
"""Role applied when the caller does not pass ``--role``."""

ALL_AGENT_FILENAMES_BY_ROLE: dict[str, tuple[str, ...]] = {
    ROLE_BUGTEAM: ("code-quality-agent.md", "clean-coder.md"),
}
"""Agent definition filenames required under ``agents/`` for each known role."""

REASON_GROK_BINARY_MISSING: str = "grok_binary_missing"
"""Fallthrough reason when the grok binary is not resolvable on PATH."""

REASON_GROK_AUTH_FAILED: str = "grok_auth_failed"
"""Fallthrough reason when ``grok models`` exits non-zero or is unusable."""

REASON_CLAUDE_DEV_ENV_CONFIG_MISSING: str = "claude_dev_env_config_missing"
"""Fallthrough reason when the install manifest or role agents are absent."""

REASON_GROK_USAGE_EXHAUSTED: str = "grok_usage_exhausted"
"""Fallthrough reason when a live ping fails with a usage-exhaustion signature."""

STDOUT_OK_LINE: str = "grok_preflight: ok"
"""Machine-readable stdout line when tier 1 is usable."""

STDOUT_FALLTHROUGH_TEMPLATE: str = "grok_preflight: fallthrough reason={reason}"
"""Machine-readable stdout line when the soft gate falls through."""

EXIT_USABLE: int = 0
"""Process exit code when tier 1 is usable."""

EXIT_FALLTHROUGH: int = 1
"""Process exit code when the soft gate falls through (callers continue the chain)."""

CLI_ROLE_FLAG: str = "--role"
"""CLI flag naming the role whose agent definition set must be present."""

CLI_PING_FLAG: str = "--ping"
"""CLI flag that enables the opt-in cached live single-turn ping."""

CLI_RUN_STATE_DIR_FLAG: str = "--run-temp-dir"
"""CLI flag naming the run-scoped state directory for sockets and the ping cache."""

UTF8_ENCODING: str = "utf-8"
"""Encoding used for subprocess text mode and the ping cache file."""

ALL_USAGE_EXHAUSTION_SIGNATURES: tuple[str, ...] = (
    "usage limit",
    "out of usage",
    "quota exceeded",
    "rate limit",
    "usage exhausted",
)
"""Case-insensitive substrings that mark a non-zero ping as usage exhaustion."""

ALL_AUTH_FAILURE_SIGNATURES: tuple[str, ...] = (
    "not logged in",
    "unauthenticated",
    "authentication failed",
    "please log in",
    "login required",
    "unauthorized",
)
"""Case-insensitive substrings that mark a non-zero completion as an auth failure."""
