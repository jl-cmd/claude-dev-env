# Examples

Worked examples for `pr-converge`. Read on demand when a tick's
classification is novel or ambiguous against the in-skill rules. Cross-refs
into `SKILL.md` use `§Section name` notation.

<example> User: `/pr-converge` Claude: [PR context + one tick of internal
code-review/bugteam work, then the terminal Bugbot and Copilot gates; Step 4
per `workflows/schedule-wakeup-loop.md` — default loop until convergence or
stop]
</example>

<example> CODE_REVIEW tick (the entry phase), the static sweep raises a
`ruff` failure on a changed file. Claude: [fixes it TDD, one commit, pushes,
resets `bugbot_clean_at = null`, `code_review_clean_at = null`,
`bugteam_clean_at = null`, `copilot_clean_at = null`, `merge_state_status =
null`, stays `phase = CODE_REVIEW`, Step 4 at 270s, re-runs the sweep next
tick]
</example>

<example> CODE_REVIEW tick, static sweep clean, `/code-review high --fix`
applies fixes to the working tree. Claude: [commits the applied fixes in one
commit, pushes, resets `bugbot_clean_at = null`, `code_review_clean_at =
null`, `bugteam_clean_at = null`, `copilot_clean_at = null`,
`merge_state_status = null`, stays `phase = CODE_REVIEW`, Step 4 at 270s,
returns]
</example>

<example> CODE_REVIEW tick, static sweep clean and `/code-review high --fix`
clean (no changes applied). Claude: [sets `code_review_clean_at = HEAD`,
`phase = BUGTEAM`, runs `Skill({skill: "bugteam", ...})` in same tick]
</example>

<example> BUGTEAM phase, bugteam pushed a fix commit during its run. Claude:
[re-resolves HEAD, resets `bugbot_clean_at = null`, `code_review_clean_at =
null`, `bugteam_clean_at = null`, `copilot_clean_at = null`,
`merge_state_status = null`, `phase = CODE_REVIEW`, Step 4 at 270s, re-enters
the internal passes on the new HEAD]
</example>

<example> BUGTEAM phase, bugteam reports convergence with no push. Claude:
[the internal passes are clean on `current_head`; `phase = BUGBOT` — routes into
the terminal Bugbot gate in the same tick]
</example>

<example> Terminal BUGBOT gate, Bugbot disabled for the run (the default).
Claude: [availability gate exits 0, sets `bugbot_down = true`, advances to the
`convergence-gates.md` gates with the Bugbot gate bypassed — no trigger, no
wait, no agent]
</example>

<example> Terminal BUGBOT gate, Bugbot enabled and clean on HEAD. Claude:
[sets `bugbot_clean_at = HEAD`, advances to the `convergence-gates.md` gates in
the same tick]
</example>

<example> Terminal BUGBOT gate, Bugbot has 2 unaddressed findings on HEAD.
Claude: [TDD-fixes both, one commit, pushes, replies inline on both threads,
resets `bugbot_clean_at = null`, `code_review_clean_at = null`,
`bugteam_clean_at = null`, `copilot_clean_at = null`, `merge_state_status =
null`, `phase = CODE_REVIEW`, Step 4 at 270s, re-enters the internal passes
on the new HEAD]
</example>

<example> Convergence gates after the terminal Bugbot gate confirms
(`bugbot_clean_at == current_head`). Claude: [runs `convergence-gates.md` gates
in order:
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
    APPROVED at <SHA>", re-validate gates (b) and (c).
  Gate (e): the `pr-fix-protocol` unresolved-thread sweep
    (`../../pr-fix-protocol/SKILL.md`) → zero across PR → record evidence.
  Gate (f): all six gates pass → `update_pull_request(pullNumber=NUMBER,
    owner=OWNER, repo=REPO, draft=false)`.
Reports "PR #N converged: bugbot CLEAN at <SHA>, bugteam CLEAN at <SHA>,
mergeable_state clean, copilot CLEAN at <SHA>, claude absent at <SHA>,
0 unresolved threads across PR; marked ready for review",
applies **Convergence** from `workflows/schedule-wakeup-loop.md`]
</example>

<example> CODE_REVIEW tick, review body says "found 3 potential issues"
against HEAD (a stale prior finding) but the diff is clean. Claude: [the static
sweep and `/code-review high --fix` both pass, sets `code_review_clean_at =
HEAD`, `phase = BUGTEAM`]
</example>

<example> Convergence gates reached, but `mergeStateStatus: DIRTY` (base
advanced, merge conflicts). Claude: [runs §Convergence gate (c); does NOT
mark ready; invokes `rebase` skill per `../../rebase/SKILL.md` Phase 1–4;
after force-with-lease push, resets `bugbot_clean_at = null`,
`code_review_clean_at = null`, `bugteam_clean_at = null`,
`copilot_clean_at = null`, `merge_state_status = null`, `phase =
CODE_REVIEW`, schedules next wakeup]
</example>

<example> Convergence gates reached, mergeability CLEAN, Copilot review at
`current_head` `state == "CHANGES_REQUESTED"` with two unaddressed inline
findings. Claude: [runs §Convergence gates (a); applies Fix protocol (TDD
test → fix → push → reply inline both threads), resets `bugbot_clean_at =
null`, `code_review_clean_at = null`, `bugteam_clean_at = null`,
`copilot_clean_at = null`, `merge_state_status = null`, `phase =
CODE_REVIEW`, schedules next wakeup, re-enters the internal passes on the
new HEAD]
</example>

<example> Convergence gates reached, mergeability CLEAN, no Copilot review on
`current_head`. Claude sets `phase = COPILOT_WAIT`, runs gate (d):
`request_copilot_review(owner=OWNER, repo=REPO, pullNumber=NUMBER)`,
schedules next wakeup, returns. Next tick:
Copilot review `state: APPROVED` at `current_head`. Claude: [re-runs
gate (a) fetch → APPROVED → sets `copilot_clean_at = current_head`,
records evidence: "Copilot APPROVED at <SHA>";
re-validates gates (b) Claude absent and (c) mergeability clean,
records evidence for both; gate (e) — the `pr-fix-protocol`
unresolved-thread sweep — passes trivially, record evidence:
"0 unresolved threads across PR at <SHA>";
runs `update_pull_request(pullNumber=NUMBER,
owner=OWNER, repo=REPO, draft=false)`; reports "PR #N converged: bugbot CLEAN
at <SHA>, bugteam CLEAN at <SHA>, mergeable_state clean, copilot CLEAN at
<SHA>, claude absent at <SHA>, 0 unresolved threads across PR; marked ready for review"]
</example>

<example> Convergence gates reached, mergeability CLEAN, post-convergence
Copilot review returned `state: CHANGES_REQUESTED` with inline findings on
`current_head`. Claude: [does NOT mark PR ready — gate (d) failed;
applies Fix protocol on every confirmed Copilot finding (TDD test → fix →
push → reply inline on each thread); resets `bugbot_clean_at = null`,
`code_review_clean_at = null`, `bugteam_clean_at = null`,
`copilot_clean_at = null`, `merge_state_status = null`; `phase =
CODE_REVIEW`; schedules next wakeup, re-enters the internal passes on the new
HEAD. Full back-to-back-clean cycle plus all six gates must hold again on new
HEAD.]
</example>
