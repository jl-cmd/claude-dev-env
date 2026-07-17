"""Constants for the scripted converge task-list builder.

``build_converge_task_list.py`` is the only place that decides which review
gates appear on a run. Skill prose must not invent a different list.
"""

from __future__ import annotations

TASK_ID_CODE_REVIEW: str = "code_review"
TASK_ID_BUGTEAM: str = "bugteam"
TASK_ID_BUGBOT: str = "bugbot"
TASK_ID_COPILOT: str = "copilot"
TASK_ID_CODEX: str = "codex"
TASK_ID_ALL_CLEAN_SAME_HEAD: str = "all_runnable_reviews_clean_same_head"

TASK_KIND_REVIEW: str = "review"
TASK_KIND_FINAL: str = "final"

TASK_TITLE_CODE_REVIEW: str = "CODE_REVIEW clean (claude-review / xhigh)"
TASK_TITLE_BUGTEAM: str = "BUGTEAM clean (full origin/main...HEAD audit)"
TASK_TITLE_BUGBOT: str = "BUGBOT clean on same HEAD (or down/skip)"
TASK_TITLE_COPILOT: str = "COPILOT clean on same HEAD (or down/skip)"
TASK_TITLE_CODEX: str = "CODEX clean on same HEAD (when required)"
TASK_TITLE_ALL_CLEAN_SAME_HEAD: str = (
    "All runnable code reviews CLEAN on the same HEAD"
)

RESULT_KEY_TASKS: str = "tasks"
RESULT_KEY_FINAL_TASK_ID: str = "final_task_id"
RESULT_KEY_RUNNABLE_REVIEW_IDS: str = "runnable_review_ids"
RESULT_KEY_SKIPPED_REVIEW_IDS: str = "skipped_review_ids"
RESULT_KEY_DONE_WHEN: str = "done_when"

TASK_FIELD_ID: str = "id"
TASK_FIELD_TITLE: str = "title"
TASK_FIELD_KIND: str = "kind"
TASK_FIELD_IS_RUNNABLE: str = "is_runnable"
TASK_FIELD_SKIP_REASON: str = "skip_reason"

SKIP_REASON_BUGBOT_DOWN: str = "bugbot_down"
SKIP_REASON_COPILOT_DOWN: str = "copilot_down"
SKIP_REASON_CODEX_DOWN: str = "codex_down"
SKIP_REASON_CODEX_NOT_REQUIRED: str = "codex_not_required"

CLI_BUGBOT_DOWN_FLAG: str = "--bugbot-down"
CLI_COPILOT_DOWN_FLAG: str = "--copilot-down"
CLI_CODEX_DOWN_FLAG: str = "--codex-down"
CLI_CODEX_REQUIRED_FLAG: str = "--codex-required"

DONE_WHEN_TEXT: str = (
    "Every task with is_runnable true and kind review is clean at one shared "
    "HEAD; final task all_runnable_reviews_clean_same_head is completed."
)

EXIT_SUCCESS: int = 0
EXIT_USAGE_ERROR: int = 2
