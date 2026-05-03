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

Adds the same **traffic** fields whether they live in **`state.json`** or in the **conversation state line**; only the **store** differs.

| Field | Type | Purpose |
|---|---|---|
| `phase` | enum | `BUGBOT` \| `BUGTEAM` — which reviewer the current tick drives |
| `current_head` | str | PR `headRefOid` / `git rev-parse` for the PR under work (each tick; from `view_pr_context.py` when no file store) |
| `bugbot_clean_at` | str \| null | HEAD SHA at which Cursor Bugbot last reported clean, or `null` (reset on every push) |
| `inline_lag_streak` | int | Consecutive ticks where bugbot's review body claims findings but inline-comments API returns zero rows for `current_head` |
| `tick_count` | int | Observability only — **no ceiling**; loop ends on convergence or **Stop conditions** in `pr-converge` |

**Dual persistence** (normative: `skills/pr-converge/SKILL.md` § State across ticks, § Multi-PR orchestration model):

| Mode | When it applies | Source of truth | `tick_count` bump |
|---|---|---|---|
| **`state.json`** | File exists at `<TMPDIR>/pr-converge-<session_id>/state.json` (multi-PR orchestration or other file-backed session) | JSON: top-level `session_id`; per-PR objects under `prs[<number>]` with `owner`, `repo`, `branch`, `phase`, `current_head`, `bugbot_clean_at`, `inline_lag_streak`, `tick_count`, `last_action`, `status`, `last_updated`. Optional sibling `converged.log` (append-only; multi-PR only). Writes use lock + atomic replace per skill **Concurrency** | **Orchestrator only** at tick start (locked merge for every non-terminal PR); **never** bump `tick_count` in Step 1 when this file is in use |
| **Conversation state line** | **No** `state.json` (typical single-PR `/pr-converge` in Cursor) | Persist **`phase`**, **`bugbot_clean_at`**, **`inline_lag_streak`**, **`tick_count`** as **plain text** in each assistant turn; next tick reads them from the **most recent assistant message**. **`current_head` is not serialized in that line** — re-resolve each tick via `view_pr_context.py` (same contract as `skills/pr-converge/SKILL.md` § State across ticks). | **Step 1** increments `tick_count` in that line **only** when no `state.json` — must not double-count with any file-backed path |

**`status` (file-backed `prs[...]` only):** `fresh` \| `in_progress` \| `awaiting_bugbot` \| `awaiting_bugteam` \| `converged` \| `blocked`

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
- pr-converge: `bugbot_clean_at` resets to `null` on every push (a new commit invalidates prior clean by definition); `phase` cycles each tick. With `state.json`, orchestrator reads that file at tick start; without it, rely on the prior conversation state line — **never** mix both increment rules for `tick_count` on the same run
- monitor-many: persists across orchestrator runs; only `last_seen_comment_id` advances monotonically

## Convergence checks

- bugteam, qbug: `last_action == "audited"` AND `last_findings.total == 0` → `converged`
- pr-converge: `bugbot_clean_at == current_head` AND most-recent bugteam exit is `converged` AND no push during the bugteam tick → back-to-back clean → `gh pr ready` (read `current_head` / `bugbot_clean_at` from `state.json` when file-backed, else from the conversation state line and Step 1 `view_pr_context.py` output)
- monitor-many: no unresolved comments requiring code changes AND required checks green AND review policy satisfied → `gh pr ready`
