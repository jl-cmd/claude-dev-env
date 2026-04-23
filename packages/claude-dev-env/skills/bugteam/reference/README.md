# Bugteam reference

Expanded material that used to live inline in `SKILL.md`. Load a file when the orchestration stub in `SKILL.md` is not enough — debugging GitHub review shape, gate semantics, teardown edge cases, or explaining the design to a human.

| File | Domain |
|------|--------|
| [`design-rationale.md`](design-rationale.md) | Why agent teams (clean-room), table-of-contents habit, when `/bugteam` applies, refusal reasons |
| [`team-setup.md`](team-setup.md) | Permissions grant (`CLAUDE_SKILL_DIR`), PR scope, `TeamCreate`, team name / sanitization / temp dir / roles / loop state |
| [`github-pr-reviews.md`](github-pr-reviews.md) | Per-loop reviews, `jq` + `gh api` payloads, anchors, fallbacks, REST endpoints |
| [`audit-and-teammates.md`](audit-and-teammates.md) | Pre-audit gate, full cycle numbering, AUDIT and FIX actions, parallel auditors |
| [`teardown-publish-permissions.md`](teardown-publish-permissions.md) | Utility scripts note, teardown, PR description rewrite, revoke, final report |

Canonical documentation quotes: [`../sources.md`](../sources.md).

## Retired: pre-push-review skill

The `pre-push-review` skill was retired. Its mechanical checks are now covered automatically by the expanded code-rules enforcer and the git hooks installed via `npx claude-dev-env`.

**What replaced what:**

- **Mechanical pre-push checks** (magic values, boolean naming, imports, constants location, and other CODE_RULES checks) — handled by the `code_rules_enforcer.py` PreToolUse hook (blocks at write time) and by the git pre-push hook installed via `npx claude-dev-env`. The git pre-push hook is the gate that runs at `git push` time; no manual invocation is needed.

- **`/qbug`** — a full PR audit-fix cycle that spawns subagents, runs multiple audit loops, and produces a structured report. It is NOT a lightweight pre-push gate. Do not use `/qbug` as a substitute for `git push` (the hook fires automatically). Use `/qbug` when you want a thorough multi-loop review of a PR before requesting human review.

References updated:
- `skills/pr-review-responder/SKILL.md` — Rule 6 and checklist item updated to reference the git pre-push hook
- `commands/plan.md` — Phase 5 step 10 updated to reference the git pre-push hook
- `hooks/github-action/pre-push-review.yml` — deleted (workflow no longer needed)
- `hooks/github-action/test_workflow.py` — deleted alongside the workflow
