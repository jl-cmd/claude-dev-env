# Examples

Worked examples for `pr-converge`. Read on demand when a tick's
classification is novel or ambiguous against the in-skill rules. Cross-refs
into `SKILL.md` use `§Section name` notation.

<example> User: `/pr-converge` Claude: [PR context + one tick bugbot/bugteam
work; Step 4 per `workflows/schedule-wakeup-loop.md` — default loop until
convergence or stop]
</example>

<example> BUGBOT tick, latest bugbot review against older commit. Claude:
[posts `bugbot run`, sets `bugbot_clean_at = null`, Step 4 per
`workflows/schedule-wakeup-loop.md` (e.g. 270s wakeup), returns]
</example>

<example> BUGBOT tick, bugbot has 2 unaddressed findings on HEAD. Claude:
[TDD-fixes both, one commit, pushes, replies inline on both threads, posts
`bugbot run`, Step 4 at 270s, returns]
</example>

<example> BUGBOT tick, bugbot clean against HEAD. Claude: [sets
`bugbot_clean_at = HEAD`, `phase = CODE_REVIEW`, runs `/code-review --fix`
in same tick]
</example>

<example> CODE_REVIEW tick, `/code-review --fix` applies fixes to the
working tree. Claude: [commits the applied fixes in one commit, pushes,
resets `bugbot_clean_at = null` and `code_review_clean_at = null`, posts
`bugbot run`, `phase = BUGBOT`, Step 4 at 270s, returns]
</example>

<example> CODE_REVIEW tick, `/code-review --fix` clean (no changes
applied). Claude: [sets `code_review_clean_at = HEAD`, `phase = BUGTEAM`,
runs `Skill({skill: "bugteam", ...})` in same tick]
</example>

<example> BUGTEAM phase, bugteam reports convergence and `bugbot_clean_at
== current_head` (no push). Claude: [back-to-back clean — necessary, not
sufficient. Runs `convergence-gates.md` gates in order:
  Gate (a): two calls — `pull_request_read(method="get_reviews")` +
    `pull_request_read(method="get_review_comments")`
    → filter Copilot → APPROVED at `current_head`
    → record evidence, set `copilot_clean_at = current_head`.
  Gate (b): two calls — `pull_request_read(method="get_reviews")` +
    `pull_request_read(method="get_review_comments")`
    → filter Claude → absent at `current_head`
    → record evidence, continue (trivially clean).
  Gate (c): `pull_request_read(method="get")` → `.mergeable_state == "clean"`
    AND `.mergeable == true` → record evidence.
  Gate (d): set `phase = COPILOT_WAIT`;
    `request_copilot_review(owner=OWNER, repo=REPO, pullNumber=NUMBER)`
    → schedule next wakeup, return.
    Next tick: re-run gate (a) fetch → Copilot `APPROVED` at `current_head`
    → set `copilot_clean_at = current_head`, record evidence: "Copilot
    APPROVED at <SHA>", set `phase = BUGTEAM`, re-validate gates (b) and (c).
  Gate (e): `pull_request_read(method="get_review_comments")` → count
    threads where `is_resolved == false` (no author/commit/outdated
    filter) → zero across PR → record evidence.
  Gate (f): all six gates pass → `update_pull_request(pullNumber=NUMBER,
    owner=OWNER, repo=REPO, draft=false)`.
Reports "PR #N converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>,
mergeable_state clean, copilot CLEAN at <SHA>, claude absent at <SHA>,
0 unresolved threads across PR; marked ready for review",
applies **Convergence** from `workflows/schedule-wakeup-loop.md`]
</example>

<example> BUGTEAM phase, bugteam pushed fix commit during run. Claude:
[re-resolves HEAD, sets `bugbot_clean_at = null`, posts `bugbot run` in
same tick, `phase = BUGBOT`, Step 4 at 270s]
</example>

<example> BUGBOT tick, review body says "found 3 potential issues" against
HEAD but inline API returns zero matching for `current_head`. Claude:
[increments `inline_lag_streak` to 1, Step 4 inline-lag rules (90s
`ScheduleWakeup`), returns]
</example>

<example> Back-to-back clean reached, but `mergeStateStatus: DIRTY` (base
advanced, merge conflicts). Claude: [runs §Convergence gate (c); does NOT
mark ready; invokes `rebase` skill per `../../rebase/SKILL.md` Phase 1–4;
after force-with-lease push, resets `bugbot_clean_at = null`,
`copilot_clean_at = null`, `merge_state_status = null`, `phase = BUGBOT`,
posts `bugbot run` on new HEAD, schedules next wakeup]
</example>

<example> Back-to-back clean, mergeability CLEAN, Copilot review at
`current_head` `state == "CHANGES_REQUESTED"` with two unaddressed inline
findings. Claude: [runs §Convergence gates (a); applies Fix protocol (TDD
test → fix → push → reply inline both threads), resets `bugbot_clean_at`
and `copilot_clean_at` null, `phase = BUGBOT`, posts `bugbot run` on new
HEAD, schedules next wakeup]
</example>

<example> Back-to-back clean, mergeability CLEAN, no Copilot review on
`current_head`. Claude sets `phase = COPILOT_WAIT`, runs gate (d):
`request_copilot_review(owner=OWNER, repo=REPO, pullNumber=NUMBER)`,
schedules next wakeup, returns. Next tick:
Copilot review `state: APPROVED` at `current_head`. Claude: [re-runs
gate (a) fetch → APPROVED → sets `copilot_clean_at = current_head`,
records evidence: "Copilot APPROVED at <SHA>", sets `phase = BUGTEAM`;
re-validates gates (b) Claude absent and (c) mergeability clean,
records evidence for both; gate (e) zero unresolved threads passes
trivially, record evidence: "0 unresolved threads across PR at <SHA>";
runs `update_pull_request(pullNumber=NUMBER,
owner=OWNER, repo=REPO, draft=false)`; reports "PR #N converged: bugbot CLEAN
at <SHA>, bugteam CLEAN at <SHA>, mergeable_state clean, copilot CLEAN at
<SHA>, claude absent at <SHA>, 0 unresolved threads across PR; marked ready for review"]
</example>

<example> Back-to-back clean, mergeability CLEAN, post-convergence Copilot
review returned `state: CHANGES_REQUESTED` with inline findings on
`current_head`. Claude: [does NOT mark PR ready — gate (d) failed;
applies Fix protocol on every confirmed Copilot finding (TDD test → fix →
push → reply inline on each thread); resets `bugbot_clean_at = null` and
`copilot_clean_at = null`; `phase = BUGBOT`; posts `bugbot run` on new
HEAD; schedules next wakeup. Full back-to-back-clean cycle plus all six
gates must hold again on new HEAD.]
</example>
