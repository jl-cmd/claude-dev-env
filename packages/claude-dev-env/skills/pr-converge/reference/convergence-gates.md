# Convergence gates

Run **only** when Step 2 BUGTEAM reports `convergence (zero findings)` AND
`bugbot_clean_at == current_head` AND no push during bugteam tick. Gates run
in order; first failure determines next-tick behavior. Mark PR ready only
when all four pass.

## (a) Copilot findings gate

Fetch latest Copilot reviewer (`copilot-pull-request-reviewer[bot]`) review
plus inline comments anchored to most recent Copilot review on
`current_head`:

```
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_reviews")
  → filter `.user.login` for copilot (case-insensitive substring "copilot")
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
  plus all four gates must hold again on new HEAD.
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
  `copilot_clean_at = current_head`. Continue to gate (b).
- **No Copilot review on `current_head` yet:** Skip — gate (c) issues
  proactive request. Continue to gate (b).

## (b) Mergeability gate

Resolve PR's mergeability state:

```
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get")
  → `.mergeable_state`, `.mergeable`
```

Persist `mergeable_state` into `merge_state_status`. Decide:

- **`mergeable_state == "clean"` AND `mergeable == true`:**
  Continue to gate (c).
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

## (c) Post-convergence Copilot review request

Once gates (a) and (b) both pass (Copilot clean at `current_head` *or* no
Copilot review yet, AND `mergeable_state == "clean"`), request Copilot
review:

```
request_copilot_review(owner=OWNER, repo=REPO, pullNumber=NUMBER)
```

When the `request_copilot_review` MCP tool is unavailable, use `add_issue_comment` as fallback: `add_issue_comment(owner=OWNER, repo=REPO, issueNumber=NUMBER, body="@copilot review")`.

After request, schedule next wakeup and return — next tick checks response.

Next tick with `phase == BUGTEAM` and prior state preserved → re-run gate
(a) first. Decide:

- **Copilot review `clean` (state `APPROVED`):** Set `copilot_clean_at =
  current_head`. Mark PR ready (`update_pull_request(pullNumber=NUMBER, owner=OWNER, repo=REPO, draft=false)`), report convergence
  per §(d), terminate per [stop-conditions.md](stop-conditions.md) / Convergence.
- **Copilot review `dirty`:** Treat identically to gate (a) dirty path —
  spawn Agent (subagent_type: clean-coder) to fix in same PR, restart convergence from BUGBOT. Follow [Single-PR fix workflow](fix-protocol.md#single-pr-fix-workflow).
  For body-only findings with empty inline, spawn Agent (subagent_type: clean-coder) to implement, then post top-level review reply
  citing new HEAD SHA. Reset `bugbot_clean_at = null` AND
  `copilot_clean_at = null`, `phase = BUGBOT`, schedule next wakeup,
  return. Full back-to-back-clean cycle plus all four gates must hold
  again on new HEAD.
- **No Copilot review at `current_head` yet (still propagating):**
  Schedule one more wakeup (270s), re-check next tick. After three consecutive empty waits,
  escalate as hard blocker per [stop-conditions.md](stop-conditions.md).

## (d) Mark ready and report

Only when all four gates pass — bugbot CLEAN ∧ bugteam CLEAN ∧
`mergeable_state == "clean"` ∧ Copilot CLEAN at HEAD — run:

Use the `update_pull_request` MCP tool:

    update_pull_request(pullNumber=NUMBER, owner=OWNER, repo=REPO, draft=false)

With `state.json`, append convergence row to
`<TMPDIR>/pr-converge-<session_id>/converged.log` per `multi-pr-orchestration.md` §Memory; else skip.
Report: `PR #<NUMBER> converged: bugbot CLEAN at <SHA>, bugteam CLEAN at
<SHA>, mergeable_state CLEAN, copilot CLEAN at <SHA>; marked ready for
review`. **Omit loop pacing** per **Convergence** of active pacing workflow.
