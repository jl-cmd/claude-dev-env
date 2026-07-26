# Fix protocol

Open and apply the shared fix sequence in
[`../../_shared/pr-loop/fix-protocol.md`](../../_shared/pr-loop/fix-protocol.md)
— executor choice, the 13-step sequence, reply transport, thread resolution,
and post-push resets. Hook handling per [ground-rules.md](ground-rules.md).

This file holds only the pr-converge deltas: the multi-PR teammate
obligations and the same-tick re-entry rule.

**Multi-PR (`state.json`) teammate obligations** (plus TDD, commit, push):

- Replies inline on each addressed finding via
  `python scripts/post_fix_reply.py --owner <O> --repo <R> --pr-number <N> --in-reply-to <COMMENT_ID> --body <text>`
  (what changed + commit identifier), matching §Audit result → fix worker step 4 — **before** writing
  `state.json` and going idle.
- Writes `last_action: "fix_pushed"`, `current_head: <new SHA>`,
  `bugbot_clean_at: null`, `code_review_clean_at: null`,
  `bugteam_clean_at: null`, `copilot_clean_at: null`,
  `merge_state_status: null`, `bugbot_down: false`, `codex_down: false`,
  `phase: "CODE_REVIEW"`, `status: "awaiting_code_review"`, `last_updated`
  (ISO-8601 UTC) to `state.json` (per §Concurrency).
- Goes idle. Orchestrator spawns a follow-up `general-purpose` agent for the
  CODE_REVIEW re-entry on the new HEAD.

Orchestrator does not reply inline, re-enter code-review, or read repo source
files during fix phase in multi-PR mode.

### Same-tick re-entry rule

**After pushing a fix, re-enter the CODE_REVIEW phase in the same tick**
regardless of phase. A new commit **resets the full convergence cycle**: a
code-review clean, a bugteam clean, and a Bugbot clean on an older SHA do
**not** count toward convergence on the new `HEAD`. Re-run the static sweep and
`/code-review ultra --fix` on `current_head`, then bugteam, then the terminal
Bugbot gate, all on the same `HEAD` with no intervening push. Re-entering in the
same tick saves a wakeup cycle.
