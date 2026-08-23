"""Constants for the optional Codex Sol advisor bind."""

from __future__ import annotations

CODEX_EXECUTABLE: str = "codex"
ADVISOR_CODEX_EXECUTABLE_ENV_VAR: str = "ADVISOR_CODEX_EXECUTABLE"
CODEX_READ_ONLY_SANDBOX: str = "read-only"
CODEX_JSON_FLAG: str = "--json"
CODEX_MODEL_FLAG: str = "--model"
CODEX_CONFIG_FLAG: str = "--config"
SOL_REASONING_EFFORT: str = "low"
CODEX_REASONING_CONFIG: str = f'model_reasoning_effort="{SOL_REASONING_EFFORT}"'
CODEX_PROMPT_FROM_STDIN: str = "-"
CODEX_EXEC_SUBCOMMAND: str = "exec"
CODEX_RESUME_SUBCOMMAND: str = "resume"
CODEX_SANDBOX_FLAG: str = "--sandbox"
CLAUDE_CONFIG_DIRECTORY_NAME: str = ".claude"
SOL_SESSION_ID_METAVAR: str = "SESSION_ID"
SOL_CODEX_TIMEOUT_SECONDS: float = 120.0
SOL_USAGE_PROBE_TIMEOUT_SECONDS: float = 30.0
# Flag name still says XHIGH; Sol reasoning effort is low.
SOL_ENV_VAR: str = "ADVISOR_SOL_XHIGH"
ALL_SOL_TRUTHY_VALUES: frozenset[str] = frozenset({"1", "true", "yes", "on"})
SOL_PREFLIGHT_FAILURE_REASON: str = "sol preflight did not establish an eligible Codex meter"
SOL_BIND_FAILURE_REASON: str = "Codex Sol bind failed"
SOL_REPLY_FAILURE_REASON: str = "Codex Sol returned no advisor guidance"
SOL_PROBE_TIMEOUT_REASON: str = "Codex Sol meter check timed out"
SOL_CODEX_TIMEOUT_REASON: str = "Codex Sol request timed out"
SOL_MALFORMED_JSONL_REASON: str = "Codex Sol returned malformed JSONL"
SOL_MISSING_SESSION_REASON: str = "Codex Sol returned no session id"
SOL_INVALID_SIGNAL_REASON: str = "Codex Sol returned an invalid guidance signal"
SOL_EXECUTABLE_NOT_FOUND_REASON: str = "Codex Sol could not find the codex executable on PATH"
SOL_FALLBACK_KIND_DECLINED: str = "declined"
SOL_FALLBACK_KIND_BROKEN: str = "broken"
SOL_ENABLE_FLAG: str = "--enable-sol"
