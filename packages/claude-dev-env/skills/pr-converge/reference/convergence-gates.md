# Convergence gates

## Contents

- [(a) Copilot findings gate](#a-copilot-findings-gate)
- [(b) Claude reviewer gate (agent-side)](#b-claude-reviewer-gate-agent-side)
- [(c) Mergeability gate](#c-mergeability-gate)
- [(d) Post-convergence Copilot review request](#d-post-convergence-copilot-review-request)
- [(e) Thread-resolution gate](#e-thread-resolution-gate)
- [(f) Mark ready and report](#f-mark-ready-and-report)
- [(g) Codex review gate (conditional-required)](#g-codex-review-gate-conditional-required)
Run **only** after the terminal Bugbot gate confirms the HEAD
(`bugbot_clean_at == current_head` OR `bugbot_down`), which runs just before
these gates once Step 2 BUGTEAM reports `convergence (zero findings)` with no
push during the bugteam tick. Gates run in order; first failure determines
next-tick behavior. Mark PR ready only when every gate that applies passes.

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

When `copilot_down == true` (start-of-run quota pre-check), skip this gate
entirely — no Copilot fetch, no request, no poll, no agent. Record evidence
"Copilot bypassed (quota pre-check non-zero) at <SHA>" and continue to gate (b); the bypass
holds for the whole run and the quota API is not re-queried per tick. Otherwise
decide among the four branches below.

Decide (four branches; match first whose predicate holds):

- **`classification == "dirty"` with non-empty inline comments matching
  `pull_request_review_id`:** Fix protocol input (same shape as bugbot
  dirty). Apply the shared fix protocol ([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md); skill deltas in [`fix-protocol.md`](fix-protocol.md)) in the same tick.
  Reset push-invalidated markers per [ground-rules.md](ground-rules.md) /
  [state-schema.md](state-schema.md) (all `*_clean_at`, `merge_state_status`,
  `bugbot_down`, `bugbot_acknowledged_at`), `phase = CODE_REVIEW`, schedule
  next wakeup, return. Full back-to-back-clean cycle plus all six gates must
  hold again on new HEAD.
- **`classification == "dirty"` with empty inline comments matching
  `pull_request_review_id`:** Copilot posted findings only in review body
  (`CHANGES_REQUESTED` or `COMMENTED` with non-empty body, no inline
  threads). Parse body for actionable findings. Apply the
  shared fix protocol ([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md); skill deltas in [`fix-protocol.md`](fix-protocol.md)), whose reply
  step for body-only findings posts a top-level review reply citing the
  new HEAD SHA. Reset push-invalidated markers per
  [ground-rules.md](ground-rules.md) / [state-schema.md](state-schema.md)
  (all `*_clean_at`, `merge_state_status`, `bugbot_down`,
  `bugbot_acknowledged_at`), `phase = CODE_REVIEW`, schedule next wakeup,
  return. Convergence needs full back-to-back-clean on new HEAD.
- **`classification == "clean"` (state `APPROVED`):** Set
  `copilot_clean_at = current_head`. Record evidence: "Copilot APPROVED at <SHA>".
  Continue to gate (b).
- **No Copilot review on `current_head` yet:** Record evidence: "No Copilot review at <SHA>".
  Skip — gate (d) issues proactive request. Continue to gate (b).

## (b) Claude reviewer gate (agent-side)

Agent-side only — not a `check_convergence.py` condition. Fetch latest Claude
reviewer (`claude[bot]`) review plus inline comments anchored to most recent
Claude review on `current_head`:

```
pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_reviews")
  → filter `.user.login` for claude (case-insensitive substring "claude")
    AND `.commit_id == current_head`
  → sort by `.submitted_at` descending

pull_request_read(owner=OWNER, repo=REPO, pullNumber=NUMBER, method="get_review_comments")
  → filter threads where `is_resolved == false`
```

Decide (four branches; match first whose predicate holds):

- **`classification == "dirty"` with non-empty inline comments matching
  `pull_request_review_id`:** Treat identically to gate (a) dirty+inline
  path — apply the shared fix protocol ([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md); skill deltas in [`fix-protocol.md`](fix-protocol.md)). Reset push-invalidated markers per
  [ground-rules.md](ground-rules.md) / [state-schema.md](state-schema.md)
  (all `*_clean_at`, `merge_state_status`, `bugbot_down`,
  `bugbot_acknowledged_at`), `phase = CODE_REVIEW`, schedule next wakeup,
  return.
- **`classification == "dirty"` with empty inline comments matching
  `pull_request_review_id`:** Claude posted findings only in review body
  (`CHANGES_REQUESTED` or `COMMENTED` with non-empty body, no inline
  threads). Treat identically to gate (a) dirty+body path — apply the
  shared fix protocol ([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md); skill deltas in [`fix-protocol.md`](fix-protocol.md)). Reset
  push-invalidated markers per [ground-rules.md](ground-rules.md) /
  [state-schema.md](state-schema.md) (all `*_clean_at`, `merge_state_status`,
  `bugbot_down`, `bugbot_acknowledged_at`), `phase = CODE_REVIEW`, schedule
  next wakeup, return.
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
  every prior clean state — reset push-invalidated markers per
  [ground-rules.md](ground-rules.md) / [state-schema.md](state-schema.md)
  (all `*_clean_at`, `merge_state_status`, `bugbot_down`,
  `bugbot_acknowledged_at`), `phase = CODE_REVIEW`, schedule next wakeup,
  return. Loop re-runs from scratch on new HEAD.
- **`mergeable_state` is `"blocked"`, `"behind"`, `"unknown"`, or `"unstable"` for
  non-conflict reasons** (required checks pending/failing for "unstable",
  branch behind base without conflicts for "behind", GitHub indeterminate
  for "unknown"): **hard blocker** per
  [stop-conditions.md](stop-conditions.md) — do not invent a fix. Report specific
  `mergeable_state`, omit loop pacing.

## (d) Post-convergence Copilot review request

When `copilot_down == true` (start-of-run quota pre-check), skip this gate: do
not request a Copilot review and do not enter `COPILOT_WAIT`. Export
`CLAUDE_REVIEWS_DISABLED="copilot"` before gate (f)'s convergence check so
`check_convergence.py` bypasses the Copilot review and pending-review gates.
Continue to gate (e).

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
    waiting). Stay on `COPILOT_WAIT` — do not re-enter BUGTEAM.
    Continue to gate (e) when (b) and (c) still pass.
  - `state: CHANGES_REQUESTED` or `COMMENTED` with non-empty body → dirty.
    Treat identically to gate (a) dirty path — apply the shared fix protocol ([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md); skill deltas in [`fix-protocol.md`](fix-protocol.md)).
    Reset push-invalidated markers per [ground-rules.md](ground-rules.md) /
    [state-schema.md](state-schema.md) (all `*_clean_at`, `merge_state_status`,
    `bugbot_down`, `bugbot_acknowledged_at`), `phase = CODE_REVIEW`, schedule
    next wakeup, return.
- **No Copilot review at `current_head` yet:** Record evidence: "No Copilot
  review at <SHA> (wait count: <N>)". Increment `copilot_wait_count`
  (init 0 on first COPILOT_WAIT entry; reset to 0 on every push and on every
  successful Copilot review). After three consecutive empty waits
  (`copilot_wait_count >= 3`), escalate as hard blocker — report
  "Copilot did not surface a review on current_head after 3 wakeups"
  and omit loop pacing. Otherwise schedule next wakeup (360s), return.

## (e) Thread-resolution gate

Agent-side prep before the machine checklist in gate (f). The script label
`zero unresolved bot threads` is what marks ready; this gate clears those
threads first.

Machine filter (same as `check_convergence.py`):

- `isResolved == false`
- `isOutdated == true` → thread **excluded** (does not fail the gate)
- first-comment author login contains `cursor`, `claude`, or `copilot`
  (case-insensitive substrings only)

Broader unresolved-thread sweeps (all authors, including human reviewers) are
agent-side via the shared fix protocol ([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md); skill deltas in [`fix-protocol.md`](fix-protocol.md)) and are not script conditions.

Decide:

- **Zero unresolved bot threads** under the filter above: Record evidence:
  "0 unresolved bot threads at <SHA>". Continue to gate (f).
- **One or more unresolved bot threads:** Do **not** mark ready. Apply the
  shared fix protocol unresolved-thread sweep ([`../../../_shared/pr-loop/fix-protocol.md`](../../../_shared/pr-loop/fix-protocol.md) step 12; skill deltas in [`fix-protocol.md`](fix-protocol.md)). Push if any code changed → reset
  push-invalidated markers per [ground-rules.md](ground-rules.md) /
  [state-schema.md](state-schema.md) (all `*_clean_at`, `merge_state_status`,
  `bugbot_down`, `bugbot_acknowledged_at`), `phase = CODE_REVIEW`, schedule
  next wakeup, return. If only resolutions (no code changes), re-check this
  gate without resetting.

## (f) Mark ready and report

**Machine pre-condition checklist.** Run the script — do not hand-check labels:

```
python $HOME/.claude/skills/pr-converge/scripts/check_convergence.py \
  --owner <O> --repo <R> --pr-number <N> \
  [--bugbot-down] [--copilot-down] [--codex-down] \
  [--codex-clean-at <SHA>]
```

Ready means exit `0` and the line:

```
All pre-conditions met — PR is ready to mark ready.
```

Exact printed labels (script order):

1. `bugbot_clean_at == current_head`
2. `bugbot review body clean` (omitted when `bugbot_down`)
3. `bugteam_clean_at == current_head`
4. `copilot_clean_at == current_head`
5. `codex_clean_at == current_head` (skipped when usage is at/below threshold,
   null, `codex_down`, or the `codex` opt-out token)
6. `zero unresolved bot threads`
7. `PR is mergeable`
8. `no pending requested reviews`

On label 6: `isOutdated == true` excludes the thread; bot filter is login
substrings `cursor` | `claude` | `copilot` only. The script has no Claude
APPROVED review gate.

**Agent-side only (not script conditions):** Claude reviewer presence or
APPROVED state (gate (b)); broader non-bot thread sweeps; loop preconditions
such as no push since bugteam convergence. Confirm those in the agent path
before invoking the script; they never appear as `check_convergence.py` labels.

When the script fails (exit 1), do NOT mark ready. Report the FAIL label and
route through the matching fix path (BUGBOT for dirty reviews, rebase for
merge conflicts, Codex findings via the shared fix protocol, and so on).

When the script passes (exit 0):

Use the `update_pull_request` MCP tool:

    update_pull_request(pullNumber=NUMBER, owner=OWNER, repo=REPO, draft=false)

With `state.json`, append convergence row to
`<TMPDIR>/pr-converge-<session_id>/converged.log` per `multi-pr-orchestration.md` §Memory; else skip.
Report from the script's PASS lines (the eight labels above). **Omit loop
pacing** per **Convergence** of active pacing workflow.

## (g) Codex review gate (conditional-required)

Machine condition label: `codex_clean_at == current_head`.

**Threshold rule** (shared with `codex_usage_probe.py` —
`WEEKLY_USAGE_GATE_THRESHOLD_PERCENT`; never restate the numeric literal):

- When the weekly probe reports **more than** the threshold percent left: a
  clean Codex review on `current_head` is required. Stamp
  `codex_clean_at = current_head` after a clean skill run, and pass
  `--codex-clean-at <SHA>` (or keep it in `$CLAUDE_JOB_DIR/pr-converge-state.json`)
  so `check_convergence.py` can verify the stamp.
- When usage is **at or below** the threshold, or `percent_left` is null: the
  gate is skipped and never blocks ready.
- When `codex_down == true`, when `CLAUDE_REVIEWS_DISABLED` lists `codex`, or
  when the caller passes `--codex-down`: the gate is bypassed and never blocks.

**Agent path before the machine checklist:** run the usage probe, then when
required and not opted out, invoke the `codex-review` skill against the PR base
branch (HEAD vs base) per [per-tick.md](per-tick.md). Findings enter the shared
fix protocol; a `codex_down` classification sets `codex_down = true` and
continues without blocking.
