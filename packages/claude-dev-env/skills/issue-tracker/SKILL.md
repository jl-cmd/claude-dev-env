---
name: issue-tracker
description: >-
  One consistent way to create, update in place, and close GitHub issues for a
  work-stream: one epic parent with native sub-issues, dedup against open and
  closed issues first, marker-delimited body sections edited in place, and an
  epic checklist that mirrors the children. Triggers: issue tracker, file an
  issue, track this issue, open an epic, update the epic, close the issue,
  refresh the epic checklist, attach a sub-issue.
argument-hint: "[one issue op — file | update | close | refresh-epic]"
---

# Issue tracker

**Core principle:** Every issue op runs the same path — dedup first, one epic per work-stream, native sub-issues under it, in-place body edits through marker sections, an epic checklist that mirrors the children, and a returned issue number plus URL. One op per call.

## Gotchas

Highest-signal content. Append a bullet each time an op fails in a new way.

- The native sub-issues endpoint takes the child's REST database `.id`, a large integer — the display number (`#42`) is a different value and the attach fails silently when you pass it. Read the child's `.id` before the attach. Full matrix: [reference/operation-matrix.md](reference/operation-matrix.md).
- A gh sub-issue attach with `-f sub_issue_id=<n>` sends a string and the endpoint rejects it. Use `-F` (typed integer).
- A routine status posted as a comment scatters the state across a comment thread a reader has to scroll. Status lives in the issue body's marker section, edited in place. A comment carries only a cross-reference, such as a PR link.
- Skipping the closed-issue search re-files a twin the team already resolved. Every dedup search covers open and closed.
- An epic body edited outside its `<!-- issue-tracker:children -->` markers loses the checklist structure the refresh step depends on. Replace only the marked section.
- A finished sub-issue that carries no `Closes #N` in its commit or PR leaves the issue open after the PR merges. Put `Closes #N` in from the first commit; the commit reminder hook is the backstop, not the plan.

## When this skill applies

Run this skill for any single GitHub issue op on a work-stream: open an epic, file a sub-issue under it, update an issue's status in place, refresh the epic checklist, or close a sub-issue. The `issue-tracker` agent is the primary handler; this skill is the path a session follows when the agent is unavailable.

Triggers: "file an issue", "track this issue", "open an epic", "update the epic", "close the issue", "refresh the epic checklist", "attach a sub-issue".

## The model — one epic, native sub-issues

One parent **epic** issue holds a work-stream; each unit of work is a native GitHub **sub-issue** under it. The epic body mirrors its children as a checklist inside marker delimiters, and every issue carries a status section inside its own markers. Body skeletons, the marker pairs, and the refresh step: [reference/epic-and-sub-issue-model.md](reference/epic-and-sub-issue-model.md).

## Labels

- `epic` on every parent.
- `type: roadblock`, `type: task`, `type: bug`, or `type: enhancement` on every sub-issue.

Create a label when the repository lacks it, then apply it. The label create op is in the operation matrix.

## In-place body edits through markers

Two marker pairs delimit the editable sections:

- `<!-- issue-tracker:status -->` … `<!-- /issue-tracker:status -->` — on any issue.
- `<!-- issue-tracker:children -->` … `<!-- /issue-tracker:children -->` — on the epic only.

Update is always: read the current body, replace only the text between the target marker pair, write the whole body back with the issue-update op. Favor an in-place body edit over a comment. A comment is only for a cross-reference (a PR link, a related issue), never for routine status.

## Dedup first

Before creating any epic or sub-issue, search open and closed issues on the target repository for a twin. An open twin means update it in place rather than file a second. A closed twin is surfaced for a reopen-or-file-new decision, not silently duplicated.

## Tooling — MCP preferred, gh fallback

Each op maps to a GitHub MCP tool and a `gh` fallback that reaches the same REST endpoint, so the skill runs in a cloud session or a local one. The full mapping, with the sub-issue `.id` rule spelled out: [reference/operation-matrix.md](reference/operation-matrix.md).

## The handoff record it consumes

An orchestrator or the closeout skill hands the tracker an issue-candidate JSON record per obstacle. The tracker consumes it through the full path: dedup, find or create the epic, create the sub-issue, apply labels, attach the native sub-issue, refresh the epic checklist. The record's fields and a filled example: [reference/handoff-schema.md](reference/handoff-schema.md).

## Closes #N from the start

When a sub-issue has a fix in flight, its first commit and its PR body carry `Closes #N` (the sub-issue's number), so the merge closes the issue. The commit reminder hook only catches a miss; the plan is to write it in from the start.

## One op per call, return numbers and URLs

Each invocation runs exactly one issue op. The return is the affected issue number(s) and URL(s) and nothing else, so a caller can chain the next op.

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | This hub — core principle, gotchas, the model, labels, markers, dedup, tooling, handoff, return shape |
| `reference/operation-matrix.md` | Each op mapped to its GitHub MCP tool and its `gh` REST fallback, with the sub-issue `.id` rule |
| `reference/epic-and-sub-issue-model.md` | The epic-plus-sub-issue model, both marker pairs, a body skeleton, and the checklist refresh step |
| `reference/handoff-schema.md` | The issue-candidate JSON record, a filled example, and the consume flow |

## Folder map

- `SKILL.md` — hub: principle, gotchas, model, labels, markers, dedup, tooling, handoff, return shape.
- `reference/` — operation matrix, epic-and-sub-issue model, handoff schema.
