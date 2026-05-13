---
name: session-log
description: >-
  Log a session report as a styled HTML file in the vault, track vault context usage, extract unrecorded decisions, tidy the project's session folder, publish via /doc-gist as a shareable webpage, and output a /rename command. Use when the user says /session-log, journal this session, log this work, session report, or any variation of "summarize/log/record this session". Also triggers on "save session", "capture session", or "document what we did".
---

# Session Log

## Overview

Write a structured session report as HTML, then run vault context tracking, decision extraction, session tidying, publish via /doc-gist, and finalize with a /rename clipboard hand-off.

**Announce at start:** "I'm logging this session."

This skill runs as a 6-step workflow. Every step runs automatically -- no user prompts between steps except where noted.

## Gotchas

- **HTML output, not Markdown.** The repo's `md_to_html_blocker` PreToolUse hook rejects Write/Edit on `.md` files outside `.claude/` directories. Headless vault paths (e.g., `$OBSIDIAN_VAULT_PATH`) resolve outside `.claude/`, so session reports use HTML. (The local vault at `~/.claude/vault/` is exempt, but HTML is the uniform format regardless of backend.)
- **Avoid historical and comparative language.** The `state_description_blocker` hook enforces this for markdown and code files. While the hook does not scan `.html`, the same present-tense, current-state style applies to session reports. The trigger pattern set lives in `~/.claude/rules/no-historical-clutter.md`.
- **doc-gist uses `--description` for gist title text.** `gist_upload.py` uploads HTML verbatim with no content parsing. Pass `--description "Session [N] — [Title]"` to set the gist description.
- **doc-gist preview URL takes a few seconds.** The htmlpreview.github.io renderer fetches the raw gist on first hit. Quote both URLs and tell the user to refresh once if the page is blank.
- **gh must be authenticated.** Running gist_upload.py with `gh` unauthenticated prints the auth prompt and exits non-zero. Surface that message to the user; the local HTML file in the vault is still the canonical artifact, so Step 6 still runs.
- **Obsidian frontmatter index is sacrificed.** Obsidian's native YAML-frontmatter parser reads only `.md` files. HTML files do not appear in the Obsidian UI's frontmatter index. Search by content still works; search by `type: session-report` does not.
- **Existing files require the Edit tool.** The `write_existing_file_blocker` hook rejects the Write tool on existing paths. Use Write only when creating a fresh session report; use Edit for Step 2's append and Step 4's auto-fixes.

## Backend Detection (run before Step 1)

Determine which storage backend is available. Try in this order and use the first that succeeds:

1. **Headless vault** -- run `ob --version` via Bash to verify the obsidian-headless CLI is installed. Then check `OBSIDIAN_VAULT_PATH` environment variable or `~/.claude/vault/` for a vault directory. If the CLI exists and a vault directory resolves, optionally run `ob sync-status --path <vault-path>` to verify sync is active. Set `backend = "headless"`.

2. **Local vault** -- fall back to `~/.claude/vault/` as a local vault directory. Create it via `mkdir -p ~/.claude/vault/sessions` if it does not exist. Set `backend = "local"`. This provides a working vault structure that can be upgraded to headless sync later.

**Backend capabilities:**

| Capability | headless | local |
|---|---|---|
| Write session reports | Write tool to `.html` path | Write tool to `.html` path |
| Search prior sessions | Bash `ls` + Grep | Bash `ls` + Grep |
| Session number detection | parse filenames | parse filenames |
| Frontmatter | YAML inside HTML comment | YAML inside HTML comment |
| Sync | Obsidian Sync | none (local only) |

**Session number detection:**
- List files in the project directory via Bash `ls`
- Parse filenames matching `[N]. *.html` or `[N]. *.md` to preserve sequence across the format migration
- Highest N + 1. If directory does not exist, create it and start at 1

**Output paths:**
- headless: `$OBSIDIAN_VAULT_PATH/sessions/[Project]/[N]. [Title].html` (falls back to `~/.claude/vault/` when the env var is unset)
- local: `~/.claude/vault/sessions/[Project]/[N]. [Title].html`

Announce the backend: "Using headless vault at [path]." or "Using local vault at ~/.claude/vault/. Run `/obsidian-check` for upgrade options."

---

## Step 1: Write Session Report (HTML)

1. Review the conversation to identify: key outcomes, blockers, decisions, and next steps.

2. Determine session metadata:
   - **Project name:** infer from conversation context
   - **Session number:** list the project's vault folder via Bash `ls`, parse `[N]. *.html` and `[N]. *.md` filenames, take highest+1. If no prior sessions, start at 1.
   - **Date:** today's date
   - **Title:** a 2-5 word summary of the session's primary outcome or focus area. Pick the single most important thing that happened. Examples: "Amazon Auth Migration", "Source Loading Fix", "Vault Reorganization". Avoid generic titles like "Bug Fixes" or "Various Updates".

3. **Write to the vault path** via the Write tool. Create the project directory via `mkdir -p` if it does not exist. If the write fails, output the content in the conversation so the user can copy it manually. Skip Steps 2-5 and go directly to Step 6.

### Vault Format -- HTML Session Report

The vault note is a self-contained HTML file. Frontmatter lives inside an HTML comment so it is human-readable but does not affect rendering. Styling is minimal so doc-gist's template wraps the body cleanly in Step 5.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Session [N] — [Title]</title>
</head>
<body>
<!--
type: session-report
project: [name]
session: [N]
date: [YYYY-MM-DD]
status: completed|in-progress|blocked
blocked: true|false
tags: [session, [project-tag]]
-->

<h1>Session [N] Report — [Month Day, Year]</h1>

<h2>[emoji] [Section Title]</h2>
<p>[1-3 sentence explanation of what happened and why it matters]</p>
<ul>
  <li><strong>[Label]:</strong> [detail]</li>
</ul>
<p><strong>Fix:</strong> [what was done]</p>

<h2>[emoji] [Section with tabular data]</h2>
<p>[Context sentence]</p>
<table>
  <thead><tr><th>#</th><th>Item</th><th>Status</th></tr></thead>
  <tbody>
    <tr><td>1</td><td>...</td><td>...</td></tr>
  </tbody>
</table>

<h2>[emoji] Notes</h2>
<ul>
  <li><strong>[Topic]:</strong> [detail]</li>
</ul>

</body>
</html>
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

- **Section headers** (`<h2>`) get one emoji + descriptive title
- **Explanatory paragraphs** (`<p>`) under each header -- not just bullets. Explain what happened and why.
- **Bold inline labels** for key facts: `<strong>Fix:</strong>`, `<strong>Account:</strong>`, etc.
- **Tables** (`<table>`) for anything with 3+ rows of structured data (queued items, test results, file lists)
- **Bullets** (`<ul><li>`) for lists of 2+ related items
- **Links** (`<a href="...">`) where useful: file paths, URLs, PR links
- **No inline `style=` attributes and no `<style>` block.** Doc-gist wraps the body in its own template; inner styles fight the wrapper.

### What NOT to include

- Play-by-play of debugging steps or failed approaches
- Process narration ("First I tried X, then Y")
- Redundant sections -- if nothing was blocked, skip the blocked section
- Historical or comparative language — see `~/.claude/rules/no-historical-clutter.md` for the trigger pattern set. The `state_description_blocker` hook rejects writes containing these patterns in markdown/code; the same rule applies to session report HTML.

### Example

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Session 6 — Developer Docs Sources Fixed</title>
</head>
<body>
<!--
type: session-report
project: claude-academy
session: 6
date: 2026-03-27
status: completed
blocked: false
tags: [session, claude-academy]
-->

<h1>Session 6 Report — March 27, 2026</h1>

<h2>✅ Developer Docs Sources Fixed</h2>
<p>Both Developer Docs notebooks load fully with working sources:</p>
<ul>
  <li><strong>Notebook #28 — Building with Claude &amp; Tools:</strong> 52 sources loaded (all green)</li>
  <li><strong>Notebook #29 — Agent SDK &amp; Testing:</strong> 49 sources loaded (all green)</li>
</ul>
<p><strong>Fix:</strong> Use <code>docs.anthropic.com/en/docs/X</code> URLs (drop the .md extension, swap domain). Tested one URL first, then bulk-loaded.</p>

<h2>🚫 Audio Generation Blocked</h2>
<p>All 10 Audio Overviews are ready to generate but hit the daily limit wall.</p>

<h2>⚠️ Session 7 Notes</h2>
<ul>
  <li><strong>Account:</strong> Notebooks live under secondary@example.com (authuser=1), NOT the default primary@example.com.</li>
  <li><strong>Audio budget:</strong> Once the 24h window resets, all 10 overviews fit within the 20/day Pro limit.</li>
</ul>

</body>
</html>
```

---

## Step 2: Vault Context Tracking

This step runs automatically after Step 1 completes.

1. **Check vault context usage.** Review the conversation history for any use of these MCP tools (excluding this skill's own calls during Step 1):
   - `mcp__obsidian__search_notes`
   - `mcp__obsidian__read_note`
   - `mcp__obsidian__read_multiple_notes`

   Track whether vault context was used and which notes were read (if any). This determines the Notes line appended in step 2.

2. **Append a tracking line to the Notes section** via the Edit tool. Target the closing `</ul>` of the last `<h2>...Notes</h2>` block:
   - If retrieved: `<li><strong>Vault context:</strong> Retrieved ([list of note paths])</li>`
   - If not retrieved: `<li><strong>Vault context:</strong> Not retrieved</li>`

   If no Notes section exists, append a fresh one before `</body>`:
   ```html
   <h2>⚠️ Notes</h2>
   <ul>
     <li><strong>Vault context:</strong> Not retrieved</li>
   </ul>
   ```

---

## Step 3: Decision Extraction

This step runs automatically after Step 2 completes.

Scan the conversation for decisions, gotchas, or architectural choices that were not already saved via `/remember` or to memory. For each one found, ask the user:

> "I noticed this decision: [summary]. Want me to save it to the vault with /remember?"

Only write decision notes the user confirms. If no unrecorded decisions are found, skip silently.

---

## Step 4: Session Tidy (Project Scope)

This step runs automatically after Step 3 completes. Scope: the current project's session folder only.

1. **List files** in the project's vault session folder via Bash `ls`.

2. **Quick audit** each `.html` file for:
   - **Naming convention:** must match `[N]. [Title].html`
   - **Frontmatter completeness:** HTML comment block at top contains `type`, `project`, `session`, `date`, `status`, `blocked`, `tags`
   - **Status coherence:** `status: completed` with `blocked: true` is contradictory. `status: in-progress` or `status: blocked` on sessions older than 7 days is stale.

3. **Auto-fix minor issues silently** via Edit tool:
   - Missing frontmatter fields that can be inferred (e.g., `blocked: false` when status is `completed`)
   - `type` field set to a wrong value (correct to `session-report`)

4. **Report issues that need user input:**
   - Files with wrong naming convention (propose new name)
   - Stale statuses (propose update to `completed` or ask)
   - Contradictory status/blocked combos

   If no issues are found, skip silently. Do not report "all clean."

5. **Rollup check:** if the project has 5+ sessions and no `Summary.html` or `Summary.md`, mention it:
   > "This project has [N] sessions and no summary. Run `/session-tidy` for a full rollup."

---

## Step 5: Publish via /doc-gist

This step runs automatically after Step 4 completes.

### 5a. Run gist_upload.py

Hand the freshly-written HTML file to `/doc-gist` via its gist_upload.py script. Use the PowerShell tool so quoting handles spaces in the vault path:

```powershell
python "$HOME/.claude/skills/doc-gist/scripts/gist_upload.py" `
  --input "<absolute path to the .html file>" `
  --description "Session [N] — [Title] · session-log · [Project]"
```

Replace the bracketed values from Step 1's metadata. The script writes a temp copy, uploads as a secret gist, and prints two URLs to stderr — capture both:

- **Preview:** `https://htmlpreview.github.io/?https://gist.githubusercontent.com/...`
- **Gist:** `https://gist.github.com/...`

Quote both URLs back to the user as clickable links.

**If gh is not authenticated**, gist_upload.py exits non-zero with the `gh auth login` prompt. Surface that message to the user, skip 5b, and continue with Step 6 — the vault HTML is the canonical artifact. The publish step is a hand-off, not a gate.

**If the browser should not open automatically**, append `--no-open`. The gist still publishes; only the auto-open is suppressed.

### 5b. Inject the gist URL back into the session log

After 5a succeeds, edit the vault HTML to embed the Preview URL inside the Notes section so future readers of the local file can jump to the published gist. Use the Edit tool with the absolute path from Step 1.

Target: the closing `</ul>` of the last `<h2>...Notes</h2>` block. Insert this line directly before it:

```html
  <li><strong>Published as:</strong> <a href="<preview URL from 5a>">gist preview</a></li>
```

If the file has no Notes section, append a fresh one before `</body>`:

```html
<h2>⚠️ Notes</h2>
<ul>
  <li><strong>Published as:</strong> <a href="<preview URL from 5a>">gist preview</a></li>
</ul>
```

The vault HTML now contains the gist URL inline. Subsequent re-publishes will overwrite the entry only if step 5b is rerun with the new URL — the safe path is to leave the first entry as-is unless the user explicitly asks for a re-publish.

---

## Step 6: Finalize

Copy a `/rename` command to the user's clipboard via Bash: `echo -n "/rename [Project] - [Primary Outcome]" | clip.exe`. Then tell the user:

> "Copied `/rename [Project] - [Primary Outcome]` to your clipboard. Paste it to rename this session."

The primary outcome comes from the session title determined in Step 1.

---

## Best Practices

- Each section in the session report is an outcome, not a process step ("Sources Fixed" not "We debugged source loading")
- Body should be self-contained -- no context needed beyond the note itself
- If the session was exploratory with no concrete outcome, use 🔧 or 📋 sections to describe what was investigated and what's next
- Keep it scannable: a reader should grasp the session in 15 seconds from headers alone
- Tables are powerful -- use them whenever you have structured data (queued work, test results, file inventories)
- Skip inline styling. Doc-gist's template provides the visual rhythm; semantic HTML (h1/h2/p/ul/table) carries the structure.

## Run-and-report checklist

Copy and check off:

- [ ] Backend detected and announced
- [ ] Session number resolved from `[N]. *.html` files
- [ ] HTML written to vault path (Write tool, fresh path)
- [ ] Vault context line appended to Notes section (Edit tool)
- [ ] Decision extraction surfaced any unrecorded items
- [ ] Session tidy reported anomalies or stayed silent
- [ ] doc-gist publish script invoked with `--input` and `--description`
- [ ] Preview URL and Gist URL quoted to the user
- [ ] Preview URL injected back into the vault HTML's Notes section
- [ ] /rename command copied to clipboard via `clip.exe`

## Folder map

- `SKILL.md` — this hub. Single-file skill; no companions.
