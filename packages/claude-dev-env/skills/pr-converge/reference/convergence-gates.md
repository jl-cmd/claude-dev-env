# Convergence gates

Run **only** when Step 2 BUGTEAM reports `convergence (zero findings)` AND
`bugbot_clean_at == current_head` AND no push during bugteam tick. Gates run
in order; first failure determines next-tick behavior. Mark PR ready only
when all five validation gates (a)–(e) pass.

**Mandatory evidence rule:** Every gate that fetches data MUST produce a
summary of its findings before proceeding to the next gate. Gate (f) MUST
reference evidence from each prior gate. Skipping any gate silently is a
hard blocker per [stop-conditions.md](stop-conditions.md) — report "gate
evidence missing: <gate name>" and omit loop pacing.

## (a) Copilot findings gate

Fetch latest Copilot reviewer (`copilot-pull-request-reviewer[bot]`) review
plus inline comments anchored to most recent Copilot review on
`current_head`:

```
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_reviews")
  → filter `.user.login` for copilot (case-insensitive substring "copilot")
  → filter `.commit_id == current_head`
  → sort by `.submitted_at` descending

pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_review_comments")
  → filter threads where `is_outdated == false` AND any comment has `.author` matching Copilot (case-insensitive substring "copilot")
```

Decide (four branches; match first whose predicate holds):

- **`classification == "dirty"` with non-empty inline comments matching
  `pull_request_review_id`:** Fix protocol input (same shape as bugbot
  dirty). Spawn Agent (subagent_type: clean-coder) to implement → push → reply inline on each thread via
  `add_reply_to_pull_request_comment` MCP → Step 3 in same tick (see
  [Single-PR fix workflow](fix-protocol.md#single-pr-fix-workflow) for
  full contract).
  Reset `bugbot_clean_at = null` AND `copilot_clean_at = null`, `phase =
  BUGBOT`, schedule next wakeup, return. Full back-to-back-clean cycle
  plus all five gates must hold again on new HEAD.
- **`classification == "dirty"` with empty inline comments matching
  `pull_request_review_id`:** Copilot posted findings only in review body
  (`CHANGES_REQUESTED` or `COMMENTED` with non-empty body, no inline
  threads). Parse body for actionable findings. Spawn Agent (subagent_type: clean-coder) to implement → push → post
  top-level review reply using `pull_request_review_write(method="create", event="COMMENT", body)` citing new HEAD SHA → Step 3 in same tick.
  Reset
  `bugbot_clean_at = null` AND
  `copilot_clean_at = null`, `phase = BUGBOT`, Step 3 on new HEAD,
  schedule next wakeup, return. Convergence requires full
  back-to-back-clean on new HEAD.
- **`classification == "clean"` (state `APPROVED`):** Set
  `copilot_clean_at = current_head`. Record evidence: "Copilot APPROVED at <SHA>".
  Continue to gate (b).
- **No Copilot review on `current_head` yet:** Record evidence: "No Copilot review at <SHA>".
  Skip — gate (d) issues proactive request. Continue to gate (b).

## (b) Claude reviewer gate

Fetch latest Claude reviewer (`claude[bot]`) review plus inline comments
anchored to most recent Claude review on `current_head`:

```
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_reviews")
  → filter `.user.login` for claude (case-insensitive substring "claude")
  → filter `.commit_id == current_head`
  → sort by `.submitted_at` descending

pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_review_comments")
  → select newest Claude review from reviews step; filter threads by its
    `pull_request_review_id` where `is_outdated == false`

The `get_review_comments` endpoint returns threads keyed by
`pull_request_review_id`; filter to the review selected above so older
Claude threads on other commits are excluded.
```

Decide (same state-based classifier as gate (a), collapsed to two outcomes since
Claude findings go through Fix protocol regardless of inline vs body-only):

- **`classification == "dirty"` (state `CHANGES_REQUESTED` or `COMMENTED`
  with non-empty body, OR non-empty inline threads at `current_head`
  that are `is_outdated == false` AND `is_resolved == false`):** Treat identically to gate (a) dirty path — apply
  Fix protocol. Reset `bugbot_clean_at = null` AND `copilot_clean_at = null`,
  `phase = BUGBOT`, schedule next wakeup, return.
- **`classification == "clean"` (state `APPROVED` or no Claude review at
  `current_head`):** Record evidence: "Claude <APPROVED|absent> at <SHA>".
  Continue to gate (c).

## (c) Mergeability gate

Resolve PR's mergeability state:

```
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get")
  → `.mergeable_state`, `.mergeable`
```

Persist `mergeable_state` into `merge_state_status`. Decide:

- **`mergeable_state == "clean"` AND `mergeable == true`:**
  Record evidence: "mergeable_state clean, mergeable=true at <SHA>".
  Continue to gate (d).
- **`mergeable_state == "dirty"` (or `mergeable == false`):** Do
  **not** mark ready. Invoke **`rebase`** skill
  ([`../../rebase/SKILL.md`](../../rebase/SKILL.md)) Phase 1–4 against PR's
  base ref. After rebase + force-with-lease push, new HEAD invalidates
  every prior clean state — reset `bugbot_clean_at = null`,
  `copilot_clean_at = null`, `merge_state_status = null`, `phase = BUGBOT`,
  Step 3 on new HEAD, schedule next wakeup, return. Loop re-runs from
  scratch on new HEAD.
- **`mergeable_state` is `"blocked"`, `"behind"`, or `"unknown"` for
  non-conflict reasons** (required checks pending, branch behind base
  without conflicts GitHub cannot auto-resolve): **hard blocker** per
  [stop-conditions.md](stop-conditions.md) — do not invent a fix. Report specific
  `mergeable_state`, omit loop pacing.

## (d) Post-convergence Copilot review request

Once gates (a), (b), and (c) all pass AND gate (a) recorded "No Copilot review at
<SHA>" (i.e., Copilot has not already approved this HEAD), request Copilot review.
If gate (a) already set `copilot_clean_at = current_head` (Copilot APPROVED),
skip this gate and continue to gate (e).

```
request_copilot_review(owner=OWNER, repo=REPO, pullNumber=NUMBER)
```

When the `request_copilot_review` MCP tool is unavailable, use `add_issue_comment` as fallback: `add_issue_comment(owner=OWNER, repo=REPO, issueNumber=NUMBER, body="@copilot review")`.

After request, set `phase = COPILOT_WAIT`, schedule next wakeup, and return.
The COPILOT_WAIT phase prevents the agent from re-entering convergence gates
while Copilot processes. Next tick with `phase == COPILOT_WAIT`:

- **Copilot review present at `current_head`:**
  - `state: APPROVED` → reset `copilot_wait_count = 0`, set `copilot_clean_at = current_head`. Record
    evidence: "Copilot APPROVED at <SHA>". Set `phase = BUGTEAM`.
    Continue to gate (e) in same tick.
  - `state: CHANGES_REQUESTED` or `COMMENTED` with non-empty body → dirty.
    Reset `copilot_wait_count = 0`. Treat identically to gate (a) dirty path —
    spawn Agent (subagent_type: clean-coder) to fix,
    reset `bugbot_clean_at = null` AND `copilot_clean_at = null`,
    `phase = BUGBOT`, schedule next wakeup, return.
- **No Copilot review at `current_head` yet:** Increment `copilot_wait_count`
  (init 0). After three consecutive empty waits (`copilot_wait_count >= 3`),
  escalate as hard blocker per [stop-conditions.md](stop-conditions.md).
  Otherwise schedule next wakeup (270s), return.

## (e) Thread-resolution gate

Before marking ready, count unresolved review threads from all
reviewers (bot and human) anchored to `current_head`:

```
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_review_comments")
  → filter threads where `is_outdated == false` AND `is_resolved == false`
  → count

The MCP `get_review_comments` endpoint returns `review_threads` with
`is_resolved` and `is_outdated` fields per thread. Each thread contains a
`comments` array whose first comment's `author` identifies the reviewer.
```

Decide:

- **Zero unresolved threads at `current_head`:** Record evidence:
  "0 unresolved threads at <SHA>". Continue to gate (f).
- **One or more unresolved threads:** Do **not** mark ready. Apply Fix
  protocol on each unresolved thread. Reset `bugbot_clean_at = null` AND
  `copilot_clean_at = null`, `phase = BUGBOT`, schedule next wakeup, return.

## (f) Mark ready and report

**Mandatory pre-condition checklist.** Before calling `update_pull_request`,
verify ALL of the following with evidence from prior gates:

- [ ] `bugbot_clean_at == current_head` (from per-tick.md Step 2 BUGBOT §c)
- [ ] bugteam `convergence (zero findings)` at `current_head` (from per-tick.md Step 2 BUGTEAM §d)
- [ ] `copilot_clean_at == current_head` (from gate (a) or gate (d))
- [ ] Claude `APPROVED` or absent at `current_head` (from gate (b))
- [ ] `mergeable_state == "clean"` AND `mergeable == true` (from gate (c))
- [ ] Zero unresolved review threads at `current_head` (from gate (e))
- [ ] No push since bugteam convergence (from per-tick.md Step 2 BUGTEAM §b)

If ANY checkbox cannot be confirmed with evidence, do NOT mark ready.
Report the specific missing condition and route through the appropriate
fix path (BUGBOT for dirty reviews, rebase for merge conflicts, etc.).

Only when ALL seven conditions are confirmed:

Use the `update_pull_request` MCP tool:

    update_pull_request(pullNumber=NUMBER, owner=OWNER, repo=REPO, draft=false)

With `state.json`, append convergence row to
`<TMPDIR>/pr-converge-<session_id>/converged.log` per `multi-pr-orchestration.md` §Memory; else skip.
Report: `PR #<NUMBER> converged: bugbot CLEAN at <SHA>, bugteam CLEAN at
<SHA>, mergeable_state clean, copilot CLEAN at <SHA>, claude <APPROVED|absent>
at <SHA>, 0 unresolved threads; marked ready for review`.
**Omit loop pacing** per **Convergence** of active pacing workflow.
