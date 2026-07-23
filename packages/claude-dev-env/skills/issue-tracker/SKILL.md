---
name: issue-tracker
description: >-
  File, update, and close GitHub work as one epic with native sub-issues.
  Dedup open and closed issues first. Edit status only inside marker sections.
  Refresh the epic checklist so it matches its children. Triggers: issue tracker,
  file an issue, track this issue, open an epic, update the epic, close the issue,
  refresh the epic checklist, attach a sub-issue.
argument-hint: "[issue action — file | update | close | refresh-epic | full handoff]"
---

# Issue tracker

**User wants an issue action done. Here is how those actions work.**

**dedup → do the work → markers only → numbers + URLs**

Run every step the ask needs in one go (file, label, attach, refresh, and so on). The `issue-tracker` agent is the primary handler for a single spawnable op; this skill is the session path when the agent is unavailable or the ask spans several steps.

## Voice

Use the `plain-brief` output style (`output-styles/plain-brief.md`). End with the issue number(s) and URL(s) the caller must keep.

## Gotchas

Append a bullet when an action fails in a new way.

- Use REST `.id`, not display `#N`, to attach a sub-issue — [operation-matrix](reference/operation-matrix.md).
- `gh` attach: `-F sub_issue_id=<n>` (typed int), never `-f`.
- Status goes in markers, not comments — comments are cross-links only.
- Dedup open **and** closed; closed twin → reopen vs file new, never silent refile.
- Edit only between markers — free-form epic edits break the children checklist.
- Put `Closes #N` on the first commit and PR; the commit-reminder hook is a backstop only.

## The model

One **epic** issue owns a work-stream. Each unit of work is a native GitHub **sub-issue** under it. The epic checklist and every status block live inside marker pairs. Skeletons and refresh steps: [reference/epic-and-sub-issue-model.md](reference/epic-and-sub-issue-model.md).

## Labels

- Parent: `epic`.
- Sub-issue: `type: roadblock`, `type: task`, `type: bug`, or `type: enhancement`.

Create a missing label, then apply it. Label create is in the operation matrix.

## Markers

- Status (any issue): `<!-- issue-tracker:status -->` … `<!-- /issue-tracker:status -->`
- Children checklist (epic only): `<!-- issue-tracker:children -->` … `<!-- /issue-tracker:children -->`

Update path: read body → replace only the text between the target pair → write the full body back.

## Dedup

Search open and closed issues on the target repo before create. Open twin → update in place. Closed twin → ask reopen vs file new.

## Tools

Prefer GitHub MCP. Fall back to `gh` on the same REST endpoints. Full map and `.id` rule: [reference/operation-matrix.md](reference/operation-matrix.md).

## Handoff input

Optional issue-candidate JSON from orchestrator or closeout. Full schema and consume path: [reference/handoff-schema.md](reference/handoff-schema.md).

## Return shape

When a fix is in flight, include `Closes #N` on that sub-issue's first commit and PR. Reply with every affected issue number and URL — no narration after that payload.

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | Hub: how issue actions work, gotchas, model, markers, dedup, return shape |
| `reference/operation-matrix.md` | MCP + `gh` per action; sub-issue `.id` rule |
| `reference/epic-and-sub-issue-model.md` | Epic model, markers, body skeleton, checklist refresh |
| `reference/handoff-schema.md` | Issue-candidate JSON and consume flow |
