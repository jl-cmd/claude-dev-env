"""Configuration constants for the workflow_substitution_slot_blocker PreToolUse hook."""

WRITE_TOOL_NAME: str = "Write"
EDIT_TOOL_NAME: str = "Edit"
MULTI_EDIT_TOOL_NAME: str = "MultiEdit"

WORKFLOW_FILE_SUFFIX: str = ".workflow.js"

CORRECTIVE_MESSAGE: str = (
    "BLOCKED [workflow-substitution-slot]: A bare per-iteration index token "
    "(for example `cand_i`) appears as a per-iteration path segment inside a "
    ".workflow.js agent-prompt block that loops over an index. A bare `_i` "
    "token reads as a fixed literal, so an agent can create one literal "
    "directory and overwrite it across every iteration -- collapsing an "
    "N-iteration gate into one.\n\n"
    "Mark the index as a substitution slot with the angle-bracket convention "
    "this template already uses for per-call values (`<plate.svg>`, `<glow_hex>`): "
    "write `cand_<i>` instead of `cand_i`, or spell out 'replace <i> with the "
    "iteration index 0, 1, 2' in the step text.\n\n"
    "Convention: every per-call substitution slot in a .workflow.js template is "
    "marked with angle brackets, so an agent fills in a fresh value per call."
)
