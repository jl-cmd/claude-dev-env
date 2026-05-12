# Claude Development Assistant

The user delegates execution to you and expects zero manual steps unless strictly necessary. Execute every command you can directly. Only instruct the user to do something manually when you are technically unable to do it yourself. When a task involves credentials or other sensitive input, display a minimal secure UI (e.g., a password dialog) to collect it rather than asking the user to paste it into chat or run the command themselves. When direction is ambiguous, use AskUserQuestion to clarify before acting.

## Code Rules
@~/.claude/docs/CODE_RULES.md

## GOTCHAS
When making code changes, make sure you are working in the proper worktree path for the task at hand.
When writing to an existing file, you must either EDIT the file, or remove it and THEN re-write it if it's truly a full re-write.

## File-Global Constants

**file_global_constants_use_count:** Every module-level constant in production code outside `config/` must be referenced by at least two methods, functions, or classes in the same file. One reference → move to `config/` and import as a local alias. Zero references → delete (dead code). Test files are exempt.

Full rule including the decision table, examples, and exemption details: [`packages/claude-dev-env/rules/file-global-constants.md`](rules/file-global-constants.md).

## Test Philosophy

When writing tests, always write tests that actually test the behavior of the function against actual, real data and environments.

When writing tests, always ensure you utilize the production code paths instead of duplicating explicitly for the test.

## Additional Non-overlapping Rules

- **task_scope:** Match every action to what was explicitly requested. When intent is ambiguous, research official docs and present options via AskUserQuestion before making any changes. Proceed with edits only on explicit instruction.
