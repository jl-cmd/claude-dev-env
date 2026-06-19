# findbugs

Audits the current branch's pull request for bugs by spawning the `code-quality-agent` against the full PR diff in a clean room. Triggered by `/findbugs`, `find bugs in this PR`, `audit the PR`, or `bug audit on the branch`.

## Purpose

Read-only. The skill resolves PR scope, writes the diff to a scoped temp file, and spawns two `code-quality-agent` instances (primary sonnet + secondary haiku) with a self-contained, context-free prompt covering all A–P audit categories. After both return it merges findings (de-dup, max-wins severity), posts one audit review to the PR via `post_audit_thread.py` (APPROVE on clean, REQUEST_CHANGES with inline anchored comments on dirty), and reports totals and cleared categories to the user.

## Key file

| File | Purpose |
|---|---|
| `SKILL.md` | Five-step process: resolve scope, capture diff to a scoped temp path, spawn agents (clean-room prompt XML), post audit review via `post_audit_thread.py`, surface findings and offer `/fixbugs`. Includes refusals, output format, and the anchored-vs-unanchored finding split. |

## Constraints

- Never edits files, never commits, never pushes.
- One audit review per invocation is posted back to the PR — required so the unresolved-thread gate sees the audit pass.
- Disabled by `CLAUDE_REVIEWS_DISABLED=bugteam` (shared token across the audit-skill family).
- Always ask before running `/fixbugs`; never auto-spawn the fixer.
