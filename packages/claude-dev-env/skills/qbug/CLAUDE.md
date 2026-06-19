# qbug

Quick baseline PR audit: one clean-coder subagent loops audit → fix → commit → push until the PR is clean or stuck.

**Trigger:** `/qbug`, "quick bug audit", "solo bug audit", "baseline PR review", "bugteam without a team".

## Purpose

`/qbug` is the required baseline review for every new PR. It runs the same A–N bug category rubric and CODE_RULES gate as `/bugteam` but with a single persistent subagent (no TeamCreate, no per-loop clean-room, no loop cap). Escalate to `/bugteam` when bias isolation across loops matters.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | The complete skill — four steps (pre-flight, resolve PR scope, spawn subagent cycle, final report). Self-contained with full subagent XML prompt inline. |

## Shared artifacts (referenced by path, not copied)

The skill references shared scripts from `../_shared/pr-loop/scripts/`:

| Script | Role |
|---|---|
| `preflight.py` | Git hooks path check, pytest, optional pre-commit |
| `code_rules_gate.py` | CODE_RULES gate run before every AUDIT |
| `post_audit_thread.py` | Posts one GitHub review per loop (APPROVE or REQUEST_CHANGES) |
| `audit-reply-template.md` | Unified reply body shape for resolved threads |

Bug category rubric A–N lives at `../bugteam/PROMPTS.md`. Audit contract (finding schema, proof-of-absence, Haiku secondary, self-audit) lives at `../bugteam/reference/audit-contract.md`.

## Subagent structure

- **Primary:** `clean-coder` — runs the full audit → fix → commit → push cycle internally.
- **Secondary:** `code-quality-agent` (Haiku model) — audit-only, read-only; findings merged before FIX step.
- No `TeamCreate`. No loop cap. Exits on `converged`, `stuck`, or `error`.

## Conventions

- The lead resolves the temp directory via Python's `tempfile.gettempdir()` and passes the absolute path to the subagent.
- Each loop: one `code_rules_gate.py` pre-audit, one GitHub review posted, one commit on fix.
- Self-PR toggle: `post_audit_thread.py` detects author-equals-reviewer and switches to an alternate `gh` account automatically.
