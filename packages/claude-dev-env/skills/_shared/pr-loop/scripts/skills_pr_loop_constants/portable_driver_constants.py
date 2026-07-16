"""Constants for the scripted portable converge driver.

Deterministic control for third-party pacers lives in
``portable_converge_driver.py``. These names are the only phase, next-action,
and delay tokens that driver emits.
"""

from __future__ import annotations

PHASE_CODE_REVIEW: str = "CODE_REVIEW"
PHASE_BUGTEAM: str = "BUGTEAM"
PHASE_BUGBOT: str = "BUGBOT"
PHASE_COPILOT_WAIT: str = "COPILOT_WAIT"
PHASE_READY: str = "READY"
PHASE_BLOCKED: str = "BLOCKED"
ALL_PHASES: tuple[str, ...] = (
    PHASE_CODE_REVIEW,
    PHASE_BUGTEAM,
    PHASE_BUGBOT,
    PHASE_COPILOT_WAIT,
    PHASE_READY,
    PHASE_BLOCKED,
)

NEXT_RUN_CODE_REVIEW: str = "run_code_review"
NEXT_APPLY_FIXES: str = "apply_fixes_and_push"
NEXT_RUN_BUGTEAM: str = "run_bugteam"
NEXT_RUN_BUGBOT_GATE: str = "run_bugbot_gate"
NEXT_RUN_CODEX: str = "run_codex_review"
NEXT_REQUEST_COPILOT: str = "request_copilot_review"
NEXT_POLL_WAIT: str = "poll_wait"
NEXT_CHECK_READY: str = "check_ready"
NEXT_MARK_READY: str = "mark_ready"
NEXT_TEARDOWN: str = "teardown"
NEXT_STOP_BLOCKED: str = "stop_blocked"
ALL_NEXT_ACTIONS: tuple[str, ...] = (
    NEXT_RUN_CODE_REVIEW,
    NEXT_APPLY_FIXES,
    NEXT_RUN_BUGTEAM,
    NEXT_RUN_BUGBOT_GATE,
    NEXT_RUN_CODEX,
    NEXT_REQUEST_COPILOT,
    NEXT_POLL_WAIT,
    NEXT_CHECK_READY,
    NEXT_MARK_READY,
    NEXT_TEARDOWN,
    NEXT_STOP_BLOCKED,
)

DEFAULT_WAIT_SECONDS: int = 360
BUGBOT_INLINE_LAG_WAIT_SECONDS: int = 90
INLINE_LAG_STREAK_CAP: int = 3
COPILOT_WAIT_HARD_CAP: int = 3
BUGBOT_ABSENT_WAIT_HARD_CAP: int = 3

STATE_FILENAME: str = "pr-converge-state.json"
STATE_JSON_INDENT: int = 2
STATE_STAGING_SUFFIX: str = ".tmp"
ALL_GIT_REV_PARSE_HEAD_ARGV: tuple[str, ...] = ("git", "rev-parse", "HEAD")
PREFLIGHT_WORKTREE_SCRIPT_NAME: str = "preflight_worktree.py"
CLI_DESCRIPTION: str = "portable_converge_driver phase machine"
SERVED_COMMAND_IN_SESSION: str = "in_session"

RESULT_KEY_STATUS: str = "status"
RESULT_KEY_PHASE: str = "phase"
RESULT_KEY_NEXT: str = "next"
RESULT_KEY_STATE_FILE: str = "state_file"
RESULT_KEY_CURRENT_HEAD: str = "current_head"
RESULT_KEY_TICK_COUNT: str = "tick_count"
RESULT_KEY_WAIT_SECONDS: str = "wait_seconds"
RESULT_KEY_BLOCKER: str = "blocker"
RESULT_KEY_COMMANDS: str = "commands"
RESULT_KEY_PACER: str = "pacer"
RESULT_KEY_ENTRY_SKILL: str = "entry_skill"
RESULT_KEY_OWNER: str = "owner"
RESULT_KEY_REPO: str = "repo"
RESULT_KEY_PR_NUMBER: str = "pr_number"
RESULT_KEY_MESSAGE: str = "message"
RESULT_KEY_COPILOT_DOWN: str = "copilot_down"
RESULT_KEY_BUGBOT_DOWN: str = "bugbot_down"
RESULT_KEY_CODEX_DOWN: str = "codex_down"

STATUS_OK: str = "ok"
STATUS_ERROR: str = "error"

BLOCKER_COPILOT_WAIT_CAP: str = "copilot_wait_cap"
BLOCKER_BUGBOT_WAIT_CAP: str = "bugbot_wait_cap"
BLOCKER_INLINE_LAG_CAP: str = "inline_lag_cap"
BLOCKER_REVIEW_FAILED: str = "code_review_failed"
BLOCKER_PREFLIGHT: str = "preflight_failed"
BLOCKER_NOT_PORTABLE: str = "pacer_not_portable"

CLI_STATE_DIR_FLAG: str = "--state-dir"
CLI_STATE_FILE_FLAG: str = "--state-file"
CLI_OWNER_FLAG: str = "--owner"
CLI_REPO_FLAG: str = "--repo"
CLI_PR_NUMBER_FLAG: str = "--pr-number"
CLI_CWD_FLAG: str = "--cwd"
CLI_SESSION_MODEL_FLAG: str = "--session-model"
CLI_RETURNCODE_FLAG: str = "--returncode"
CLI_DIRTY_TREE_FLAG: str = "--dirty-tree"
CLI_SERVED_COMMAND_FLAG: str = "--served-command"
CLI_PUSHED_FLAG: str = "--pushed"
CLI_CONVERGED_FLAG: str = "--converged"
CLI_CLASSIFICATION_FLAG: str = "--classification"
CLI_REVIEW_SURFACED_FLAG: str = "--review-surfaced"
CLI_INLINE_LAG_FLAG: str = "--inline-lag"
CLI_BUGBOT_DOWN_FLAG: str = "--bugbot-down"
CLI_COPILOT_DOWN_FLAG: str = "--copilot-down"
CLI_CODEX_DOWN_FLAG: str = "--codex-down"
CLI_CODEX_REQUIRED_FLAG: str = "--codex-required"
CLI_CODEX_CLEAN_AT_FLAG: str = "--codex-clean-at"
CLI_CURRENT_HEAD_FLAG: str = "--current-head"
CLI_CHECK_CONVERGENCE_EXIT_FLAG: str = "--check-exit"

CLASSIFICATION_CLEAN: str = "clean"
CLASSIFICATION_DIRTY: str = "dirty"
CLASSIFICATION_ABSENT: str = "absent"
CLASSIFICATION_DOWN: str = "down"
ALL_CLASSIFICATIONS: tuple[str, ...] = (
    CLASSIFICATION_CLEAN,
    CLASSIFICATION_DIRTY,
    CLASSIFICATION_ABSENT,
    CLASSIFICATION_DOWN,
)
ALL_COPILOT_CLASSIFICATIONS: tuple[str, ...] = (
    CLASSIFICATION_CLEAN,
    CLASSIFICATION_DIRTY,
    CLASSIFICATION_ABSENT,
    CLASSIFICATION_DOWN,
)
ALL_CODEX_CLASSIFICATIONS: tuple[str, ...] = (
    CLASSIFICATION_CLEAN,
    CLASSIFICATION_DIRTY,
    CLASSIFICATION_DOWN,
)

STATE_KEY_PENDING_NEXT: str = "pending_next"
STATE_KEY_CODEX_DOWN: str = "codex_down"
STATE_KEY_CODEX_REQUIRED: str = "codex_required"
STATE_KEY_CODEX_CLEAN_AT: str = "codex_clean_at"
STATE_KEY_SESSION_MODEL: str = "session_model"
STATE_KEY_CWD: str = "cwd"

MARK_READY_GH_BINARY: str = "gh"
MARK_READY_PR_TOKEN: str = "pr"
MARK_READY_SUBCOMMAND: str = "ready"
MARK_READY_REPO_FLAG: str = "--repo"

CHECK_CONVERGENCE_OWNER_FLAG: str = "--owner"
CHECK_CONVERGENCE_REPO_FLAG: str = "--repo"
CHECK_CONVERGENCE_PR_NUMBER_FLAG: str = "--pr-number"
CHECK_CONVERGENCE_COPILOT_DOWN_FLAG: str = "--copilot-down"
CHECK_CONVERGENCE_BUGBOT_DOWN_FLAG: str = "--bugbot-down"
CHECK_CONVERGENCE_CODEX_DOWN_FLAG: str = "--codex-down"
CHECK_CONVERGENCE_CODEX_CLEAN_AT_FLAG: str = "--codex-clean-at"

COMMAND_OPEN_RUN: str = "open-run"
COMMAND_AFTER_CODE_REVIEW: str = "after-code-review"
COMMAND_AFTER_BUGTEAM: str = "after-bugteam"
COMMAND_AFTER_BUGBOT: str = "after-bugbot"
COMMAND_AFTER_COPILOT_WAIT: str = "after-copilot-wait"
COMMAND_AFTER_CODEX: str = "after-codex"
COMMAND_AFTER_READY_CHECK: str = "after-ready-check"
COMMAND_SHOW_STATE: str = "show-state"

DEFAULT_SESSION_MODEL: str = "third-party"

INVOKE_CODE_REVIEW_RELATIVE_PATH: str = ".claude/scripts/invoke_code_review.py"
CHECK_CONVERGENCE_RELATIVE_PATH: str = (
    ".claude/skills/pr-converge/scripts/check_convergence.py"
)

EXIT_SUCCESS: int = 0
EXIT_USAGE_ERROR: int = 2
EXIT_CONTRACT_ERROR: int = 1
