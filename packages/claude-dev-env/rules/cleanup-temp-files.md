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

## Exceptions to the removal duty

Three kinds of file are already ephemeral and need no explicit removal:

- A file under the OS temporary root.
- A file under `$CLAUDE_JOB_DIR`, which the harness clears with the job.
- A child agent's scratch file, which the parent removes at teardown.

Use an allowed removal form for everything else: [`destructive-commands.md`](destructive-commands.md) names them.

## What counts as temporary

- Scripts written to test a hypothesis or run a one-off check
- Debug output files, log dumps, or intermediate data exports
- Helper files created to work around tool limitations
- Any file the user did not ask for and would not expect to find after the task
