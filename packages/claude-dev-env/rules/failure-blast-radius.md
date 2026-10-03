---
paths:
  - "**/*.py"
  - "**/*.mjs"
  - "**/*.js"
  - "**/*.ts"
  - "**/*.ps1"
---

# Failure Blast Radius

**When this applies:** Batch code that processes assets, rows, accounts, messages, or files where one member can fail while the others are fine.

Every raise reached through per-member work names what stops. A type ending in `RunFatal` stops the whole run. A type ending in `ItemBlocked` stops one member, and the batch carries on. Define `RunFatal` outside the `ItemBlocked` branch, and put the `try`/`except` inside the loop body with the `RunFatal` re-raise first.

Four failures end a run: the source bytes changed, a provenance or digest mismatch, authentication is required, or a runtime crash such as `TypeError`. Work every other failure. Repair in place, take three attempts (three theories of the cause), then park the member and move on. The batch always reaches a deliverable. Three members parked with the same signature share one cause. The closing report gives every issue one line with how it ended, plus a recommended durable fix.

**Enforcement:** `code_rules_blast_radius.py`, which the staged policy lint runs through `code_rules_enforcer.py` under its `code-rules` rule. CI runs it against the merge base.

**Full text:** [`docs/rule-guides/failure-blast-radius.md`](../docs/rule-guides/failure-blast-radius.md), with the boundary example and the Codex excerpt.
