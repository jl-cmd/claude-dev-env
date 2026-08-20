---
name: issue-tracker
description: >-
  File, update, and close GitHub work as one epic with native sub-issues.
  Dedup open and closed issues first. Edit status only inside marker sections.
  Refresh the epic checklist so it matches its children. Triggers: issue tracker,
  file an issue, track this issue, open an epic, update the epic, close the issue,
  refresh the epic checklist, attach a sub-issue.
argument-hint: "[issue action - file | update | close | refresh-epic | full handoff]"
---

# Issue tracker

**User wants an issue action done. Here is how those actions work.**

**dedup -> do the work -> markers only -> numbers + URLs**

Run every step the ask needs in one go (file, label, attach, refresh, and so on). The `issue-tracker` agent is the primary handler for one action per turn; this skill is the session path when the agent is unavailable or the ask spans several steps.

Prefer the **same warm** `issue-tracker` agent for follow-ups on the same issue or a related issue on the same epic. Spawn a new agent only for an unrelated work-stream or when the warm agent is gone.

## Voice

Use the `plain-brief` output style (`output-styles/plain-brief.md`). End with the issue number(s) and URL(s) the caller must keep.

## Gotchas

Append a bullet when an action fails in a new way.

- Use REST `.id`, not display `#N`, to attach a sub-issue - [operation-matrix](reference/operation-matrix.md).
- `gh` attach: `-F sub_issue_id=<n>` (typed int), never `-f`.
- Status goes in markers, not comments - comments are cross-links only.
- Dedup open **and** closed; closed twin -> reopen vs file new, never silent refile.
- Edit only between markers - free-form epic edits break the children checklist.
- Auto-close is PR-body-first: a related-only UI link does not close the issue on merge.

## The model

One **epic** issue owns a work-stream. Each unit of work is a native GitHub **sub-issue** under it. The epic checklist and every status block live inside marker pairs. Skeletons and refresh steps: [reference/epic-and-sub-issue-model.md](reference/epic-and-sub-issue-model.md).

## Labels

- Parent: `epic`.
- Sub-issue: `type: roadblock`, `type: task`, `type: bug`, or `type: enhancement`.

Create a missing label, then apply it. Label create is in the operation matrix.

## Markers

- Status (any issue): `<!-- issue-tracker:status -->` … `<!-- /issue-tracker:status -->`
- Children checklist (epic only): `<!-- issue-tracker:children -->` … `<!-- /issue-tracker:children -->`

Update path: read body -> replace only the text between the target pair -> write the full body back.

## Dedup

Search open and closed issues on the target repo before create. Open twin -> update in place. Closed twin -> ask reopen vs file new.

## Tools

Prefer GitHub MCP. Fall back to `gh` on the same REST endpoints. Full map and `.id` rule: [reference/operation-matrix.md](reference/operation-matrix.md).

## Handoff input

Optional issue-candidate JSON from orchestrator or closeout. Full schema and consume path: [reference/handoff-schema.md](reference/handoff-schema.md).

## Close the sub-issue through the PR (required when a fix ships)

GitHub closes the sub-issue when someone **merges** a pull request into the **default branch** and that PR carries a closing keyword for the issue.

**Required on the PR that merges into the default branch:** put `Closes #N` in the PR body for each finished sub-issue. One keyword per issue: write `Closes #12` and `Closes #13`, not `Closes #12, #13` (only the first number closes in the comma form).

**Preferred on commits:** also put `Closes #N` in the first commit message when the fix starts. Commit alone is backup; the PR body is the contract.

**Stacked / intermediate PRs** that do not merge into the default branch: use a plain `#N` reference in the body so the issue links without a false close promise. Put `Closes #N` only on the PR that actually lands on the default branch.

**Not enough:** a Development "related" link with no closing keyword. **Not enough:** closing the PR without merging.

**Who owns `#N`:** the agent or session writing the PR must use the correct sub-issue number. Nothing in this package verifies the number matches the fix.

## Return shape

Reply with every affected issue number and URL - no narration after that payload.

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | Hub: how issue actions work, gotchas, model, markers, dedup, PR auto-close, return shape |
| `reference/operation-matrix.md` | MCP + `gh` per action; sub-issue `.id` rule |
| `reference/epic-and-sub-issue-model.md` | Epic model, markers, body skeleton, checklist refresh |
| `reference/handoff-schema.md` | Issue-candidate JSON and consume flow |
