"""Constants for the optional Codex Sol xhigh advisor bind."""

from __future__ import annotations

CODEX_EXECUTABLE: str = "codex"
CODEX_READ_ONLY_SANDBOX: str = "read-only"
CODEX_JSON_FLAG: str = "--json"
CODEX_MODEL_FLAG: str = "--model"
CODEX_CONFIG_FLAG: str = "--config"
CODEX_REASONING_CONFIG: str = 'model_reasoning_effort="xhigh"'
CODEX_PROMPT_FROM_STDIN: str = "-"
CODEX_EXEC_SUBCOMMAND: str = "exec"
CODEX_RESUME_SUBCOMMAND: str = "resume"
CODEX_SANDBOX_FLAG: str = "--sandbox"
CLAUDE_CONFIG_DIRECTORY_NAME: str = ".claude"
SOL_SESSION_ID_METAVAR: str = "SESSION_ID"
SOL_CODEX_TIMEOUT_SECONDS: float = 120.0
SOL_USAGE_PROBE_TIMEOUT_SECONDS: float = 30.0
SOL_ENV_VAR: str = "ADVISOR_SOL_XHIGH"
ALL_SOL_TRUTHY_VALUES: frozenset[str] = frozenset({"1", "true", "yes", "on"})
SOL_PREFLIGHT_FAILURE_REASON: str = "sol preflight did not establish an eligible Codex meter"
SOL_BIND_FAILURE_REASON: str = "Codex Sol xhigh bind failed"
SOL_REPLY_FAILURE_REASON: str = "Codex Sol xhigh returned no advisor guidance"
SOL_PROBE_TIMEOUT_REASON: str = "Codex Sol meter check timed out"
SOL_CODEX_TIMEOUT_REASON: str = "Codex Sol xhigh request timed out"
SOL_MALFORMED_JSONL_REASON: str = "Codex Sol xhigh returned malformed JSONL"
SOL_MISSING_SESSION_REASON: str = "Codex Sol xhigh returned no session id"
SOL_INVALID_SIGNAL_REASON: str = "Codex Sol xhigh returned an invalid guidance signal"
