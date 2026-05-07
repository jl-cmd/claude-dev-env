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
`bugbot_clean_at = HEAD`, `phase = BUGTEAM`, runs `Skill({skill: "bugteam",
...})` in same tick]
</example>

<example> BUGTEAM phase, bugteam reports convergence and `bugbot_clean_at
== current_head`. Claude: [runs `update_pull_request(pullNumber=NUMBER, owner=OWNER, repo=REPO, draft=false)`, reports "PR
converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>; marked ready for
review", applies **Convergence** from `workflows/schedule-wakeup-loop.md`]
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
advanced, merge conflicts). Claude: [runs §Convergence gates (b); does NOT
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
`current_head`. Claude requests Copilot via `add_issue_comment(owner=OWNER, repo=REPO, issueNumber=NUMBER, body="@copilot review")`,
waits one tick. Next tick: Copilot review `state: APPROVED`. Claude: [sets
`copilot_clean_at = current_head`; runs `update_pull_request(pullNumber=NUMBER, owner=OWNER, repo=REPO, draft=false)`; reports "PR
#N converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>,
mergeable_state clean, copilot CLEAN; marked ready for review"]
</example>

<example> Back-to-back clean, mergeability CLEAN, post-convergence Copilot
review returned `state: CHANGES_REQUESTED` with inline findings on
`current_head`. Claude: [does NOT mark PR ready — gate (4) failed;
applies Fix protocol on every confirmed Copilot finding (TDD test → fix →
push → reply inline on each thread); resets `bugbot_clean_at = null` and
`copilot_clean_at = null`; `phase = BUGBOT`; posts `bugbot run` on new
HEAD; schedules next wakeup. Full back-to-back-clean cycle plus all four
gates must hold again on new HEAD.]
</example>
