---
name: session-tidy
description: Audit, clean, and consolidate session logs in the Obsidian vault. Fixes format drift, resolves orphaned next-steps, updates stale statuses, and generates project rollup summaries. Use when session logs feel cluttered or before starting a new project milestone. Triggers on '/session-tidy', 'tidy sessions', 'clean up session logs', 'session audit'.
disable-model-invocation: true
---

# Session Tidy: Session Log Consolidation

## Overview

Audit and consolidate session logs in the Obsidian vault (`sessions/[Project]/`) by enforcing the format contract, categorizing uncategorized files into project subfolders, resolving orphaned next-steps, updating stale statuses, and generating project rollup summaries.

**Announce at start:** "Running session log consolidation."

**Context:** Standalone maintenance utility. Run periodically, after completing a project milestone, or when starting fresh on a project. Companion to `/dream` (memory consolidation) and `/session-log` (session creation).

## The Format Contract

Source: `journal:session-log` skill definition. Read that skill's SKILL.md if you need to verify the authoritative format.

**Directory structure:** `sessions/[Project]/[N]. [Title].md`
- Each project gets its own subfolder under `sessions/`
- Session files are named `[N]. [Title].md` where Title is a 2-5 word summary of the primary outcome (e.g., `3. Amazon Auth Migration.md`)
- Summary files are named `Summary.md` in the same project folder
- No parenthetical suffixes like `(Wrap-Up)`
- Files missing a title (e.g., `Session 1.md` or `1.md`) should be flagged for renaming -- read the content to derive a title

**Required frontmatter fields:**
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

**Content structure:**
- Section headers (`###`) use one emoji + outcome-oriented title
- Valid emojis: ✅ (done), 🚫 (blocked), ⚠️ (note), 🔧 (in-progress), 📋 (queued)
- Explanatory paragraphs under each header, not just bullets
- Tables for 3+ rows of structured data
- No play-by-play or process narration

## The Process

### Phase 0: Preflight

Determine which storage backend is available. Try in this order and use the first that succeeds:

1. **Headless vault** -- run `ob --version` via Bash to verify the obsidian-headless CLI is installed. Then check `OBSIDIAN_VAULT_PATH` environment variable or `~/.claude/vault/` for a vault directory. If the CLI exists and a vault directory resolves, set `backend = "headless"`.

2. **Obsidian MCP** -- call `mcp__obsidian__list_directory` with `path="sessions"`. If it succeeds, set `backend = "obsidian"`.

3. **Local vault** -- use `~/.claude/vault/` as a local vault directory. Create it via `mkdir -p ~/.claude/vault/sessions` if it does not exist. Set `backend = "local"`.

**Headless and local capability notes:** When running without Obsidian MCP, the following operations use alternative methods:
- **Move/rename:** `mv` via Bash
- **Frontmatter update:** Read + modify YAML + Write
- **Search:** Bash `ls` + Grep

### Phase 1: Audit

List project subdirectories in `sessions/` via `mcp__obsidian__list_directory`. For each project folder, read its files via `mcp__obsidian__read_note`. Also check for any files sitting directly in `sessions/` (uncategorized). For each file, check:

1. **Naming convention?** Must match `[N]. [Title].md` where N is the session number and Title is a 2-5 word outcome summary. Flag bracket prefixes, date-only names, parenthetical suffixes, or legacy `Session [N].md` patterns missing a title.
2. **Frontmatter complete?** All required fields present: `type`, `project`, `session`, `date`, `status`, `blocked`, `tags`.
3. **Type correct?** Must be `session-report`. Flag other types like `rule-audit`.
4. **Status coherent?** `status: "completed"` with `blocked: true` is contradictory. `status: "in-progress"` or `status: "blocked"` on sessions older than 7 days is likely stale.
5. **Orphaned next-steps?** Scan content for sections containing "Next", "Queued", "Session N+1", "TODO", or clipboard emoji sections. Cross-reference against subsequent sessions for the same project to determine if the items were addressed.
6. **Categorized?** Files sitting directly in `sessions/` (not in a project subfolder) are uncategorized. Infer the project name from the filename pattern (e.g., `BudgetBridge Session 3.md` belongs in `sessions/BudgetBridge/`) or from the frontmatter `project` field. Flag for move into the correct subfolder.

### Phase 2: Propose Changes

Present a structured report:

**Format violations** -- files with wrong naming, missing/wrong frontmatter fields, wrong type
**Stale statuses** -- in-progress or blocked sessions older than 7 days, contradictory status+blocked combos
**Orphaned next-steps** -- queued items from session N with no evidence of resolution in session N+1 or later. For each item, state whether it was:
  - **Resolved:** found evidence in a later session
  - **Orphaned:** no later session addresses it
  - **Unknown:** later sessions exist but don't clearly address or skip the item
**Uncategorized files** -- files in `sessions/` root that should be moved into a project subfolder
**Rollup candidates** -- projects with 3+ sessions that have no rollup/summary session
**Proposed actions** -- numbered list of specific changes

Do NOT execute any changes yet. Wait for user approval.

### Phase 3: Execute

After user approves (all or selected items):

1. **Rename** non-conforming files via `mcp__obsidian__move_note`.
2. **Fix frontmatter** via `mcp__obsidian__update_frontmatter` -- set correct type, add missing fields.
3. **Update stale statuses** -- change old in-progress/blocked to completed (or ask user for correct status).
4. **Clean orphaned next-steps** -- for confirmed orphaned items, either:
   - Remove the section if all items are orphaned and the session is old
   - Add a strikethrough or "(not pursued)" annotation if some items remain relevant
   - Leave unchanged if user declines
5. **Generate project rollups** -- for each qualifying project, write a summary note via `mcp__obsidian__write_note`:
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
6. **Categorize uncategorized files** -- move files from `sessions/` root into the correct project subfolder via `mcp__obsidian__move_note`. When moving, rename to match the `[N]. [Title].md` convention (e.g., `sessions/BudgetBridge Session 3.md` becomes `sessions/BudgetBridge/3. [Title derived from content].md`).

### Phase 4: Verify

After execution, re-read the vault and confirm:
- Every session file lives in a project subfolder under `sessions/[Project]/`
- Every file has valid frontmatter with all required fields
- Every filename matches the naming convention (`[N]. [Title].md` or `Summary.md`)
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
