# State schema

State each PR-loop workflow tracks across iterations. Workflows differ on persistence (in-memory vs files) and which fields they use; shapes overlap.

## Common fields

| Field | Type | Purpose |
|---|---|---|
| `loop_count` | int | Iterations completed; bumps on each AUDIT or tick |
| `last_action` | enum | `fresh`, `audited`, `fixed` — drives next-step dispatch |
| `last_findings` | object | `{p0, p1, p2, total}` count of findings from most recent AUDIT |
| `audit_log` | list[str] | Per-iteration one-line summaries for the final report |
| `starting_sha` | str | `git rev-parse HEAD` at workflow start |
| `loop_comment_index` | dict | `{finding_id: {finding_comment_id, finding_comment_url, thread_node_id, fix_status, ...}}` (`thread_node_id` is the PR review thread node id — `PRRT_kwDOxxx` — captured at audit time when calling `get_review_comments`, used by `resolve_thread` at FIX time) |

## autoconverge (workflow and portable pacer)

Workflow runs hold round state in the workflow journal. On `pacer=portable`, the
continuous driver seeds `pr-converge-state.json` under the job directory and
advances phases through `portable_converge_driver.py`. Portable state carries
`current_head`, `phase`, `codex_clean_at`, `codex_down`, `codex_required`, and
pending `next` / `wait_seconds` stamps. Round shape and terminal gates are
documented in
[`../../.agents/skills/autoconverge/reference/convergence.md`](../../.agents/skills/autoconverge/reference/convergence.md).
The machine readiness checklist is
[`../../.agents/skills/autoconverge/reference/convergence-gates.md`](../../.agents/skills/autoconverge/reference/convergence-gates.md).

## Archived workflow extensions

Historical field lists for retired entry skills live under
`packages/claude-dev-env/.agents/skills-archived/`:

- **bugteam** — inline orchestrator state, `team_name`, `gate_round_count`, exit payload fields. See [`../../.agents/skills-archived/bugteam/SKILL.md`](../../.agents/skills-archived/bugteam/SKILL.md).
- **pr-converge** — file-backed multi-PR state, phase enum, dual persistence. See [`../../.agents/skills-archived/pr-converge/reference/state-schema.md`](../../.agents/skills-archived/pr-converge/reference/state-schema.md) and [`../../.agents/skills-archived/pr-converge/reference/multi-pr-orchestration.md`](../../.agents/skills-archived/pr-converge/reference/multi-pr-orchestration.md).

## Reset semantics

- **autoconverge** — portable state resets on a fresh `open-run`; workflow journal is per run id.
- **Archived bugteam** — cleared on each new invocation; see archived skill body.
- **Archived pr-converge** — see archived [`state-schema.md`](../../.agents/skills-archived/pr-converge/reference/state-schema.md); multi-PR file state persists across orchestrator runs and only `last_seen_comment_id` advances monotonically.

## Convergence checks

- **autoconverge** — `packages/claude-dev-env/_shared/pr-loop/scripts/check_convergence.py` is the single readiness source; gate labels are listed in [`../../.agents/skills/autoconverge/reference/convergence-gates.md`](../../.agents/skills/autoconverge/reference/convergence-gates.md). On pass, mark the PR ready (`gh pr ready`).
- **Archived pr-converge** — same script and archived [`convergence-gates.md`](../../.agents/skills-archived/pr-converge/reference/convergence-gates.md) reference.
