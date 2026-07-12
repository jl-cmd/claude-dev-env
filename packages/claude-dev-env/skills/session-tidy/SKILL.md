---
name: session-tidy
description: Audit, clean, and consolidate session logs in the Obsidian vault. Fixes format drift, resolves orphaned next-steps, updates stale statuses, and generates project rollup summaries. Use when session logs feel cluttered or before starting a new project milestone. Triggers on '/session-tidy', 'tidy sessions', 'clean up session logs', 'session audit'.
disable-model-invocation: true
---

# Session Tidy: Session Log Consolidation

## Overview

Audit and consolidate session logs in the Obsidian vault (`sessions/[Project]/`) by enforcing the tidy audit rules, categorizing uncategorized files into project subfolders, resolving orphaned next-steps, updating stale statuses, and generating project rollup summaries.

**Announce at start:** "Running session log consolidation."

**Context:** Standalone maintenance utility. Run periodically, after completing a project milestone, or when starting fresh on a project. Companion to `/dream` (memory consolidation) and `/session-log` (session creation).

## The Format Contract

**Write-side HTML contract:** `/session-log` owns how new session reports are written — vault path, HTML frontmatter comment block, Artifact publish, and body design. Read `journal:session-log` SKILL.md for that contract. The markdown field shapes below describe files tidy may read; they are not the write path for new session reports.

**What tidy audits:** Project folders under `sessions/` may hold `.html` session reports and `.md` session files. Audit every session file present. The rules in this skill are the single home for tidy audit criteria.

**Directory structure:** `sessions/[Project]/`
- Session files match `[N]. [Title].html` or `[N]. [Title].md`, where Title is a 2-5 word summary of the primary outcome (e.g., `3. Amazon Auth Migration.html`)
- Summary files are `Summary.html` or `Summary.md` in the same project folder
- No parenthetical suffixes like `(Wrap-Up)`
- Files missing a title (e.g., `Session 1.md` or `1.html`) should be flagged for renaming — read the content to derive a title

**Shared metadata fields (required on every session file):**
`type`, `project`, `session`, `date`, `status`, `blocked`, `tags`

**HTML session reports** — when tidy reads a `.html` session file, metadata sits in an HTML comment block at the start of the file content. The write-side comment shape lives in session-log SKILL.md. HTML reports also carry `session_id` and `vault_context_retrieved`.

**Markdown session files** — when tidy reads a `.md` session file, metadata sits in YAML frontmatter:

```yaml
---
type: session-report
project: "[name]"
session: [N]
date: "[YYYY-MM-DD]"
status: "completed" | "in-progress" | "blocked"
blocked: true | false
tags: ["session", "[project-tag]"]
---
```

**Content structure for markdown session files:**
- Section headers (`###`) use one emoji + outcome-oriented title
- Valid emojis: ✅ (done), 🚫 (blocked), ⚠️ (note), 🔧 (in-progress), 📋 (queued)
- Explanatory paragraphs under each header, not just bullets
- Tables for 3+ rows of structured data
- No play-by-play or process narration

**Content structure for HTML session reports:** Body shape is session-specific (session-log designs per session). Tidy does not enforce a fixed HTML section template. Audit naming, metadata completeness, type, status coherence, orphaned next-steps text in the body, and categorization.

## The Process

### Phase 0: Preflight

Determine which storage backend is available. First success wins:

1. **Headless vault** — same check as Backend Detection in `journal:session-log` SKILL.md: Bash `ob --version`, then `OBSIDIAN_VAULT_PATH` or `~/.claude/vault/`. When the CLI check succeeds and a vault directory resolves, set `backend = "headless"`.

2. **Obsidian MCP** — call `mcp__obsidian__list_directory` with `path="sessions"`. If it succeeds, set `backend = "obsidian"`.

3. **Local vault** — same fallback as session-log Backend Detection: `~/.claude/vault/`. Create `~/.claude/vault/sessions` via `mkdir -p` if missing. Set `backend = "local"`.

**Capability notes by backend:**
- **obsidian:** list, read, move, frontmatter update, and write via MCP tools (`list_directory`, `read_note`, `move_note`, `update_frontmatter`, `write_note`). For `.html` files, metadata edits use Read + Edit of the HTML comment block when MCP frontmatter tools do not apply.
- **headless / local:** Move/rename via `mv` (Bash). Metadata update via Read + Edit/Write. Search via Bash `ls` + Grep.

### Phase 1: Audit

List project subdirectories in `sessions/` (MCP `list_directory` when backend is obsidian; Bash `ls` when headless or local). For each project folder, read its files. Also check for any files sitting directly in `sessions/` (uncategorized). Audit both `.html` and `.md` session files. For each file, check:

1. **Naming convention?** Must match `[N]. [Title].html` or `[N]. [Title].md` where N is the session number and Title is a 2-5 word outcome summary. Flag bracket prefixes, date-only names, parenthetical suffixes, or patterns missing a title such as `Session 1.md` or `1.html`.
2. **Frontmatter complete?** All shared required fields present: `type`, `project`, `session`, `date`, `status`, `blocked`, `tags`. For `.html` session reports, also require `session_id` and `vault_context_retrieved`.
3. **Type correct?** Must be `session-report`. Flag other types.
4. **Status coherent?** `status: completed` with `blocked: true` is contradictory. `status: in-progress` or `status: blocked` on sessions older than 7 days is likely stale.
5. **Orphaned next-steps?** Scan content for sections containing "Next", "Queued", "Session N+1", "TODO", or clipboard emoji sections. Cross-reference against subsequent sessions for the same project to determine if the items were addressed.
6. **Categorized?** Files sitting directly in `sessions/` (not in a project subfolder) are uncategorized. Infer the project name from the filename pattern (e.g., `BudgetBridge Session 3.md` belongs in `sessions/BudgetBridge/`) or from the frontmatter `project` field. Flag for a move into the correct subfolder.

### Phase 2: Propose Changes

Present a structured report:

**Format violations** -- files with wrong naming, missing/wrong frontmatter fields, wrong type
**Stale statuses** -- in-progress or blocked sessions older than 7 days, contradictory status+blocked combos
**Orphaned next-steps** -- queued items from session N with no evidence of resolution in session N+1 or later. For each item, state whether it was:
  - **Resolved:** found evidence in a later session
  - **Orphaned:** no later session addresses it
  - **Unknown:** later sessions exist but don't clearly address or skip the item
**Uncategorized files** -- files in `sessions/` root that should live in a project subfolder
**Rollup candidates** -- projects with 3+ sessions that have no `Summary.html` or `Summary.md`
**Proposed actions** -- numbered list of specific changes

Do NOT execute any changes yet. Wait for user approval.

### Phase 3: Execute

After user approves (all or selected items):

1. **Rename** non-conforming files via `mcp__obsidian__move_note` (obsidian) or `mv` (headless/local). Keep the file's extension (`.html` or `.md`).
2. **Fix frontmatter:**
   - `.md` files: `mcp__obsidian__update_frontmatter` when backend is obsidian; Read + Edit/Write of YAML frontmatter when headless or local. Set correct type; add missing shared fields.
   - `.html` files: Read + Edit of the HTML comment block fields (shape in session-log SKILL.md). Set correct type; add missing shared fields plus `session_id` and `vault_context_retrieved` when absent.
3. **Update stale statuses** -- change old in-progress/blocked to completed (or ask user for correct status).
4. **Clean orphaned next-steps** -- for confirmed orphaned items, either:
   - Remove the section if all items are orphaned and the session is old
   - Add a strikethrough or "(not pursued)" annotation if some items remain relevant
   - Leave unchanged if user declines
5. **Generate project rollups** -- for each qualifying project, write a summary note via `mcp__obsidian__write_note` (obsidian) or Write (headless/local):
   - **Path:** `sessions/[Project]/Summary.md`
   - **Frontmatter:** `{"type": "project-summary", "project": "[name]", "sessions": [count], "date_range": "[first] to [last]", "tags": ["summary", "[project-tag]"]}`
   - **Content:** Use this template:

```markdown
## [Project] -- Project Summary

### Timeline

| # | Title | Date | Status |
|---|-------|------|--------|
| 1 | [title from filename] | [date] | ✅/🔧/🚫 |

### Key Outcomes
- **Session [N]:** [one-line summary of primary outcome]

### Current Status
[One paragraph: where the project stands now, what's active, what's done]

### Carried Forward
- [ ] [unresolved item from latest session]
```
6. **Categorize uncategorized files** -- move files from `sessions/` root into the correct project subfolder via `mcp__obsidian__move_note` or `mv`. When moving, rename to match the `[N]. [Title].html` or `[N]. [Title].md` convention for that file's extension (e.g., `sessions/BudgetBridge Session 3.md` becomes `sessions/BudgetBridge/3. [Title derived from content].md`).

### Phase 4: Verify

After execution, re-read the vault and confirm:
- Every session file lives in a project subfolder under `sessions/[Project]/`
- Every file has valid frontmatter with all required fields for its shape
- Every filename matches the naming convention (`[N]. [Title].html`, `[N]. [Title].md`, `Summary.html`, or `Summary.md`)
- No contradictory status/blocked combos
- All orphaned next-steps resolved or annotated
- Rollup summaries exist for qualifying projects

Report the results: files renamed, frontmatter fixed, statuses updated, next-steps resolved, rollups generated.

If Phase 1 finds zero issues across all checks, skip Phases 2-4 and report: "All session logs are tidy. Nothing to do."

## Output Format

Phase 2 report structure:

```
## Session Tidy Report

### Format Violations (X found)
- [file] -- [issue]

### Stale Statuses (X found)
- [file] -- [status] since [date] ([age] days ago)

### Uncategorized Files (X found)
- [file] -- move to sessions/[Project]/[new filename]

### Orphaned Next-Steps (X found)
- [file] -- "[item text]" -- [resolved/orphaned/unknown]

### Rollup Candidates (X projects)
- [project] -- [N] sessions, [date range], no summary exists

### Proposed Actions
1. [action] -- [file] -- [reason]
2. ...

Approve all, select by number, or cancel?
```

## After Completion

Report summary: files renamed, frontmatter fixes, status updates, next-steps cleaned, rollups generated.

## Best Practices

- Run after finishing a multi-session project
- Run before starting a new milestone on an existing project (clears stale context)
- Cross-reference next-steps manually when the skill flags "unknown" -- it cannot determine intent from content alone
- The 7-day staleness threshold is a heuristic -- adjust based on how frequently you session-log
- Rollup summaries are not a replacement for individual session logs -- they are a navigational aid
