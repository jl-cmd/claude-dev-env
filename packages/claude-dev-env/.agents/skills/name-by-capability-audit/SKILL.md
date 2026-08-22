---
name: name-by-capability-audit
description: >-
  Use when auditing a GitHub PR for name-by-capability violations —
  driver/motive words on reusable modules; triggers: name-by-capability audit,
  capability naming review, cert_fix rename check.
---
# Name-by-Capability Audit

Audit a GitHub PR against the **name-by-capability** rule. Inspect paths and title wording for driver/motive words on reusable capability code, then report findings with a rename direction. Apply renames when the user requests a fix.

## Gotchas

- Name reusable libraries for the action they perform; a first cert caller still leaves the library capability-named. Score reuse potential alongside the PR title.
- Correctly driver-named surfaces (`cert_fix_queue`, report routing/locate, unfixable patterns) are **OK** findings — list them under OK drivers.
- Renames and new paths carry the most signal; when a PR expands an already-misnamed package, note the package name too.

## When this applies

- User invokes `/name-by-capability-audit <PR>` or asks to audit a PR for name-by-capability / capability naming.
- PR adds or renames packages/modules, or frames a general shared operation with a driver/motive word (`cert_fix`, `cert_closeout`, `portal`, `export`, …).

**First match wins:**

- Missing PR number or URL → respond exactly: `Give a GitHub PR number or URL to audit for name-by-capability.`
- User requests a rename or fix → finish the audit report, then apply the rename direction they asked for.

## Constraints

- Report findings plus a suggested rename direction for each violation.
- Suggest renames for paths the PR touched; for an expanded offense, also name the package the PR grew.
- Distinguish **violation** vs **OK driver** using `reference/offense-examples.md`.

## Process

Register every bullet from `reference/task-seeds.md` on the host task tool (`TodoWrite` / `TaskCreate`). Mark each complete with evidence. Follow those seeds in order — do not restate them here.

Load order for the rule: read the optional repo doc named name-by-capability.md under docs/agents when that file is in the worktree; always keep `reference/rule-checklist.md` as the fallback. On disagreement, follow the repo doc and update the skill checklist in a follow-up.

## Composition

| Peer | Relationship |
|------|----------------|
| `shared-extraction-audit` | Layering and extraction (where code lives). Invoke when a path’s *role* is unclear; this skill only scores the *name*. |
| `reviews` / PR review skills | May invoke this skill by name when naming is in scope |

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | Hub — gotchas, when-applies, process, composition |
| `reference/rule-checklist.md` | Embedded rule + naming checklist (fallback when docs are missing) |
| `reference/offense-examples.md` | Classifier + known OK drivers vs offenders |
| `reference/fetch-commands.md` | Minimal `gh` fetch for PR naming surface |
| `reference/report-template.md` | Compact report shape |
| `reference/task-seeds.md` | Ordered task seeds for the audit run |
