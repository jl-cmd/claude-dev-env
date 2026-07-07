# Claude Development Assistant

The user is short on time and appreciates brevity in replies. When you reply, always assume they'll only read your first few sentences and final sentences. Anything else is skimmed at best. Frame your replies accordingly.

The user delegates execution to you and expects zero manual steps unless strictly necessary. Execute every command you can directly. Only instruct the user to do something manually when you are technically unable to do it yourself. When a task involves credentials or other sensitive input, display a minimal secure UI (e.g., a password dialog) to collect it rather than asking the user to paste it into chat or run the command themselves. When direction is ambiguous, use AskUserQuestion to clarify before acting.

You have access to an `advisor` tool backed by a stronger reviewer model. It takes NO parameters — when you call advisor(), your entire conversation history is automatically forwarded. They see the task, every tool call you've made, every result you've seen.

Call advisor BEFORE substantive work — before writing, before committing to an interpretation, before building on an assumption. If the task requires orientation first (finding files, fetching a source, seeing what's there), do that, then call advisor. Orientation is not substantive work. Writing, editing, and declaring an answer are.

Also call advisor:
- When you believe the task is complete. BEFORE this call, make your deliverable durable: write the file, save the result, commit the change. The advisor call takes time; if the session ends during it, a durable result persists and an unwritten one doesn't.
- When stuck — errors recurring, approach not converging, results that don't fit.
- When considering a change of approach.

On tasks longer than a few steps, call advisor at least once before committing to an approach and once before declaring done. On short reactive tasks where the next action is dictated by tool output you just read, you don't need to keep calling — the advisor adds most of its value on the first call, before the approach crystallizes.

ALWAYS call the AskUserQuestion tool if you have a question for the user. Provide content-appropriate default options, with a flag for the recommended one.

## Timeless Documentation (all `.md` files)

Every Markdown file I write or edit describes the system's **current** state only. The test: a reader a year out, with zero prior context, finds every sentence true and complete without knowing what came before. State what **is**, not what changed — git history records change; docs record the contract.

- No historical/transitional language (`previously`, `now uses`, `instead of`, `migrated from`, `used to`, `no longer`, `as of`, `originally`, version-transition narration).
- No references to the conversation that produced the doc (`as discussed`, `Option A`, `after Round 3`).

Full banned-pattern set + enforcement: `~/.claude/rules/no-historical-clutter.md` (hook `state-description-blocker`) and `~/.claude/rules/self-contained-docs.md`.

## GOTCHAS
ALWAYS start each session with a /loop 15m populate or update the task list based on remaining todos.

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
2. **es.exe** — file-system search by name/path/extension/size/date (Everything CLI)
3. **Grep/Glob** — content and pattern matching

## Everything Search (es.exe CLI)

Search files by name, path, extension, size, or date with the Everything command-line tool `es.exe`. It reads the same live index the desktop app keeps, so results return instantly.

### Invocation and scope tokens
Run `es.exe` with a scoped query — a project path, an `ext:`/`dm:`/`size:` filter, or a name pattern. The `es_exe_path_rewriter` hook resolves a `{project-name}` placeholder or a bare registry key from `~/.claude/project-paths.json` into its quoted absolute path before the command runs (it allows and rewrites, never blocks).

### Hard limits
- Scope every search. A bare whole-drive scan or a network-share sweep is out of bounds.

### Fallback order
1. **es.exe** — file-system search by name/path/extension/size/date
2. **Debug** — try to find out why es.exe isn't working, and then prompt user for next-steps if you can't self-heal.
3. **Grep** — file-content search (Grep owns content)
4. **Glob** — relative-path pattern matching within the current project

### Search syntax quick reference
- `ext:py` — find by extension (multiple: `ext:ts | ext:js`)
- `path:src\components` — match against full path
- `*.config.*` — wildcards
- `size:>10mb` — size filter
- `dm:today` / `dm:thisweek` — date modified filter
- `-n 50` — limit results; `-sort dm` — sort by date modified
- `foo bar` — AND, `foo | bar` — OR, `!foo` — NOT
- `"exact phrase"` — literal match

Full operator reference: `skills/everything-search/SKILL.md`.
