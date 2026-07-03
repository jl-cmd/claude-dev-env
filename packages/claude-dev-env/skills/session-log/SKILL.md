---
name: session-log
description: >-
  Log a session report by composing a self-contained HTML page and publishing it with the Artifact tool, then track vault context, extract unrecorded decisions, tidy the project's session folder, and output a /rename command. Use when the user says /session-log, journal this session, log this work, session report, or any variation of "summarize/log/record this session". Also triggers on "save session", "capture session", or "document what we did".
---

# Session Log

## Overview

Session-log composes the HTML report and publishes it directly with the `Artifact` tool. The skill owns the whole flow: where the file lives in the vault, what number it gets, the frontmatter metadata contract, HTML composition and publishing, post-write vault tracking, decision extraction, project-folder hygiene, and the closing `/rename` hand-off.

**Announce at start:** "I'm logging this session."

## Why this report is designed fresh per session

Sessions come in many shapes — convergence loops, feature builds, research dives, incidents, refactors, decisions. A single h2-emoji-list template forces every session into the same form regardless of fit, and the artifact reads as a process log rather than a substance log. Load the `artifact-design` skill before composing any page content — it calibrates the design investment and shape to the session's character: a feature build reads naturally as a PR writeup, an incident or convergence loop as a timeline, a status update as a progress summary, a plan or decision as a decision record, an exploration as a multi-approach walkthrough.

## Gotchas

- **Load the `artifact-design` skill before writing page content.** The `Artifact` tool needs this step first — it is not optional polish.
- **The `Artifact` tool wraps the file in a document skeleton at publish time.** It adds `<!doctype html>…<head>…</head><body>` around whatever the file holds — write page content only (a `<title>`, a `<style>` block, and the body markup). Do not include `<!DOCTYPE>`, `<html>`, `<head>`, or `<body>` tags in the file itself.
- **The `Artifact` tool redeploys to the same URL only within the current run.** Editing the session's HTML file in a later step of this same skill run and calling `Artifact` again does not mint a new URL — it updates the same published page in place. A fresh session has no memory of an artifact's URL from an earlier run, so republishing a session report written in a prior session always mints a new URL (there is no other way to target the old one without the user supplying it).
- **Vault paths sit outside `.claude/`.** Headless vault paths (e.g., `$OBSIDIAN_VAULT_PATH`) resolve outside the project tree. Session reports use HTML regardless of vault location — the Artifact tool needs a written file to publish.
- **Sessions describe current state by convention.** The state_description_blocker hook does not scan .html, but the rule at `~/.claude/rules/no-historical-clutter.md` applies as a writing standard — skip historical and comparative language when composing the report; the rule file lists the full trigger set.
- **`write_existing_file_blocker` rejects Write on existing paths.** Use Write only when creating a fresh session report; use Edit for the vault-context append in step 3.
- **Obsidian frontmatter index is HTML-blind.** Obsidian's native YAML-frontmatter parser reads only `.md` files. HTML files do not appear in Obsidian's frontmatter index. Search by content still works; search by `type: session-report` does not.

## Backend Detection (run before Step 1)

Determine which storage backend is available. First success wins.

1. **Headless vault** — Bash `ob --version` to verify the obsidian-headless CLI is installed. Check `OBSIDIAN_VAULT_PATH` env var or `~/.claude/vault/` for a vault directory. When the CLI check succeeds AND at least one of those paths resolves to a vault directory, set `backend = "headless"`.
2. **Local vault** — fall back to `~/.claude/vault/`. Create `~/.claude/vault/sessions` via `mkdir -p` if missing. Set `backend = "local"`.

**Session-number detection:** Bash `ls` the project's session folder, parse filenames matching `[N]. *.html` or `[N]. *.md` to preserve sequence across the format migration. Highest N + 1. New project → start at 1.

**Output paths:**
- headless: `$OBSIDIAN_VAULT_PATH/sessions/[Project]/[N]. [Title].html` (falls back to `~/.claude/vault/` when the env var is unset)
- local: `~/.claude/vault/sessions/[Project]/[N]. [Title].html`

Announce the backend: "Using headless vault at [path]." or "Using local vault at ~/.claude/vault/. Install obsidian-headless and set the `OBSIDIAN_VAULT_PATH` environment variable (PowerShell: `$env:OBSIDIAN_VAULT_PATH = '<path>'`; POSIX shells: `export OBSIDIAN_VAULT_PATH=<path>`) to enable sync."

---

## Step 1: Compose Session Metadata

Review the conversation to identify the session's primary outcome and the small set of facts a cold reader needs.

Resolve the metadata used by the frontmatter and the vault path:

- **Project name:** infer from conversation context
- **Session number:** from backend detection above
- **Session ID:** the session ID of the agent authoring this log, read from the `CLAUDE_CODE_SESSION_ID` environment variable (PowerShell: `$env:CLAUDE_CODE_SESSION_ID`). This UUID names the authoring agent's own transcript file (`<session-id>.jsonl`), so the saved report points back to the exact session that produced it. When the variable is unset, use the literal `unknown`.
- **Date:** today's date
- **Title:** a 2–5 word summary of the session's primary outcome. Examples: "Amazon Auth Migration", "Source Loading Fix", "PR 475 Convergence". Avoid generic titles like "Bug Fixes".

The frontmatter contract every session report carries (inside an HTML comment, as the first child of `<body>`):

```html
<!--
type: session-report
project: [name]
session: [N]
session_id: [uuid]
date: [YYYY-MM-DD]
status: completed|in-progress|blocked
blocked: true|false
vault_context_retrieved: true|false
tags: [session, [project-tag], [topic-tags]]
-->
```

Every session report carries this metadata block verbatim so vault search and the tidy step in step 5 work. **Initial values for Step 2's Write:** substitute concrete values for every placeholder — for `session_id`, write the value read from `CLAUDE_CODE_SESSION_ID` in step 1 (or `unknown` when the variable is unset); for `vault_context_retrieved`, write the literal value `false` (the safe default before Step 3's vault-MCP-tool scan completes). Step 3 then Edits `vault_context_retrieved` to `true` if any of the three vault MCP tools fired this session.

## Step 2: Compose and Publish the HTML via the Artifact Tool

Load the `artifact-design` skill before writing any content. Design the artifact for **this session's character** — a feature build reads naturally as a PR writeup, an incident or convergence loop as a timeline, a status update as a progress summary, a plan or decision as a decision record, an exploration as a multi-approach walkthrough. The report must answer for a cold reader, from the section headers alone, three questions: *what shipped*, *why it matters*, *what impact it had*. Process narration (commit-by-commit walks, agent gotchas, retry counts) belongs at the end, not in the opening sections.

**Required as the first content line:** the frontmatter HTML comment from step 1.

**Required somewhere in the content:** a `<title>` element naming the session — it names the browser tab and the artifact gallery entry.

**Required as the first content section (after the frontmatter comment):** an opening "What this session shipped" paragraph + bullets — written so a reader with zero prior context understands the outcome. For continuation sessions (where the substantive work landed in a prior session), recap the parent session's outcome briefly so the report stands alone.

**Required: self-contained, responsive, theme-aware HTML.** Inline all CSS in a `<style>` block and all JS inline; embed any images as data URIs — the `Artifact` tool's content security policy blocks external CDN scripts, stylesheets, fonts, and network requests. Use relative units so the layout holds at any width, and support both light and dark via `prefers-color-scheme` (or `:root[data-theme]` overrides).

**No document wrapper tags.** The `Artifact` tool wraps the file content in a `<!doctype html>…<head>…</head><body>` skeleton at publish time — write the `<title>`, `<style>`, and body markup directly, with no `<!DOCTYPE>`, `<html>`, `<head>`, or `<body>` tags of your own.

Beyond those requirements, design the shape that fits the session — the `artifact-design` skill's guidance covers typography, palette, and layout choices.

**Write the file** via the Write tool to the vault path. Create the project directory via `mkdir -p` if it does not exist.

**Publish the file** by calling the `Artifact` tool with `file_path` set to the vault path just written, `favicon` set to the fixed session-log favicon `📓` — this favicon stays the same across every session-log report so the series reads as one consistent collection; never swap it per session — and `description` set to a one-sentence subtitle summarizing the session. Capture the returned URL: it is the canonical URL for this session report, and it stays the same across every later `Artifact` call on this same `file_path` within the current run (steps 3 and 5 redeploy to it rather than minting a new one).

**If the Write fails**, output the HTML content in the conversation so the user can copy it manually. Before emitting the HTML to chat, resolve the `vault_context_retrieved` placeholder to `true` or `false` based on the same vault-MCP-tool scan that Step 3 would have run, and include the matching vault-context `<li>` line (Retrieved or Not retrieved) so the emitted HTML is a valid copy-paste artifact with complete frontmatter. Skip Step 3 and continue at step 4.

## Step 3: Vault Context Tracking

This step runs automatically after step 2.

Review the conversation history for any use of these vault MCP tools (look only at tool calls the session made before /session-log itself ran):

- `mcp__obsidian__search_notes`
- `mcp__obsidian__read_note`
- `mcp__obsidian__read_multiple_notes`

Edit the vault HTML via two Edit calls:

1. Set the frontmatter `vault_context_retrieved` field to `true` when any of the three tools fired this session, `false` otherwise.
2. Append one fact — vault-context status — into whatever section the report designer placed for notes / metadata / references. If the report has no such section, append a fresh `<h2>Notes</h2>` block at the end of the content:

```html
<h2>Notes</h2>
<ul>
  <!-- Pick exactly one of the two forms based on whether vault MCP tools fired this session: -->
  <li><strong>Vault context:</strong> Retrieved ([list of note paths])</li>
  <li><strong>Vault context:</strong> Not retrieved</li>
</ul>
```

If the report already has a notes / references section, use Edit to insert one matching child element at the end of that section. The element shape mirrors whatever the section already uses: an extra `<li>` before the closing `</ul>` for a list, an extra `<dt>Vault context</dt><dd>…</dd>` pair before the closing `</dl>` for a description list, an extra `<p><strong>Vault context:</strong> …</p>` before the section's closing tag for a paragraph-based section. Pick the form that matches the surrounding markup.

After both Edits land, call the `Artifact` tool again with the same `file_path` and the same `favicon` used in step 2 to redeploy the updated content. This updates the URL captured in step 2 in place; no new URL is minted.

## Step 4: Decision Extraction

Scan the conversation for decisions, gotchas, or architectural choices that were not already saved via `/remember`. For each one found, ask the user via `AskUserQuestion`:

> "I noticed this decision: [summary]. Save it to the vault via `/remember`?"

Only invoke `/remember` for decisions the user confirms; `/remember` writes the decision as a vault note. If no unrecorded decisions are found, skip silently.

## Step 5: Session Tidy (Project Scope)

Scope: the current project's session folder only.

1. **List files** in the project's vault session folder via Bash `ls`.
2. **Quick audit** each `.html` file for:
   - **Naming convention:** must match `[N]. [Title].html`
   - **Frontmatter completeness:** HTML comment block at top of `<body>` contains `type`, `project`, `session`, `date`, `status`, `blocked`, `vault_context_retrieved`, `tags`
   - **Status coherence:** `status: completed` with `blocked: true` is contradictory. `status: in-progress` or `status: blocked` on sessions older than 7 days is stale.
3. **Auto-fix minor issues** via Edit:
   - Missing frontmatter fields that can be inferred (e.g., `blocked: false` when status is `completed`; `vault_context_retrieved: false` when the field is absent, since the field defaults to false in pre-existing sessions)
   - `type` field set to a wrong value (correct to `session-report`)

   When the Edit touches the session report created in this run, call `Artifact` again with the same `file_path` and `favicon` from step 2 to redeploy — the URL captured in step 2 stays unchanged. When the Edit touches an older session report published in a prior run, call `Artifact` on that `file_path` with no `url` argument, since this skill keeps no record of that file's earlier URL — this publishes the older report at a new URL. Surface a `Session [N] republished at a new URL: <url>` line so the user can update any prior shares.
4. **Report issues that need user input:**
   - Files with wrong naming convention (propose new name)
   - Stale statuses (propose update to `completed` or ask)
   - Contradictory status/blocked combos

   If no issues are found, skip silently. Do not report "all clean."
5. **Rollup check:** if the project has 5+ sessions and no `Summary.html` or `Summary.md`, mention it:
   > "This project has [N] sessions and no summary. A rollup would help; `/session-tidy` is defined for the Markdown session format and may mis-audit or propose destructive renames against HTML sessions, so a manual rollup is the safe path."

## Step 6: Finalize

Copy a `/rename` command to the user's clipboard via PowerShell:

```
pwsh -NoProfile -Command "Set-Clipboard '/rename [Project] - [Primary Outcome]'"
```

Then tell the user:

> "Copied `/rename [Project] - [Primary Outcome]` to your clipboard. Paste it to rename this session."

The primary outcome comes from the session title resolved in step 1.

---

## Run-and-report checklist

- [ ] Backend detected and announced
- [ ] Session number resolved from `[N]. *.html` and `[N]. *.md` files (both parsed to preserve sequence across the format migration)
- [ ] `artifact-design` skill loaded before composing page content
- [ ] HTML composed for this session's character (no document wrapper tags; self-contained, responsive, theme-aware)
- [ ] Frontmatter HTML comment present as the first content line
- [ ] `session_id` frontmatter field set from `CLAUDE_CODE_SESSION_ID` (the authoring agent's own session), or `unknown` when the variable is unset
- [ ] Opening section answers "what shipped / why / impact" for a cold reader
- [ ] Published via the `Artifact` tool with the fixed favicon `📓`; URL captured (or HTML emitted to chat when step 2 Write failed)
- [ ] Vault-context line appended via Edit (step 3); `Artifact` redeployed on the same URL
- [ ] Decision extraction surfaced any unrecorded items
- [ ] Session tidy reported anomalies or stayed silent
- [ ] `/rename` command copied to clipboard via `pwsh Set-Clipboard`

## Folder map

- `SKILL.md` — this hub. Single-file skill; no companions.
