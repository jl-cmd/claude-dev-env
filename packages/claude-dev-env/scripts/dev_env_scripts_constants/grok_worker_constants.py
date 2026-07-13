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

ALL_USAGE_LIMIT_SIGNATURES: tuple[str, ...] = (
    "429",
    "rate limit",
    "credit",
    "quota",
    "usage limit",
    "out of usage",
    "quota exceeded",
    "usage exhausted",
)
"""Case-insensitive substrings that mark a non-zero exit as a usage-limit failure."""

ALL_USAGE_EXHAUSTION_SIGNATURES: tuple[str, ...] = ALL_USAGE_LIMIT_SIGNATURES
"""Alias used by the preflight soft gate for the same usage-limit signatures."""

ALL_AUTH_FAILURE_SIGNATURES: tuple[str, ...] = (
    "401",
    "unauthorized",
    "invalid key",
    "not logged in",
    "unauthenticated",
    "authentication failed",
    "please log in",
    "login required",
)
"""Case-insensitive substrings that mark a non-zero completion as an auth failure."""

PROMPT_FILE_FLAG: str = "--prompt-file"
"""CLI flag that points grok at a prompt file for headless single-turn work."""

CWD_FLAG: str = "--cwd"
"""CLI flag that sets the working directory for the headless grok process."""

OUTPUT_FORMAT_FLAG: str = "--output-format"
"""CLI flag that selects the headless output format."""

OUTPUT_FORMAT_JSON: str = "json"
"""Output-format value that requests machine-readable JSON from grok."""

ALWAYS_APPROVE_FLAG: str = "--always-approve"
"""CLI flag that auto-approves tool executions in the headless worker."""

AGENT_FLAG: str = "--agent"
"""CLI flag that names the role agent definition the worker should load."""

MODEL_FLAG: str = "--model"
"""CLI flag that pins a model id when ``GROK_MODEL_PIN`` is non-empty."""

GROK_MODEL_PIN: str = ""
"""Optional model id pin. Empty string leaves the CLI default (``grok-4.5``)."""

LEADER_SOCKET_FILENAME_PREFIX: str = "grok-leader-"
"""Filename prefix for each unique per-invocation leader socket under the run state directory."""

LEADER_SOCKET_FILENAME_SUFFIX: str = ".sock"
"""Filename suffix for each unique per-invocation leader socket."""

CLASSIFICATION_OK: str = "ok"
"""Outcome classification when the headless process exits zero."""

CLASSIFICATION_USAGE_LIMIT: str = "usage_limit"
"""Outcome classification when stdout/stderr match a usage-limit signature."""

CLASSIFICATION_AUTH_FAILURE: str = "auth_failure"
"""Outcome classification when stdout/stderr match an auth-failure signature."""

CLASSIFICATION_TIMEOUT: str = "timeout"
"""Outcome classification when the headless process exceeds the timeout and is killed."""

CLASSIFICATION_ERROR: str = "error"
"""Outcome classification for a non-zero exit that matches no known signature."""

DEFAULT_WORKER_TIMEOUT_SECONDS: int = 600
"""Default timeout applied to one headless worker invocation, in seconds."""

TIMEOUT_RETURN_CODE: int = -1
"""Return code recorded on the outcome when a timed-out process leaves no return code."""

TIER_GROK: int = 1
"""Dispatcher tier number for the headless grok worker path."""

TIER_CLAUDE_AGENT: int = 2
"""Dispatcher tier number for the in-host claude_agent_required handoff."""

TIER_CLAUDE_HEADLESS: int = 3
"""Dispatcher tier number for the headless claude chain path."""

REASON_CLAUDE_AGENT_REQUIRED: str = "claude_agent_required"
"""Fallthrough reason when the caller must run claude_agent_required itself."""

DEFAULT_SPAWN_MAX_TURNS: int = 8
"""Default max-turns applied to the headless grok worker when the caller names none."""

SPAWN_SERVED_EXIT_CODE: int = 0
"""CLI exit code when a dispatcher tier served the call."""

SPAWN_EXHAUSTED_EXIT_CODE: int = 2
"""CLI exit code when no dispatcher tier served the call."""

SPAWN_CONFIG_ERROR_EXIT_CODE: int = 3
"""CLI exit code when the claude chain configuration is missing or invalid."""

RESULT_KEY_TIER_USED: str = "tier_used"
"""JSON result key naming the tier that served the call, or null."""

RESULT_KEY_OK: str = "ok"
"""JSON result key holding whether the served call completed successfully."""

RESULT_KEY_ATTEMPTS: str = "attempts"
"""JSON result key holding the ordered list of tier attempts."""

RESULT_KEY_OUTPUT: str = "output"
"""JSON result key holding captured worker stdout from the serving tier."""

RESULT_KEY_RETURNCODE: str = "returncode"
"""JSON result key holding the process return code from the last tier run."""

ATTEMPT_KEY_TIER: str = "tier"
"""JSON attempt key naming the tier number tried."""

ATTEMPT_KEY_OK: str = "ok"
"""JSON attempt key holding whether that tier completed successfully."""

ATTEMPT_KEY_REASON: str = "reason"
"""JSON attempt key holding the fallthrough or handoff reason string."""

CLI_PROMPT_FILE_FLAG: str = "--prompt-file"
"""CLI flag naming the prompt file path for the dispatcher."""

CLI_CWD_FLAG: str = "--cwd"
"""CLI flag naming the working directory for the worker process."""

CLI_TIMEOUT_FLAG: str = "--timeout-seconds"
"""CLI flag naming the per-tier timeout in seconds."""

CLI_ENABLE_CLAUDE_TIER_FLAG: str = "--enable-claude-tier"
"""CLI flag that enables the headless claude chain tier on a Claude host."""

EMPTY_OUTPUT: str = ""
"""Empty captured output when no tier produced stdout."""
