---
name: name-by-capability-audit
description: >-
  Audit a GitHub PR for name-by-capability violations: driver/motive words on
  reusable capability modules (queues and report routers may keep the driver
  word), then apply capability-oriented renames by default. Triggers:
  /name-by-capability-audit, name-by-capability audit, audit PR for naming, name
  by capability, capability naming review, cert_fix rename check, driver word in
  package name.
---

# Name-by-Capability Audit

Audit a GitHub PR against the **name-by-capability** rule. Inspect paths and title wording for driver/motive words on reusable capability code, report findings with a rename direction, and apply the suggested renames by default. An explicit audit-only request ends after the report.

## Gotchas

- Name reusable libraries for the action they perform; a first cert caller still leaves the library capability-named. Score reuse potential alongside the PR title.
- Correctly driver-named surfaces (`cert_fix_queue`, report routing/locate, unfixable patterns) are **OK** findings — list them under OK drivers.
- Renames and new paths carry the most signal; when a PR expands an already-misnamed package, note the package name too.

## When this applies

- User invokes `/name-by-capability-audit <PR>` or asks to audit a PR for name-by-capability / capability naming.
- PR adds or renames packages/modules, or frames a general shared operation with a driver/motive word (`cert_fix`, `cert_closeout`, `portal`, `export`, …).

**First match wins:**

- Missing PR number or URL → respond exactly: `Give a GitHub PR number or URL to audit for name-by-capability.`
- User requests audit-only → finish the audit report and stop.
- User gives a rename or fix direction → finish the audit report, then apply the direction they gave.
- A violation with no user-supplied direction → finish the audit report, then apply the suggested rename direction by default.

## Constraints

- Report findings plus a suggested rename direction for each violation.
- Suggest renames for paths the PR touched; for an expanded offense, also name the package the PR grew.
- Distinguish **violation** vs **OK driver** using `reference/offense-examples.md`.

## Process

Register every bullet from `reference/task-seeds.md` on the host task tool (`TodoWrite` / `TaskCreate`). Mark each complete with evidence. Follow those seeds in order — do not restate them here.

Load order for the rule: if `docs/agents/name-by-capability.md` exists, read it first; always keep `reference/rule-checklist.md` as the fallback when the doc is missing. On disagreement after the docs PR merges, prefer the repo doc and update the skill checklist in a follow-up.

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

## Folder map

- `SKILL.md` — hub
- `reference/` — rule, examples, fetch recipe, report template, task seeds
