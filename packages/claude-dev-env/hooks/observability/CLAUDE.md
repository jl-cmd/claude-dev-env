# hooks/observability

PostToolUse hooks that record agent behavior for later review. These hooks do not block tool calls; they log or annotate them.

## Key files

| File | Event | What it does |
|---|---|---|
| `instructions_loaded_logger.py` | PostToolUse (file load events) | Appends a JSONL record to `~/.claude/logs/instructions_loaded.jsonl` each time Claude Code loads a context file (CLAUDE.md, rules, skills), capturing the file path, load reason, memory type, and session ID |
| `test_instructions_loaded_logger.py` | — | Tests for `instructions_loaded_logger.py` |

## Conventions

- The log file is append-only; the hook creates the parent directory if needed.
- Errors during logging are caught and written as error records rather than propagated — the hook never blocks the tool call.
- Tests run with `python -m pytest observability/test_instructions_loaded_logger.py`.
