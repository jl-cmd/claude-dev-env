# Clean Up Temporary Files

**When this applies:** After tasks that created scratch files, debug dumps, or one-off scripts the user did not ask to keep.

Source: [Anthropic — Reduce file creation in agentic coding](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#reduce-file-creation-in-agentic-coding)

## During a task

- Prefer working in memory over creating scratchpad files. Use variables and tool results instead of writing intermediate data to disk.
- When a temporary file is genuinely needed (e.g., a helper script, a test fixture, a debug output), track it mentally for cleanup.

## When a task is complete

- Remove every temporary file, script, or helper file you created during the task.
- Leave the working directory cleaner than you found it.
- If a file was created at the user's explicit request (not as a byproduct of your process), leave it in place.

## What counts as temporary

- Scripts written to test a hypothesis or run a one-off check
- Debug output files, log dumps, or intermediate data exports
- Helper files created to work around tool limitations
- Any file the user did not ask for and would not expect to find after the task

## Why

Temporary files accumulate across sessions and clutter the project root. Latest models sometimes use files as scratchpads during iteration, and these leftovers confuse both the user and future sessions if not cleaned up.
