---
name: closeout
description: >-
  Harvests session obstacles into GitHub issues backed by quoted evidence at
  session end, validates each draft with the user, dedupes against open and
  closed issues, routes each to its repo, files children then a parent
  checklist, and prints a computed cloud handoff prompt. Triggers: /closeout,
  close out this session, close out the session, file the session obstacles,
  session closeout, harvest session obstacles, end-of-session issue filing.
  Near-miss: not session-log, which journals the session to the vault; closeout
  files GitHub issues and prints a handoff prompt, and writes no session
  journal.
---

# Closeout

**Core principle:** At the end of a working session, turn the obstacles the session hit into user-approved GitHub issues — each backed by a quoted line — plus a computed cloud handoff prompt, never guessing, never filing without approval, never touching the host repo's live pipeline.

## Gotchas

Highest-signal content. Append a bullet each time a run fails in a new way.

- An obstacle stated from memory drifts. File only what the session can quote word for word — the actual error text, the exact command, the exact log line. A candidate that cannot be quoted goes under "Unverified candidates" for the user to judge, never into a filed issue as fact.
- Skipping the confirmation gate files noise to a shared server that other people read. Every parent and child draft passes the AskUserQuestion gate before any write.
- A body that leans on chat context reads as a puzzle to anyone who opens the issue cold. Write each body so a reader with zero session context acts on it: name the failure, the count, and the quoted line.
- A `--body` string mangles backticks on GitHub — they land as literal `\``. Every `gh` create and comment uses `--body-file <path>`.
- A dedupe search that skips closed issues re-files a twin the team already resolved. The search covers `--state all`.
- A volatile path in an issue body breaks the moment the job scratch is cleaned. Keep temp dirs, worktrees, and `$CLAUDE_JOB_DIR` out of every body.

## When this skill applies

Run this skill **at the end** of a working session, from inside that same session, when the session hit obstacles worth filing — hook blocks, gates that fired wrongly, tools that failed, forced workarounds, dead ends.

Triggers: `/closeout`, "close out this session", "file the session obstacles", "session closeout", "harvest session obstacles", "end-of-session issue filing".

**Refusal cases — first match wins:**

- **Mid-session, work still open.** Respond: `Closeout runs at session end. Keep working, and run /closeout once the session's work is done.`
- **Asked to journal the session.** Respond: `Closeout files GitHub issues; it does not write a session journal. For a session report to the vault, use /session-log.`
- **No obstacles this session.** Respond: `No obstacles to file — the session hit no hook blocks, tool failures, or dead ends worth an issue. Nothing to close out.`

## The process

Copy this checklist into your response and mark each phase as you finish it:

```
- [ ] Phase 1 — Harvest obstacles from the three sources; quote verbatim evidence
- [ ] Phase 1 — Run the PII pass over every candidate
- [ ] Phase 2 — Draft the parent + children set
- [ ] Phase 2 — Confirmation gate: AskUserQuestion, file only on approval
- [ ] Phase 3 — Dedupe each candidate against open and closed issues
- [ ] Phase 4 — Route each issue to its repo
- [ ] Phase 5 — File children, then the parent checklist
- [ ] Phase 6 — Print the computed cloud handoff prompt in chat
```

### Phase 1 — Harvest obstacles

Read three sources, in order:

1. **This session's conversation** — the chat log visible in context.
2. **The session task list** — TaskCreate/TaskUpdate records read through TaskList and TaskGet.
3. **Tool results still in the context window** — hook denials, command output, log tails.

An obstacle is a hook block, a gate that fired wrongly, a tool that failed, a forced workaround, or a dead end.

**Non-negotiable evidence rule:** every filed issue quotes verbatim evidence captured this session — the actual error text, the exact command, the exact log line. An obstacle you cannot quote is dropped, or listed under a "Unverified candidates" section of the drafts for the user to decide. It is never filed as fact.

**PII pass (runs on every run):** strip personal data from every issue body and from the handoff prompt — emails, real names, home paths, private hosts and IPs, account ids, tokens. The pass runs whether the target repo is public or private; repository visibility changes only how aggressive the redaction is (public repos get the strictest pass), never whether the pass runs. Checklist and swaps: [reference/pii-redaction-checklist.md](reference/pii-redaction-checklist.md).

### Phase 2 — Draft and validate with the user

Build the parent → children issue set as drafts. Body shapes and worked examples: [reference/issue-body-templates.md](reference/issue-body-templates.md).

Then the **mandatory confirmation gate**. Present through AskUserQuestion:

- Each drafted parent and child — title, target repo, one line of scope each.
- Any PII concern the pass found.
- Any closed twin a dedupe search surfaced (see Phase 3), as a reopen/comment/file-new choice.

Filing to GitHub is an irreversible write to a shared server that other people read. File only on explicit user approval. The user validates every finding before anything is posted.

### Phase 3 — Dedupe

Before filing each candidate, search open and closed issues on the target repo:

```
gh issue list --search "<terms>" --state all
```

- **Open twin exists** → comment on it, rather than filing a new issue.
- **Closed twin exists** → do not silently file or comment. Surface it in the Phase 2 gate as "previously closed twin — reopen, comment, or file new" for the user to decide.

`gh issue list` needs no pagination flags. If you show a `gh api` read of a paginated list endpoint anywhere, show `--paginate --slurp` piped to external `jq` — `gh`'s built-in `--jq` runs per page and gives wrong cross-page results.

### Phase 4 — Repo routing

Route each issue by a deterministic rule:

- The evidence names a file under the dev-env tree — `packages/claude-dev-env/hooks/`, `rules/`, `skills/`, `commands/`, `agents/`, `bin/`, or `docs/` — or an installed copy of those under `~/.claude/` (hooks, rules, skills, commands, agents) → file against **claude-dev-env**.
- Otherwise → the **working repo**, read live:

```
gh repo view --json nameWithOwner
```

- **Cross-repo case** — a hook shipped by repo B blocked work in repo A → file against **B** and reference A in the body.

### Phase 5 — File

File **children first**, then the parent. The parent body is a checklist of `- [ ] owner/repo#N` lines, one per child created.

- Every `gh issue create` and `gh issue comment` uses `--body-file <path>`, never `--body`.
- No volatile paths in any body: no temp dirs, no worktrees, no `$CLAUDE_JOB_DIR`, no `.claude-editor/jobs` or `.claude/worktrees` paths.
- Bodies are self-contained and specific: the failure mode, the count, and the quoted line — not "improve error handling".

### Phase 6 — Computed handoff prompt

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
- It creates issues and comments and prints text. Nothing else.

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | This hub — core principle, gotchas, refusal cases, six-phase process, boundaries |
| `reference/issue-body-templates.md` | Parent and child issue body shapes with worked examples |
| `reference/pii-redaction-checklist.md` | The PII pass: categories, swaps, public-versus-private aggression |
| `reference/handoff-prompt-template.md` | The computed cloud handoff prompt shape with a worked example |

## Folder map

- `SKILL.md` — hub: principle, gotchas, refusal, six-phase process, boundaries.
- `reference/` — issue body templates, PII redaction checklist, handoff prompt template.
