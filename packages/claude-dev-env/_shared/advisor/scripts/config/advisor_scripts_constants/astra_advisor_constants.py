"""Constants for the optional Codex Astra advisor bind."""

from __future__ import annotations

CODEX_EXECUTABLE: str = "codex"
ADVISOR_CODEX_EXECUTABLE_ENV_VAR: str = "ADVISOR_CODEX_EXECUTABLE"
CODEX_READ_ONLY_SANDBOX: str = "read-only"
CODEX_JSON_FLAG: str = "--json"
CODEX_MODEL_FLAG: str = "--model"
CODEX_CONFIG_FLAG: str = "--config"
CODEX_REASONING_CONFIG_TEMPLATE: str = 'model_reasoning_effort="{effort}"'
CODEX_PROMPT_FROM_STDIN: str = "-"
CODEX_EXEC_SUBCOMMAND: str = "exec"
CODEX_RESUME_SUBCOMMAND: str = "resume"
CODEX_SANDBOX_FLAG: str = "--sandbox"
CODEX_HOME_ENV_VAR: str = "CODEX_HOME"
ALL_ACCOUNT_PICKER_RELATIVE_PARTS: tuple[str, ...] = ("scripts", "codex_account_choice.py")
SHARED_PACKAGE_ROOT_PARENT_INDEX: int = 2
ACCOUNT_PICKER_CHOOSE_COMMAND: str = "choose"
CODEX_TIER_NORMAL: str = "normal"
ASTRA_SESSION_ID_METAVAR: str = "SESSION_ID"
ASTRA_CODEX_TIMEOUT_SECONDS: float = 120.0
ASTRA_ACCOUNT_PICK_TIMEOUT_SECONDS: float = 150.0
ASTRA_ENV_VAR: str = "ADVISOR_ASTRA"
ALL_ASTRA_TRUTHY_VALUES: frozenset[str] = frozenset({"1", "true", "yes", "on"})
ASTRA_PREFLIGHT_FAILURE_REASON: str = "astra preflight found no Codex account to bind"
ASTRA_BIND_FAILURE_REASON: str = "Codex Astra bind failed"
ASTRA_REPLY_FAILURE_REASON: str = "Codex Astra returned no advisor guidance"
ASTRA_ACCOUNT_PICK_TIMEOUT_REASON: str = "Codex Astra account pick timed out"
ASTRA_CODEX_TIMEOUT_REASON: str = "Codex Astra request timed out"
ASTRA_MALFORMED_JSONL_REASON: str = "Codex Astra returned malformed JSONL"
ASTRA_MISSING_SESSION_REASON: str = "Codex Astra returned no session id"
ASTRA_INVALID_SIGNAL_REASON: str = "Codex Astra returned an invalid guidance signal"
ASTRA_EXECUTABLE_NOT_FOUND_REASON: str = "Codex Astra could not find the codex executable on PATH"
ASTRA_FALLBACK_KIND_DECLINED: str = "declined"
ASTRA_FALLBACK_KIND_BROKEN: str = "broken"
ASTRA_ENABLE_FLAG: str = "--enable-astra"
ASTRA_EFFORT_FLAG: str = "--effort"
