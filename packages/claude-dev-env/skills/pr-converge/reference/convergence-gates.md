# Convergence gates

Run **only** when Step 2 BUGTEAM reports `convergence (zero findings)` AND
`bugbot_clean_at == current_head` AND no push during bugteam tick. Gates run
in order; first failure determines next-tick behavior. Mark PR ready only
when all four pass.

## (a) Copilot findings gate

Fetch latest Copilot reviewer (`copilot-pull-request-reviewer[bot]`) review
plus inline comments anchored to most recent Copilot review on
`current_head`:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/fetch_copilot_reviews.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>

python "${CLAUDE_SKILL_DIR}/scripts/fetch_copilot_inline_comments.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER> --commit "$current_head"
```

Decide (four branches; match first whose predicate holds):

- **`classification == "dirty"` with non-empty inline comments matching
  `pull_request_review_id`:** Fix protocol input (same shape as bugbot
  dirty). Spawn Agent (subagent_type: clean-coder) to implement → push → reply inline on each thread via
  `reply_to_inline_comment.py` → Step 3 in same tick (see
  [Single-PR fix workflow](fix-protocol.md#single-pr-fix-workflow) for
  full contract).
  Reset `bugbot_clean_at = null` AND `copilot_clean_at = null`, `phase =
  BUGBOT`, schedule next wakeup, return. Full back-to-back-clean cycle
  plus all four gates must hold again on new HEAD.
- **`classification == "dirty"` with empty inline comments matching
  `pull_request_review_id`:** Copilot posted findings only in review body
  (`CHANGES_REQUESTED` or `COMMENTED` with non-empty body, no inline
  threads). Parse body for actionable findings. Spawn Agent (subagent_type: clean-coder) to implement → push → post
  top-level review reply citing new HEAD SHA → Step 3 in same tick (see
  [Single-PR fix workflow](fix-protocol.md#single-pr-fix-workflow) for
  full contract).
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

```bash
python "${CLAUDE_SKILL_DIR}/scripts/check_pr_mergeability.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>
```

Persist `mergeStateStatus` into `merge_state_status`. Decide:

- **`mergeStateStatus == "CLEAN"` AND `mergeable == "MERGEABLE"`:**
  Continue to gate (c).
- **`mergeStateStatus == "DIRTY"` (or `mergeable == "CONFLICTING"`):** Do
  **not** mark ready. Invoke **`rebase`** skill
  ([`../../rebase/SKILL.md`](../../rebase/SKILL.md)) Phase 1–4 against PR's
  base ref. After rebase + force-with-lease push, new HEAD invalidates
  every prior clean state — reset `bugbot_clean_at = null`,
  `copilot_clean_at = null`, `merge_state_status = null`, `phase = BUGBOT`,
  Step 3 on new HEAD, schedule next wakeup, return. Loop re-runs from
  scratch on new HEAD.
- **`mergeStateStatus` is `BLOCKED`, `BEHIND`, or `UNKNOWN` for
  non-conflict reasons** (required checks pending, branch behind base
  without conflicts GitHub cannot auto-resolve): **hard blocker** per
  [stop-conditions.md](stop-conditions.md) — do not invent a fix. Report specific
  `mergeStateStatus`, omit loop pacing.

## (c) Post-convergence Copilot review request

Once gates (a) and (b) both pass (Copilot clean at `current_head` *or* no
Copilot review yet, AND `mergeStateStatus == "CLEAN"`), request Copilot
review:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/request_copilot_review.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>
```

After request, schedule next wakeup and return — next tick checks response.

Next tick with `phase == BUGTEAM` and prior state preserved → re-run gate
(a) first. Decide:

- **Copilot review `clean` (state `APPROVED`):** Set `copilot_clean_at =
  current_head`. Mark PR ready (`mark_pr_ready.py`), report convergence
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
`mergeStateStatus == "CLEAN"` ∧ Copilot CLEAN at HEAD — run:

```bash
python "${CLAUDE_SKILL_DIR}/scripts/mark_pr_ready.py" \
--owner <OWNER> --repo <REPO> --number <NUMBER>
```

When scripts unavailable, `gh pr ready <NUMBER> --repo <OWNER>/<REPO>` is
equivalent. With `state.json`, append convergence row to
`<TMPDIR>/pr-converge-<session_id>/converged.log` per `multi-pr-orchestration.md` §Memory; else skip.
Report: `PR #<NUMBER> converged: bugbot CLEAN at <SHA>, bugteam CLEAN at
<SHA>, mergeStateStatus CLEAN, copilot CLEAN at <SHA>; marked ready for
review`. **Omit loop pacing** per **Convergence** of active pacing workflow.
