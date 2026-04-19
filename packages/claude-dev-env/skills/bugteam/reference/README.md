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
