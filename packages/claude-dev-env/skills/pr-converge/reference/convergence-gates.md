# Convergence gates

Run **only** when Step 2 BUGTEAM reports `convergence (zero findings)` AND
`bugbot_clean_at == current_head` AND no push during bugteam tick. Gates run
in order; first failure determines next-tick behavior. Mark PR ready only
when all six pass.

**Mandatory evidence rule:** Every gate that fetches data MUST produce a
summary of its findings before proceeding to the next gate. Gate (f) MUST
reference evidence from each prior gate. Skipping any gate silently is a
hard blocker — report "gate evidence missing: <gate name>" and omit loop
pacing. Do not mark ready with unverified gates.

## (a) Copilot findings gate

Fetch latest Copilot reviewer (`copilot-pull-request-reviewer[bot]`) review
plus inline comments anchored to most recent Copilot review on
`current_head`:

```
python ~/.claude/skills/pr-converge/scripts/fetch_copilot_reviews.py --owner <O> --repo <R> --pr-number <N>
  → filter by `.commit_id == current_head`, sort by `.submitted_at` descending

python ~/.claude/skills/pr-converge/scripts/fetch_copilot_inline_comments.py --owner <O> --repo <R> --pr-number <N> --commit <current_head>
  → unaddressed inline threads on the latest Copilot review at current_head
```

Decide (four branches; match first whose predicate holds):

- **`classification == "dirty"` with non-empty inline comments matching
  `pull_request_review_id`:** Fix protocol input (same shape as bugbot
  dirty). Spawn Agent (subagent_type: clean-coder) to implement → push → reply inline on each thread via
  `python ~/.claude/skills/pr-converge/scripts/post_fix_reply.py` → Step 3 in same tick (see
  [Single-PR fix workflow](fix-protocol.md#single-pr-fix-workflow) for
  full contract).
  Reset `bugbot_clean_at = null` AND `copilot_clean_at = null`, `phase =
  BUGBOT`, schedule next wakeup, return. Full back-to-back-clean cycle
  plus all six gates must hold again on new HEAD.
- **`classification == "dirty"` with empty inline comments matching
  `pull_request_review_id`:** Copilot posted findings only in review body
  (`CHANGES_REQUESTED` or `COMMENTED` with non-empty body, no inline
  threads). Parse body for actionable findings. Spawn Agent (subagent_type: clean-coder) to implement → push → post
  top-level review reply via `python ~/.claude/skills/pr-converge/scripts/post_fix_reply.py` citing new HEAD SHA → Step 3 in same tick.
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
    AND `.commit_id == current_head`
  → sort by `.submitted_at` descending

pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_review_comments")
  → filter threads where `is_outdated == false` AND `is_resolved == false`
    AND `pull_request_review_id` matches the newest Claude review on `current_head`
    AND any comment has `.author` matching Claude (case-insensitive substring "claude")
```

Decide (four branches; match first whose predicate holds):

- **`classification == "dirty"` with non-empty inline comments matching
  `pull_request_review_id`:** Treat identically to gate (a) dirty+inline
  path — spawn Agent (subagent_type: clean-coder) to fix → push → reply inline on each thread. Reset
  `bugbot_clean_at = null` AND `copilot_clean_at = null`, `phase = BUGBOT`,
  schedule next wakeup, return.
- **`classification == "dirty"` with empty inline comments matching
  `pull_request_review_id`:** Claude posted findings only in review body
  (`CHANGES_REQUESTED` or `COMMENTED` with non-empty body, no inline
  threads). Treat identically to gate (a) dirty+body path — spawn Agent
  (subagent_type: clean-coder) to implement → push → post top-level review reply via `python ~/.claude/skills/pr-converge/scripts/post_fix_reply.py`. Reset
  `bugbot_clean_at = null` AND `copilot_clean_at = null`, `phase = BUGBOT`,
  schedule next wakeup, return.
- **`classification == "clean"` (state `APPROVED`):** Record evidence:
  "Claude APPROVED at <SHA>". Continue to gate (c).
- **No Claude review on `current_head` yet:** Record evidence:
  "Claude absent at <SHA>". Continue to gate (c).

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
- **`mergeable_state` is `"blocked"`, `"behind"`, `"unknown"`, or `"unstable"` for
  non-conflict reasons** (required checks pending/failing for "unstable",
  branch behind base without conflicts for "behind", GitHub indeterminate
  for "unknown"): **hard blocker** per
  [stop-conditions.md](stop-conditions.md) — do not invent a fix. Report specific
  `mergeable_state`, omit loop pacing.

## (d) Post-convergence Copilot review request

Once gates (a), (b), and (c) all pass (Copilot clean at `current_head` *or* no
Copilot review yet, AND Claude clean or absent at `current_head`, AND
`mergeable_state == "clean"`), request Copilot review:

```
gh api --method POST repos/<O>/<R>/pulls/<N>/requested_reviewers \
  -f 'reviewers[]=copilot-pull-request-reviewer[bot]'
```

Check for an existing pending review first with
`python ~/.claude/skills/pr-converge/scripts/check_pending_reviews.py --owner <O> --repo <R> --pr-number <N> --user copilot`.

After request, set `phase = COPILOT_WAIT`, schedule next wakeup, and return.
The COPILOT_WAIT phase prevents the agent from re-entering convergence gates
while Copilot processes. Next tick with `phase == COPILOT_WAIT`:
re-run the fetch from gate (a) — `python ~/.claude/skills/pr-converge/scripts/fetch_copilot_reviews.py`
plus MCP `get_review_comments` filtered for Copilot inline threads —
against `current_head`. Decide:

- **Copilot review present at `current_head`:**
  - `state: APPROVED` → set `copilot_clean_at = current_head`. Record
    evidence: "Copilot APPROVED at <SHA>". Re-validate gates (b) and (c)
    on same tick (Claude status and mergeability may have changed while
    waiting). Set `phase = BUGTEAM`.
    Continue to gate (e) when (b) and (c) still pass.
  - `state: CHANGES_REQUESTED` or `COMMENTED` with non-empty body → dirty.
    Treat identically to gate (a) dirty path — spawn Agent (subagent_type: clean-coder) to fix,
    reset `bugbot_clean_at = null` AND `copilot_clean_at = null`,
    `phase = BUGBOT`, schedule next wakeup, return.
- **No Copilot review at `current_head` yet:** Record evidence: "No Copilot
  review at <SHA> (wait count: <N>)". Increment `copilot_wait_count`
  (init 0 on first COPILOT_WAIT entry; reset to 0 on every push and on every
  successful Copilot review). After three consecutive empty waits
  (`copilot_wait_count >= 3`), escalate as hard blocker — report
  "Copilot did not surface a review on current_head after 3 wakeups"
  and omit loop pacing. Otherwise schedule next wakeup (360s), return.

## (e) Thread-resolution gate

Before marking ready, count unresolved review threads from all bot
reviewers (Bugbot, Copilot, Claude) anchored to `current_head`:

```
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_review_comments")
  → filter threads where `is_outdated == false` AND `is_resolved == false`
    AND any comment has `.author` matching a bot reviewer
    (case-insensitive substring "copilot", "cursor", "bugbot", or "claude")
  → count
```

Decide:

- **Zero unresolved threads at `current_head`:** Record evidence:
  "0 unresolved threads at <SHA>". Continue to gate (f).
- **One or more unresolved threads:** Do **not** mark ready. Apply Fix
  protocol on each unresolved thread. Reset `bugbot_clean_at = null` AND
  `copilot_clean_at = null`, `phase = BUGBOT`, schedule next wakeup, return.

## (f) Mark ready and report

**Mandatory pre-condition checklist.** Before calling `update_pull_request`,
verify ALL seven conditions below. Three are preconditions from the main
loop (bugbot clean, bugteam convergence, no intervening push); four are
evidence from gates (a)–(e) above. All seven must be confirmed:

- [ ] `bugbot_clean_at == current_head` (from per-tick.md Step 2 BUGBOT §c)
- [ ] bugteam `convergence (zero findings)` at `current_head` (from per-tick.md Step 2 BUGTEAM §d)
- [ ] `copilot_clean_at == current_head` (from gate (a) or gate (d))
- [ ] Claude `APPROVED` or absent at `current_head` (from gate (b))
- [ ] `mergeable_state == "clean"` AND `mergeable == true` (from gate (c))
- [ ] Zero unresolved bot review threads at `current_head` (from gate (e))
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
