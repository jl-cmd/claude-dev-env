# Fix protocol

The full fix protocol — executor choice, the shared 13-step sequence,
reply transport, thread resolution, the unresolved-thread sweep, and
post-push resets — lives in the `pr-fix-protocol` skill
(`../../pr-fix-protocol/SKILL.md`), which follows the shared step
sequence in `../../../_shared/pr-loop/fix-protocol.md`. Hook handling
per [ground-rules.md](ground-rules.md).

This file holds only the pr-converge deltas: the multi-PR teammate
obligations and the same-tick re-trigger rule.

**Multi-PR (`state.json`) teammate obligations** (plus TDD, commit, push):

- Replies inline on each addressed finding via
  `python scripts/post_fix_reply.py --owner <O> --repo <R> --pr-number <N> --in-reply-to <COMMENT_ID> --body <text>`
  (what changed + commit identifier), matching §Audit result → fix worker step 4 — **before** writing
  `state.json` and going idle.
- Writes `last_action: "fix_pushed"`, `current_head: <new SHA>`,
  `bugbot_clean_at: null`, `bugbot_down: false`, `phase: "BUGBOT"`,
  `status: "awaiting_bugbot"`, `last_updated` (ISO-8601 UTC) to
  `state.json` (per §Concurrency).
- Goes idle. Orchestrator spawns follow-up `general-purpose` agent for
  bugbot trigger and monitoring.

Orchestrator does not reply inline, trigger bugbot, or read repo source
files during fix phase in multi-PR mode.

### Same-tick re-trigger rule

**After pushing a fix, always run Step 3 (`bugbot run`) in the same
tick** regardless of phase. A new commit **resets the full convergence
cycle**: a bugbot clean and a bugteam clean on an older SHA do **not**
count toward convergence on the new `HEAD`. Re-obtain bugbot CLEAN on
`current_head`, then bugteam CLEAN on the same `HEAD` with no
intervening push. Re-triggering in the same tick saves a wakeup cycle
vs deferring Step 3.
