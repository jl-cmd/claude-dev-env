---
name: closeout
description: >-
  Harvests session obstacles into GitHub issues backed by quoted evidence:
  validates each draft with the user, then delegates filing to the issue-tracker
  agent (skill fallback), which dedupes against open and closed issues and files
  each under an epic as a native sub-issue. Prints a cloud handoff prompt.
  Triggers: /closeout, close out this session, close out the session, file the
  session obstacles, session closeout, harvest session obstacles, end-of-session
  issue filing. Not session-log (vault journal) — closeout files issues and
  writes no journal.
---

# Closeout

**Core principle:** At the end of a working session, turn the obstacles the session hit into user-approved GitHub issues — each backed by a quoted line — then hand each approved draft to the issue-tracker for filing, and print a computed cloud handoff prompt. Closeout never guesses, never files without approval, and never touches the host repo's live pipeline.

## The delegation boundary

Closeout is the session-end entry point. It harvests obstacles, validates them with the user, and drafts one issue-candidate record per obstacle. The **issue-tracker** owns filing: dedup against open and closed issues, one epic per work-stream, native sub-issues, labels, and marker-delimited body sections. Closeout hands each approved record to the `issue-tracker` **agent** (primary), falling back to the `issue-tracker` **skill** when the agent is unavailable. Closeout-filed issues run the full tracker path — the same as any other tracked issue. Closeout builds no separate filing layer.

## Gotchas

Highest-signal content. Append a bullet each time a run fails in a new way.

- An obstacle stated from memory drifts. File only what the session can quote word for word — the actual error text, the exact command, the exact log line. A candidate that cannot be quoted goes under "Unverified candidates" for the user to judge, never into a filed issue as fact.
- Skipping the confirmation gate files noise to a shared server that other people read. Every draft passes the AskUserQuestion gate before closeout hands it to the tracker.
- A body that leans on chat context reads as a puzzle to anyone who opens the issue cold. Write each record so a reader with zero session context acts on it: name the failure, the count, and the quoted line.
- A volatile path in an issue body breaks the moment the job scratch is cleaned. Keep temp dirs, worktrees, and `$CLAUDE_JOB_DIR` out of every record.

## When this skill applies

Run this skill **at the end** of a working session, from inside that same session, when the session hit obstacles worth filing — hook blocks, gates that fired wrongly, tools that failed, forced workarounds, dead ends.

Triggers: `/closeout`, "close out this session", "file the session obstacles", "session closeout", "harvest session obstacles", "end-of-session issue filing".

**Refusal cases — first match wins:**

- **Mid-session, work still open.** Respond: `Closeout runs at session end. Keep working, and run /closeout once the session's work is done.`
- **Asked to journal the session.** Respond: `Closeout files GitHub issues; it does not write a session journal. For a session report to the vault, use /session-log.`
- **No obstacles this session.** Respond: `No obstacles to file — the session hit no hook blocks, tool failures, or dead ends worth an issue. Nothing to close out.`

## The process

```
- [ ] Phase 1 — Harvest obstacles from the three sources; quote verbatim evidence; run the PII pass
- [ ] Phase 2 — Draft one issue-candidate record per obstacle; confirmation gate via AskUserQuestion
- [ ] Phase 3 — Route each candidate to its repo
- [ ] Phase 4 — Hand each approved record to the issue-tracker; collect numbers and URLs
- [ ] Phase 5 — Print the computed cloud handoff prompt in chat
```

### Track the phases on the task list

At invocation, copy the five phases onto the session task list — one task each via TaskCreate: harvest, draft plus user validation, repo routing, tracker hand-off, handoff prompt. Mark a task `in_progress` with TaskUpdate when its phase starts and `completed` when the phase finishes.

Hold one line on the hand-off task: never mark it `completed` while any approved record has no issue number back from the tracker. A hand-off that lands fewer issues than the approved set keeps the task open, with the missing records named on it.

### Phase 1 — Harvest obstacles

Read three sources, in order:

1. **This session's conversation** — the chat log visible in context.
2. **The session task list** — TaskCreate/TaskUpdate records read through TaskList and TaskGet.
3. **Tool results still in the context window** — hook denials, command output, log tails.

An obstacle is a hook block, a gate that fired wrongly, a tool that failed, a forced workaround, or a dead end.

**Non-negotiable evidence rule:** every filed issue quotes verbatim evidence captured this session — the actual error text, the exact command, the exact log line. An obstacle you cannot quote is dropped, or listed under a "Unverified candidates" section of the drafts for the user to decide. It is never filed as fact.

**PII pass (runs on every run):** strip personal data from every record and from the handoff prompt — emails, real names, home paths, private hosts and IPs, account ids, tokens. The pass runs whether the target repo is public or private; repository visibility changes only how aggressive the redaction is (public repos get the strictest pass), never whether the pass runs. Checklist and swaps: [reference/pii-redaction-checklist.md](reference/pii-redaction-checklist.md).

### Phase 2 — Draft and validate with the user

Build one **issue-candidate record** per obstacle, in the tracker's handoff shape: `kind`, `title`, `epic`, `summary`, `evidence`, `where`, `impact`, `proposed_fix`, `blocking`. Field meanings and a filled example: the issue-tracker skill's handoff schema (`skills/issue-tracker/reference/handoff-schema.md`). Group related obstacles under one `epic` label so the tracker files them as sub-issues of a shared epic.

Then the **mandatory confirmation gate**. Present through AskUserQuestion:

- Each drafted record — title, target repo, `epic`, one line of scope.
- Any PII concern the pass found.

Filing to GitHub is an irreversible write to a shared server that other people read. Hand a record to the tracker only on explicit user approval. The user validates every finding before anything is posted.

### Phase 3 — Repo routing

Route each candidate by a deterministic rule, and pass the resolved repo to the tracker:

- The evidence names a file under the dev-env tree — `packages/claude-dev-env/hooks/`, `rules/`, `skills/`, `commands/`, `agents/`, `bin/`, or `docs/` — or an installed copy of those under `~/.claude/` (hooks, rules, skills, commands, agents) → file against **claude-dev-env**.
- Otherwise → the **working repo**, read live:

```
gh repo view --json nameWithOwner
```

- **Cross-repo case** — a hook shipped by repo B blocked work in repo A → file against **B** and name A in the record.

### Phase 4 — Hand off to the issue-tracker

For each approved record, hand it to the `issue-tracker` **agent** (primary) with the resolved repo, one record per agent call. When the agent is unavailable, load the `issue-tracker` **skill** and run the same op inline. The tracker runs the full path for each record: dedup open and closed issues, find or create the epic, create the sub-issue, apply labels, attach the native sub-issue, and refresh the epic checklist. It returns the issue number and URL, which closeout collects for the handoff prompt.

A closed twin the tracker's dedup surfaces comes back for a reopen-or-file-new decision. Route that decision through the same AskUserQuestion gate before the tracker proceeds.

### Phase 5 — Computed handoff prompt

Print **in chat** (not a file) a prompt the user pastes into a cloud session that opens PRs for the filed issues and drives them to convergence. Template and worked example: [reference/handoff-prompt-template.md](reference/handoff-prompt-template.md).

The prompt is computed, not a bare list. It carries:

1. **Safety boundaries** — what must never be run, merged, deployed, or synced. The working repo's pipeline is live in production.
2. **Base branch and verification commands** — read the base branch and the per-package verification commands from the target repo's CLAUDE.md and docs at runtime.
3. **Dependency order** — which issue must land before which, and which issues touch the same files and so must stack on one branch rather than run in parallel.

If any issue cannot be done from a cloud session — it needs a local environment, physical devices, or a private network — the prompt says so per issue and scopes the cloud work to what a cloud session can reach.

## Skill boundaries

This skill runs inside a repo whose pipeline is live in production. Hold these lines:

- It never runs that pipeline, never merges, never deploys, never syncs.
- It never runs the host repo's automations.
- It harvests obstacles, validates them, delegates filing to the tracker, and prints text. Nothing else.

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | This hub — core principle, delegation boundary, gotchas, refusal cases, five-phase process, boundaries |
| `reference/pii-redaction-checklist.md` | The PII pass: categories, swaps, public-versus-private aggression |
| `reference/handoff-prompt-template.md` | The computed cloud handoff prompt shape with a worked example |

## Folder map

- `SKILL.md` — hub: principle, delegation boundary, gotchas, refusal, five-phase process, boundaries.
- `reference/` — PII redaction checklist, handoff prompt template.
