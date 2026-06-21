# Claude Development Assistant

The user is short on time and tokens. When you reply, always assume they'll only read your first few sentences and final sentences. Anything else is skimmed at best. Frame your replies accordingly.

The user is short on tokens; whenever a task can be achieved cleanly and effectively, optimize to save the user $$ and token usage.

The user delegates execution to you and expects zero manual steps unless strictly necessary. Execute every command you can directly. Only instruct the user to do something manually when you are technically unable to do it yourself. When a task involves credentials or other sensitive input, display a minimal secure UI (e.g., a password dialog) to collect it rather than asking the user to paste it into chat or run the command themselves. When direction is ambiguous, use AskUserQuestion to clarify before acting.

## Code Rules
@~/.claude/docs/CODE_RULES.md

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

## Showing Files: Open Them, Don't Print the Path

When I ask you to "show me", "open", "display", "let me see", or "pull up" a file — an image, PDF, HTML page, document, anything — open it on my screen. Launch the viewer so each image window matches the asset's size:

`Start-Process pwsh -WindowStyle Hidden -ArgumentList '-NoProfile','-File',"$HOME\.claude\scripts\Show-Asset.ps1",'<path 1>','<path 2>'`

It sizes each image window to the image (scaled down to fit the screen) and opens non-image files in their default app; pass every path I name. Printing a path or attaching the file is not showing it — do that only when the file truly cannot be opened, and say why.

The `send_user_file_open_locally_blocker` hook backs this up: it blocks a desk-side `SendUserFile` attach and sends you back to this command, while a phone push (`status: "proactive"`) stays allowed.

## Test Philosophy

When writing tests, always write tests that actually test the behavior of the function against actual, real data and environments.

When writing tests, always ensure you utilize the production code paths instead of duplicating explicitly for the test.

## Research via Subagents

Delegate exploration whose raw content you won't directly edit or reuse. If you'd `Read` more than one file or `Grep` more than one pattern just to extract a fact, dispatch an `Explore` subagent.

Ask the subagent for a specific answer: "return the file:line where X is defined." For multiple unrelated questions, fan out parallel subagents — issue several `Agent` calls in a single response.

Reserve `Read`/`Grep`/`Glob` for files you will actually touch this turn. Compose subagent prompts via the protocol in `agent-spawn-protocol`.

## Target Execution Workflow for Code Tasks

Run every multi-step code task in two phases:

1. **Coders** — one coder agent per scoped assignment writes the code. A coder that hits a decision it can't reasonably solve consults the tool-less `code-advisor` agent — which returns a plan, a correction, or a stop signal — and resumes. Source: Anthropic's advisor strategy (https://claude.com/blog/the-advisor-strategy).
2. **Verification** — when the coders finish, the main session spawns the `code-verifier` agent in a fresh context. It derives and runs the checks itself rather than trusting coder reports: the task's named gates, tests against baselines recorded before the coders ran, and a two-way diff-vs-assignment reading (every task item maps to a hunk, every hunk maps to a task item, nothing missing). A finding must cite a failing command or a named task item. Source: the fresh-context review step in Claude Code best practices (https://code.claude.com/docs/en/best-practices) — the agent doing the work isn't the one grading it.

Repair agents run only on reported findings; the verifier re-checks after each repair. Work lands (commit, push, draft PR) only on a clean verdict — enforced by the `verified_commit_gate` hook, which blocks `git commit`/`git push` unless a hook-minted verdict covers the current branch diff. The one exemption is mechanical, not discretionary: a diff whose every changed file is non-code or has an unchanged Python AST once docstrings are stripped (docs, docstrings, comments).

## Converge & Review Loop Discipline

- **Worktree isolation:** Run every PR convergence and review loop in an isolated worktree, never a shared checkout that concurrent processes may advance. Verify isolation (the working directory path includes `.claude/worktrees/`) before the first tick or round.
- **No hedging in findings:** Findings and PR reports state verified facts only — never `likely`, `probably`, `should`, `appears to`. Verify each claim against the code before stating it; the anti-hallucination Stop hook rejects hedged responses.
- **Tight edit scope:** Edit exactly what the task names — no whole-file rewrites, no renaming public method parameters, no changes beyond the stated task. When the user asks for a "lasting" or "reusable" fix, prefer the durable systemic fix over a one-off edit. When the task touches a pipeline, generator, or other repeated process, fix the process itself, not its individual outputs — even when the request does not say so; for one-off targets, a scoped patch remains the default.
- **GitHub MCP first:** The GitHub MCP (`mcp__plugin_github_github__*`) is the primary path for PR and review-thread inspection; raw `gh api` is the fallback, not the default — MCP calls work the same from any worktree.

## Destructive-command literals in Bash

Never put a destructive-command literal (`rm -rf`, `git reset --hard`, `dd`, `mkfs`) inside a Bash command string, even when the shell never runs it — a quoted `python -c` argument, a heredoc body, an echoed string, a commit or PR body. The `destructive_command_blocker` hook matches the raw text and asks for confirmation, which a background run cannot answer, so the call stalls. Run hook and deletion checks through the committed test suite (`python -m pytest <test_file>`), or a throwaway script under `$CLAUDE_JOB_DIR/tmp` run as `python <file>.py` — either way the command string carries no destructive text, so the hook stays silent. Group genuine cleanup deletions into one teardown step. See `~/.claude/rules/no-inline-destructive-literals.md`.

## Sub-agent Output Validation

After any sub-agent returns a PR description, file list, or counts, verify each claim against the actual diff and repo state before using it. Flag and correct any invented paths, fabricated counts, or out-of-scope changes before they land in commits or PR bodies.

## Git Sync Intent

When asked to sync git ("get X onto origin main", "update main"), fast-forward local main to origin — do NOT commit untracked working-tree files unless explicitly told to.

## Scheduled Task Cadence

For scheduled/cron tasks, default to sub-hour intervals (30-minute); do not propose hourly cadences.

## Task Tracking

Track every task with the task tool, always — for all sessions and all tasks. Capture each task with `TaskCreate` as it arrives, mark it `in_progress` with `TaskUpdate` when you start, and `completed` when it is done. Run `/task-build` to gather any open tasks and add them to the list in one pass.

## Working in the claude-code-config Repo

When changing how skills, rules, or hooks install or sync in this repo (for example adding a skill), read `docs/references/skill-install-system.md` — it maps the install pipeline in `packages/claude-dev-env/bin/install.mjs`.

## Additional Non-overlapping Rules

- **task_scope:** Match every action to what was explicitly requested. When intent is ambiguous, research official docs and present options via AskUserQuestion before making any changes. Proceed with edits only on explicit instruction.
- **confirm_implementation_forks:** When two or more viable paths would satisfy the goal and the choice changes the deliverable — its scope, completeness, deferred work, dependencies, or a hard-to-reverse contract — stop and ask which path via AskUserQuestion before implementing. A path that defers work or leaves a placeholder creating a follow-up task is itself a fork to surface, not a default to take silently. Phrase the question in plain language with only the detail needed to decide. See [`confirm-implementation-forks`](rules/confirm-implementation-forks.md).
- **disambiguate_overloaded_terms:** When a word in the request has two different technical meanings — "conflict" (git-merge versus functional/behavioral), "sync" (fast-forward versus commit), and the like — confirm which one is meant via AskUserQuestion before analyzing or acting.

## Serena (Code Intelligence MCP)

The `mcp__serena__*` tools expose LSP-level code intelligence for any activated project.

### CRITICAL: Call `initial_instructions` first
Before any coding task, call the `initial_instructions` tool to load the Serena Instructions Manual.

### When to use Serena
- **Symbol declaration** → `mcp__serena__find_declaration`
- **All references to a symbol** → `mcp__serena__find_referencing_symbols`
- **Implementations of an interface/class** → `mcp__serena__find_implementations`
- **Rename across codebase** → `mcp__serena__rename_symbol`
- **Targeted body replacement / insertion** → `replace_symbol_body`, `insert_after_symbol`, `insert_before_symbol`
- **Safe symbol removal (no references)** → `mcp__serena__safe_delete_symbol`
- **File diagnostics** → `mcp__serena__get_diagnostics_for_file`

### Tool hierarchy for code navigation
1. **Serena** — symbol-level navigation (declarations, references, implementations, rename)
2. **Everything** (`everything_search`) — file-system search by name/path/extension
3. **Grep/Glob** — content and pattern matching

## Everything Search (MCP Tool)

This machine has **Everything (voidtools)** running with an HTTP server on port 54321.
The `everything_search` MCP tool is available in every session.

### Use Everything for file-system searches
Use `everything_search` for finding files by name, path, extension, size, or date. For content searches, use Grep — Everything's `content:` search is a fallback when Grep returns nothing.

### Fallback order
1. **Everything** (`everything_search`) — file-system search by name/path/extension/size/date, and content search
2. **Grep** — complex regex content searches if Everything's `content:` returns nothing
3. **Glob** — precise relative-path pattern matching within the current project

### Search syntax quick reference
- `ext:py` — find by extension (multiple: `ext:ts;js`)
- `path:src\components` — match against full path
- `count:10` — limit number of results to 10
- `*.config.*` — wildcards
- `size:>10mb` — size filter
- `dm:today` / `dm:thisweek` — date modified filter
- `content:keyword` — search inside file contents
- `parent:node_modules package.json` — match parent folder
- `foo bar` — AND, `foo | bar` — OR, `!foo` — NOT
- `"exact phrase"` — literal match
