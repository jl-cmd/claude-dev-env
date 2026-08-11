"""Configuration constants for the workflow_substitution_slot_blocker PreToolUse hook."""

WRITE_TOOL_NAME: str = "Write"
EDIT_TOOL_NAME: str = "Edit"
MULTI_EDIT_TOOL_NAME: str = "MultiEdit"

WORKFLOW_FILE_SUFFIX: str = ".workflow.js"

CORRECTIVE_MESSAGE: str = (
    "BLOCKED [workflow-substitution-slot]: Mark every per-iteration path slot with "
    "angle brackets. Write `cand_<i>` for the iteration index. Spell out `replace "
    "<i> with the iteration index 0, 1, 2` when the step text carries the "
    "substitution."
)
