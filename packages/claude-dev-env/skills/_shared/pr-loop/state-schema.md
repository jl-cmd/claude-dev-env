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

## Workflow-specific extensions

### bugteam

Adds:
- `team_name` — `bugteam-pr-<N>-<YYYYMMDDHHMMSS>` or `bugteam-<YYYYMMDDHHMMSS>` for multi-PR
- `team_temp_dir` — absolute path resolved from `tempfile.gettempdir()`
- `pre_fix_sha` — `git rev-parse HEAD` immediately before each FIX
- `gate_round_count` — consecutive pre-audit gate failures (cap: 5 → exit `error`)

State lives inline in the lead session (orchestrator). Cleared on TeamDelete.

### qbug

Adds nothing beyond common. Single subagent loops internally and returns a final summary; orchestrator discards intermediate state. Subagent's loop counter and findings return in the exit payload (`{exit_reason, loop_count, final_commit_sha, audit_log, unresolved}`).

### pr-converge

Normative field list, phase enum, dual persistence, and reset semantics: [`../../pr-converge/reference/state-schema.md`](../../pr-converge/reference/state-schema.md). File-backed multi-PR `status` enum: [`../../pr-converge/reference/multi-pr-orchestration.md`](../../pr-converge/reference/multi-pr-orchestration.md).

### monitor-many

Adds per-PR JSON state file at `~/.claude/skills/monitor-many/state/<owner>-<repo>-<pr_number>.json`:

| Field | Type | Description |
|---|---|---|
| `repo_name` | str | Full `owner/repo` |
| `pr_number` | int | PR number |
| `status` | enum | `open`, `blocked_escalation`, `fixing`, `ready_candidate`, `closed` |
| `copilot_review` | enum | `none`, `requested`, `pending`, `commented`, `approved` |
| `bugbot_review` | enum | Same vocabulary as `copilot_review`; one of `none`, `requested`, `pending`, `commented`, `approved` |
| `last_seen_comment_id` | int \| null | Highest processed review-comment id (incremental polling watermark) |
| `review_comments` | list[object] | Optional cache; `{id, author, path, line}` per entry |
| `escalation_queue` | list[object] | Pending human-judgment items: `{comment_id, summary, created_at}` |

## Reset semantics

- bugteam: cleared on each new `/bugteam` invocation
- qbug: cleared on each new `/qbug` invocation
- pr-converge: see [`../../pr-converge/reference/state-schema.md`](../../pr-converge/reference/state-schema.md)
- monitor-many: persists across orchestrator runs; only `last_seen_comment_id` advances monotonically

## Convergence checks

- bugteam, qbug: `last_action == "audited"` AND `last_findings.total == 0` → `converged`
- pr-converge: see [`../../pr-converge/reference/convergence-gates.md`](../../pr-converge/reference/convergence-gates.md)
- monitor-many: no unresolved comments requiring code changes AND required checks green AND review policy satisfied → `gh pr ready`
