# bugteam

Runs an audit-fix loop on an open pull request until all findings are resolved or the 20-loop cap is reached. Triggered by `/bugteam`, `run the bug team`, `auto-fix the PR until clean`, or `loop audit and fix`.

## Purpose

Each loop: a `code-quality-agent` (fresh context, all A–P audit categories) produces an outcome XML; a `clean-coder` agent applies every fix; the lead commits, pushes, and posts a GitHub PR review (APPROVE on clean, REQUEST_CHANGES with inline anchored comments on dirty). Grants `.claude/**` write permissions at the start and revokes them at the end.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Hub — pre-flight call, refusals, audit-posting protocol, progress checklist, and situation-to-reference table. Read this first. |
| `PROMPTS.md` | Spawn XML, A–P category bindings, outcome XML schemas. |
| `CONSTRAINTS.md` | Invariants — what the loop must never violate. |
| `EXAMPLES.md` | Exit scenarios: converged, cap-reached, stuck, refusal, mixed-outcome. |
| `sources.md` | Doc URLs and verbatim quotes cited in the skill body. |

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Expanded workflow detail loaded on demand (team setup, audit contract, GitHub PR review shape, teardown). |
| `scripts/` | Python scripts executed by the lead or teammates at runtime. |

## Environment controls

- `CLAUDE_REVIEWS_DISABLED=bugteam` — disables the skill entirely (pre-flight exits 7).
- `BUGTEAM_PREFLIGHT_SKIP=1` — skips pytest in pre-flight.
- `BUGTEAM_REVIEWER_ACCOUNT=<login>` — names the alternate `gh` account for posting reviews when the PR author and reviewer identity match.
