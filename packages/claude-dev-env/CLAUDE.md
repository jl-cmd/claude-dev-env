# Claude Development Assistant

The user is short on time and appreciates brevity in replies. When you reply, always assume they'll only read your first few sentences and final sentences. Anything else is skimmed at best. Frame your replies accordingly.

The user delegates execution to you and expects zero manual steps unless strictly necessary. Execute every command you can directly. Only instruct the user to do something manually when you are technically unable to do it yourself. When a task involves credentials or other sensitive input, display a minimal secure UI (e.g., a password dialog) to collect it rather than asking the user to paste it into chat or run the command themselves. When direction is ambiguous, use AskUserQuestion to clarify before acting.

## Timeless Documentation (all `.md` files)

Docs describe the current state only. Full rule set and enforcement: `~/.claude/rules/no-historical-clutter.md` (hook `state-description-blocker`) and `~/.claude/rules/self-contained-docs.md`.

## Choosing Edit vs Write

`Edit` changes existing files; `Write` creates new ones. Default to `Edit` — reach for `Write` only for a genuinely new path. For a true full rewrite, delete the file first, then `Write`.

## Showing Files: Open Them, Don't Print the Path

When I ask you to "show me", "open", "display", "let me see", or "pull up" a file — an image, PDF, HTML page, document, anything — open it on my screen. Launch the viewer so each image window matches the asset's size:

`Start-Process pwsh -WindowStyle Hidden -ArgumentList '-NoProfile','-File',"$HOME\.claude\scripts\Show-Asset.ps1",'<path 1>','<path 2>'`

## Test Philosophy

When writing tests, always write tests that actually test the behavior of the function against actual, real data and environments.

When writing tests, always ensure you utilize the production code paths instead of duplicating explicitly for the test.

## Research via Subagents

Delegate exploration whose raw content you won't directly edit or reuse. If you'd `Read` more than one file or `Grep` more than one pattern just to extract a fact, dispatch an `Explore` subagent.

Ask the subagent for a specific answer: "return the file:line where X is defined." For multiple unrelated questions, fan out parallel subagents — issue several `Agent` calls in a single response.

Reserve `Read`/`Grep`/`Glob` for files you will actually touch this turn. Compose subagent prompts via the protocol in `agent-spawn-protocol`.

## Target Execution Workflow for Code Tasks

Run every multi-step code task in two phases:

1. **Coders** — one coder agent per scoped assignment writes the code. A coder that hits a decision it can't reasonably solve consults the advisor (see beginning of this file).
2. **Verification** — when the coders finish, the main session spawns the `code-verifier` agent in a fresh context, but you must first verify that their work is based on upstream's origin main (aka: the commit live on github). It derives and runs the checks itself rather than trusting coder reports: the task's named gates, tests against baselines recorded before the coders ran, and a two-way diff-vs-assignment reading (every task item maps to a hunk, every hunk maps to a task item, nothing missing). A finding must cite a failing command or a named task item. Source: the fresh-context review step in Claude Code best practices (https://code.claude.com/docs/en/best-practices) — the agent doing the work isn't the one grading it.

Repair agents run only on reported findings; the verifier re-checks after each repair. Work lands (commit, push, draft PR) only on a clean verdict — enforced by the `verified_commit_gate` hook, which blocks `git commit`/`git push` unless a hook-minted verdict covers the current branch diff. The one exemption is mechanical, not discretionary: a diff whose every changed file is non-code or has an unchanged Python AST once docstrings are stripped (docs, docstrings, comments).

## Sub-agent Output Validation

After any sub-agent returns a PR description, file list, or counts, verify each claim against the actual diff and repo state before using it. Flag and correct any invented paths, fabricated counts, or out-of-scope changes before they land in commits or PR bodies.

## Task Tracking

Track every task with the task tool, always — for all sessions and all tasks. Capture each task with `TaskCreate` as it arrives, mark it `in_progress` with `TaskUpdate` when you start, and `completed` when it is done. Run `/task-build` to gather any open tasks and add them to the list in one pass.

## Working in the claude-code-config Repo

When changing how skills, rules, or hooks install or sync in this repo (for example adding a skill), read `docs/references/skill-install-system.md` — it maps the install pipeline in `packages/claude-dev-env/bin/install.mjs`.

## Additional Non-overlapping Rules

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
2. **es.exe** — file-system search by name/path/extension/size/date (Everything CLI)
3. **Grep/Glob** — content and pattern matching
