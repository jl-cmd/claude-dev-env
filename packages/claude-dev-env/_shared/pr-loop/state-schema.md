# State schema

State each PR-loop workflow tracks across iterations. Workflows differ on persistence (in-memory vs files) and which fields they use; shapes overlap.

## Common fields

| Field | Type | Purpose |
|---|---|---|
| `loop_count` | int | Iterations completed; bumps on each AUDIT or tick |
| `last_action` | enum | `fresh` \| `audited` \| `fixed` — drives next-step dispatch |
| `last_findings` | object | `{p0, p1, p2, total}` count of findings from most recent AUDIT |
| `audit_log` | list[str] | Per-iteration one-line summaries for the final report |
| `starting_sha` | str | `git rev-parse HEAD` at workflow start |
| `loop_comment_index` | dict | `{finding_id: {finding_comment_id, finding_comment_url, used_fallback, fix_status, ...}}` |

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

Adds:
- `phase` — `BUGBOT` \| `BUGTEAM` (which reviewer the current tick fetches from)
- `bugbot_clean_at` — HEAD SHA at which Cursor Bugbot last reported clean, or `null`
- `inline_lag_streak` — int, consecutive ticks where bugbot's review body claims findings but inline-comments API returns zero matches
- `tick_count` — int, increments on every tick (safety cap: 30 → terminate)

State persists across ticks via the assistant's plain-text state line in conversation context. Each tick reads the prior state line and emits the updated one.

### monitor-many

Adds per-PR JSON state file at `~/.claude/skills/monitor-many/state/<owner>-<repo>-<pr_number>.json`:

| Field | Type | Description |
|---|---|---|
| `repo_name` | str | Full `owner/repo` |
| `pr_number` | int | PR number |
| `status` | enum | `open` \| `blocked_escalation` \| `fixing` \| `ready_candidate` \| `closed` |
| `copilot_review` | enum | `none` \| `requested` \| `pending` \| `commented` \| `approved` |
| `bugbot_review` | enum | Same vocabulary as `copilot_review` |
| `last_seen_comment_id` | int \| null | Highest processed review-comment id (incremental polling watermark) |
| `review_comments` | list[object] | Optional cache; `{id, author, path, line}` per entry |
| `escalation_queue` | list[object] | Pending human-judgment items: `{comment_id, summary, created_at}` |

## Reset semantics

- bugteam: cleared on each new `/bugteam` invocation
- qbug: cleared on each new `/qbug` invocation
- pr-converge: `bugbot_clean_at` resets to `null` on every push (a new commit invalidates prior clean by definition); `phase` cycles each tick
- monitor-many: persists across orchestrator runs; only `last_seen_comment_id` advances monotonically

## Convergence checks

- bugteam, qbug: `last_action == "audited"` AND `last_findings.total == 0` → `converged`
- pr-converge: `bugbot_clean_at == current_head` AND most-recent bugteam exit is `converged` AND no push during the bugteam tick → back-to-back clean → `gh pr ready`
- monitor-many: no unresolved comments requiring code changes AND required checks green AND review policy satisfied → `gh pr ready`
