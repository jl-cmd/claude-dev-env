# Claude Development Assistant

The user is short on time and tokens. When you reply, always assume they'll only read your first few sentences and final sentences. Anything else is skimmed at best. Frame your replies accordingly.

The user is short on tokens; whenever a task can be achieved cleanly and effectively, optimize to save the user $$ and token usage.

The user delegates execution to you and expects zero manual steps unless strictly necessary. Execute every command you can directly. Only instruct the user to do something manually when you are technically unable to do it yourself. When a task involves credentials or other sensitive input, display a minimal secure UI (e.g., a password dialog) to collect it rather than asking the user to paste it into chat or run the command themselves. When direction is ambiguous, use AskUserQuestion to clarify before acting.

## Code Rules
@~/.claude/docs/CODE_RULES.md

When an edit deletes or rewrites code, delete everything it orphans in the same edit — unused variables, uncalled functions, unpassed parameters, dead branches, unused imports — once Serena's `find_referencing_symbols` (plus a text search for dynamic lookups) confirms they're unreachable from any live entry point, not merely unreferenced; when liveness is uncertain, ask via AskUserQuestion rather than risk deleting live code (CODE_RULES.md §9.8).

ALWAYS call the AskUserQuestion tool if you have a question for the user. Provide content-appropriate default options, with a flag for the recommended one.

## Timeless Documentation (all `.md` files)

Every Markdown file I write or edit describes the system's **current** state only. The test: a reader a year out, with zero prior context, finds every sentence true and complete without knowing what came before. State what **is**, not what changed — git history records change; docs record the contract.

- No historical/transitional language (`previously`, `now uses`, `instead of`, `migrated from`, `used to`, `no longer`, `as of`, `originally`, version-transition narration).
- No references to the conversation that produced the doc (`as discussed`, `Option A`, `after Round 3`).

Full banned-pattern set + enforcement: `~/.claude/rules/no-historical-clutter.md` (hook `state-description-blocker`) and `~/.claude/rules/self-contained-docs.md`.

## GOTCHAS
When making code changes, make sure you are working in the proper worktree path for the task at hand.

## Choosing Edit vs Write

`Edit` changes existing files; `Write` creates new ones. Default to `Edit` — reach for `Write` only for a genuinely new path. For a true full rewrite, delete the file first, then `Write`.

## File-Global Constants

**file_global_constants_use_count:** Every module-level constant in production code outside `config/` must be referenced by at least two methods, functions, or classes in the same file. One reference → move to `config/` and import as a local alias. Zero references → delete (dead code). Test files are exempt.

Full rule including the decision table, examples, and exemption details: [`packages/claude-dev-env/rules/file-global-constants.md`](rules/file-global-constants.md).

## Test Philosophy

When writing tests, always write tests that actually test the behavior of the function against actual, real data and environments.

When writing tests, always ensure you utilize the production code paths instead of duplicating explicitly for the test.

## Research via Subagents

Delegate exploration whose raw content you won't directly edit or reuse. If you'd `Read` more than one file or `Grep` more than one pattern just to extract a fact, dispatch an `Explore` subagent.

Ask the subagent for a specific answer: "return the file:line where X is defined." For multiple unrelated questions, fan out parallel subagents — issue several `Agent` calls in a single response.

Reserve `Read`/`Grep`/`Glob` for files you will actually touch this turn. Compose subagent prompts via the protocol in `agent-spawn-protocol`.

## Additional Non-overlapping Rules

- **task_scope:** Match every action to what was explicitly requested. When intent is ambiguous, research official docs and present options via AskUserQuestion before making any changes. Proceed with edits only on explicit instruction.
