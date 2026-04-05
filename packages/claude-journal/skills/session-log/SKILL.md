---
name: session-log
description: Log a session report to the Obsidian vault, track vault context usage, extract unrecorded decisions, tidy the project's session folder, and output a /rename command. Use when the user says /session-log, journal this session, log this work, session report, or any variation of "summarize/log/record this session". Also triggers on "save session", "capture session", or "document what we did".
---

# Session Log

## Overview

Write a structured session report, then run vault context tracking, decision extraction, and session tidying.

**Announce at start:** "I'm logging this session."

This skill runs as a 5-step workflow. Every step runs automatically -- no user prompts between steps except where noted.

## Backend Detection (run before Step 1)

Determine which storage backend is available. Try in this order and use the first that succeeds:

1. **Headless vault** -- run `ob --version` via Bash to verify the obsidian-headless CLI is installed. Then check `OBSIDIAN_VAULT_PATH` environment variable or `~/.claude/vault/` for a vault directory. If the CLI exists and a vault directory resolves, optionally run `ob sync-status --path <vault-path>` to verify sync is active. Set `backend = "headless"`.

2. **Obsidian MCP** -- call `mcp__obsidian__list_directory` with `path="sessions"`. If it succeeds, use Obsidian MCP for all operations. Set `backend = "obsidian"`.

3. **Local vault** -- if neither headless nor MCP is available, use `~/.claude/vault/` as a local vault directory. Create it via `mkdir -p ~/.claude/vault/sessions` if it does not exist. Set `backend = "local"`. This provides a working vault structure that can be upgraded to headless sync later.

**Backend capabilities:**

| Capability | headless | obsidian | local |
|---|---|---|---|
| Write session reports | Write tool | `mcp__obsidian__write_note` | Write tool |
| Search prior sessions | Bash `ls` + Grep | `mcp__obsidian__search_notes` | Bash `ls` + Grep |
| Session number detection | parse filenames | frontmatter search | parse filenames |
| Frontmatter | YAML `---` fences | handled by MCP | YAML `---` fences |
| Step 2 (vault context tracking) | skip | runs | skip |
| Step 4 (session tidy) | skip | runs | skip |
| Sync | Obsidian Sync | Obsidian Sync | none (local only) |

**Session number detection (headless and local):**
- List files in the project directory via Bash `ls`
- Parse filenames matching `[N]. *.md`
- Highest N + 1. If directory does not exist, create it and start at 1

**Output paths:**
- headless: `$OBSIDIAN_VAULT_PATH/sessions/[Project]/[N]. [Title].md` or `~/.claude/vault/sessions/[Project]/[N]. [Title].md`
- obsidian: `sessions/[Project]/[N]. [Title].md` (vault-relative)
- local: `~/.claude/vault/sessions/[Project]/[N]. [Title].md`

Announce the backend: "Using headless vault at [path].", "Using Obsidian vault.", or "Using local vault at ~/.claude/vault/. Run `/obsidian-check` for upgrade options."

---

## Step 1: Write Session Report

1. Review the conversation to identify: key outcomes, blockers, decisions, and next steps.

2. Determine session metadata:
   - **Project name:** infer from conversation context
   - **Session number:** search existing vault notes to find the latest session number for this project, then increment. Use `mcp__obsidian__search_notes` with `searchFrontmatter: true` and the project name. If no prior sessions exist, start at 1.
   - **Date:** today's date
   - **Title:** a 2-5 word summary of the session's primary outcome or focus area. Pick the single most important thing that happened. Examples: "Amazon Auth Migration", "Source Loading Fix", "Vault Reorganization". Avoid generic titles like "Bug Fixes" or "Various Updates".

3. **Write to vault** via `mcp__obsidian__write_note`:
   - **Path:** `sessions/[Project]/[N]. [Title].md`
   - **Frontmatter:** `{"type": "session-report", "project": "[name]", "session": [N], "date": "[YYYY-MM-DD]", "status": "completed"|"in-progress"|"blocked", "blocked": true|false, "tags": ["session", "[project-tag]"]}`
   - **Content:** Markdown formatted (see Vault Format below)

4. **Backend-specific write:**
   - **headless:** Write tool to the headless vault path. Include frontmatter as YAML `---` fences at the top of the file. Create the project directory via `mkdir -p` if it does not exist.
   - **obsidian:** `mcp__obsidian__write_note` with path and frontmatter object
   - **local:** Write tool to `~/.claude/vault/sessions/[Project]/[N]. [Title].md`. Include frontmatter as YAML `---` fences. Create the project directory via `mkdir -p` if it does not exist.
   - **If the write fails:** output the content in the conversation so the user can copy it manually. Skip Steps 2-4 and go directly to Step 5.

### Vault Format -- Markdown Session Report

The vault note uses markdown (not HTML).

```markdown
## Session [N] Report -- [Month Day, Year]

### [emoji] [Section Title]

[1-3 sentence explanation of what happened and why it matters]

- **[Label]:** [detail]

**Fix:** [what was done]

### [emoji] [Section with tabular data]

[Context sentence]

| # | Item | Status |
|---|------|--------|
| 1 | ...  | ...    |

### [emoji] Notes

- **[Topic]:** [detail]
```

### Emoji Status Indicators

| Emoji | Meaning | Use when |
|-------|---------|----------|
| ✅ | Done/Fixed | A problem was resolved or a deliverable completed |
| 🚫 | Blocked | Something couldn't be done (external limit, dependency, etc.) |
| ⚠️ | Warning/Note | Important context, gotchas, or things to remember |
| 🔧 | In Progress | Work started but not finished |
| 📋 | Queued | Work identified but not yet started |

### Formatting Rules

- **Section headers** (`###`) get one emoji + descriptive title
- **Explanatory paragraphs** under each header -- not just bullets. Explain what happened and why.
- **Bold inline labels** for key facts: `**Fix:**`, `**Account:**`, etc.
- **Tables** for anything with 3+ rows of structured data (queued items, test results, file lists)
- **Bullets** for lists of 2+ related items
- **Links** where useful: file paths, URLs, PR links as markdown links

### What NOT to include

- Play-by-play of debugging steps or failed approaches
- Process narration ("First I tried X, then Y")
- Redundant sections -- if nothing was blocked, skip the blocked section

### Example

```markdown
## Session 6 Report -- March 27, 2026

### ✅ Developer Docs Sources Fixed

Both Developer Docs notebooks that had been broken since Session 5 are now fully loaded with working sources:

- **Notebook #28 -- Building with Claude & Tools:** 52 sources loaded (all green)
- **Notebook #29 -- Agent SDK & Testing:** 49 sources loaded (all green)

**Fix:** Swapped `platform.claude.com/docs/en/X.md` URLs to `docs.anthropic.com/en/docs/X` (drop .md, swap domain). Tested one URL first, then bulk-loaded.

### 🚫 Audio Generation Blocked

All 10 Audio Overviews (8 System Card + 2 Developer Docs) are ready to generate but hit the daily limit wall. The 19 overviews from Session 5 (15 Academy + 4 Opus) are still within the rolling 24-hour window.

### ⚠️ Session 7 Notes

- **Account:** Notebooks live under secondary@example.com (authuser=1), NOT the default primary@example.com.
- **Audio budget:** Once the 24h window resets, all 10 overviews fit within the 20/day Pro limit.
```

---

## Step 2: Vault Context Tracking

This step runs automatically after Step 1 completes.

1. **Check vault context usage.** Review the conversation history for any use of these MCP tools (excluding this skill's own calls during Step 1):
   - `mcp__obsidian__search_notes`
   - `mcp__obsidian__read_note`
   - `mcp__obsidian__read_multiple_notes`

   If any were used, set `vault_context_retrieved: true`. Otherwise `false`.
   If true, also note which vault notes were read (list the paths).

2. **Update frontmatter.** Use `mcp__obsidian__update_frontmatter` to add the tracking field:
   ```
   mcp__obsidian__update_frontmatter(
     path="[session note path from Step 1]",
     frontmatter={"vault_context_retrieved": true|false},
     merge=true
   )
   ```
   If `update_frontmatter` fails, fall back to: read the note with `mcp__obsidian__read_note`, add the field to frontmatter manually, rewrite with `mcp__obsidian__write_note`.

3. **Append tracking line.** Use `mcp__obsidian__patch_note` to append a vault context line to the Notes section (or end of the note if no Notes section exists):
   - If retrieved: `- **Vault context:** Retrieved ([list of note paths])`
   - If not retrieved: `- **Vault context:** Not retrieved`

   If `patch_note` fails, fall back to read-modify-write via `read_note` + `write_note`.

---

## Step 3: Decision Extraction

This step runs automatically after Step 2 completes.

Scan the conversation for decisions, gotchas, or architectural choices that were not already saved via `/remember` or to memory. For each one found, ask the user:

> "I noticed this decision: [summary]. Want me to save it to the vault with /remember?"

Only write decision notes the user confirms. If no unrecorded decisions are found, skip silently.

---

## Step 4: Session Tidy (Project Scope)

This step runs automatically after Step 3 completes. It runs a scoped version of `/session-tidy` -- only for the current project's session folder, not the entire vault.

1. **List files** in `sessions/[Project]/` via `mcp__obsidian__list_directory`.

2. **Quick audit** each file for:
   - **Naming convention:** must match `[N]. [Title].md`
   - **Frontmatter completeness:** all required fields present (`type`, `project`, `session`, `date`, `status`, `blocked`, `tags`)
   - **Status coherence:** `status: "completed"` with `blocked: true` is contradictory. `status: "in-progress"` or `status: "blocked"` on sessions older than 7 days is stale.

3. **Auto-fix minor issues silently:**
   - Missing frontmatter fields that can be inferred (e.g., `blocked: false` when status is `completed`)
   - Type field set to wrong value (correct to `session-report`)

4. **Report issues that need user input:**
   - Files with wrong naming convention (propose new name)
   - Stale statuses (propose update to `completed` or ask)
   - Contradictory status/blocked combos

   If no issues are found, skip silently. Do not report "all clean."

5. **Rollup check:** if the project has 5+ sessions and no `Summary.md`, mention it:
   > "This project has [N] sessions and no summary. Run `/session-tidy` for a full rollup."

---

## Step 5: Finalize

Copy a `/rename` command to the user's clipboard using `echo -n "/rename [Project] - [Primary Outcome]" | clip.exe`, then tell the user:

> "Copied `/rename [Project] - [Primary Outcome]` to your clipboard. Paste it to rename this session."

The primary outcome comes from the session title determined in Step 1.

---

## Best Practices

- Each section in the session report is an outcome, not a process step ("Sources Fixed" not "We debugged source loading")
- Body should be self-contained -- no context needed beyond the note itself
- If the session was exploratory with no concrete outcome, use 🔧 or 📋 sections to describe what was investigated and what's next
- Keep it scannable: a reader should grasp the session in 15 seconds from headers alone
- Tables are powerful -- use them whenever you have structured data (queued work, test results, file inventories)
