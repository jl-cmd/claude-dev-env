"""Filename, path-segment, and template constants for the durable handoff writer.

Consumed by `write_handoff.py`, which writes each pr-loop run's resume-handoff
files under `~/.claude/runtime/pr-loop/<run-name>/`.
"""

ALL_HANDOFF_DIR_SEGMENTS = (".claude", "runtime", "pr-loop")
HANDOFF_JSON_FILENAME = "handoff.json"
HANDOFF_MARKDOWN_FILENAME = "HANDOFF.md"
STATE_COPY_FILENAME = "state-copy.json"
ATOMIC_STAGING_SUFFIX = ".tmp"
HANDOFF_JSON_INDENT = 2
COMPLETED_STEPS_SEPARATOR = ","
STEP_LINE_SEPARATOR = "\n"

NO_STATE_SNAPSHOT_LINE = (
    "No state snapshot was captured. Rebuild loop state from the PR before resuming."
)
DEFAULT_NEXT_STEP_LINE = "Continue from the resume command above."
NO_STEPS_DONE_LINE = "- (none recorded yet)"

HANDOFF_MARKDOWN_TEMPLATE = """# Resume handoff — PR {pr_number} ({head_ref})

Goal: drive PR {pr_number} to convergence. This run stopped at phase `{phase}`.

## Resume command

Run this exactly:

```
{resume_command}
```

## State file to trust

{state_line}

## Steps already done

{steps_block}

## Next step

{next_step}
"""
