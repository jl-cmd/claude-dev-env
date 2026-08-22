---
name: copilot-finding-triage
description: >-
  Tiers each Copilot gate finding from a converge run, verifies each code concern
  with an executed check, then routes it — auto-fix a self-healing finding,
  resolve a refuted one, page the user only for an inconclusive one. Triggers:
  'copilot finding triage', 'user review gate', 'tier copilot findings', 'triage
  the copilot gate'.
---

# Copilot Finding Triage

After a converge run's Copilot gate returns its findings, this skill tiers each
one, verifies every code concern with an executed check, then acts on it.
Findings scoped to style, type hints, or tests heal themselves inside the run. A
logic, security, or behavior finding goes to a verifier that runs a check against
HEAD: a confirmed defect joins the fix round carrying its repro, a refuted claim
is answered on the thread with the check evidence, and only a finding the check
leaves inconclusive pages the user and holds the run until they answer or a
45-minute deadline passes.

## When this applies

Reach for this skill when a Copilot review on the round's HEAD returns findings
inside one of these callers:

- `autoconverge` — the single-run converge workflow, at its Copilot wait-gate.
- `pr-converge` — the looping converge workflow, at each Copilot tick.

Each caller already fetches the review and carries a fix-and-push flow. This
skill decides, per finding, whether that flow runs on its own or waits behind
the user gate.

## The tier split

Read the complete rubric in `reference/tier-rubric.md`. The short form:

- **SELF-HEALING** — the fix cannot change what a production caller sees at
  runtime. Style, type hints, misplaced or unused imports, magic-value
  extraction, reshapes limited to tests, doc-versus-code mismatches, and
  de-duplication.
- **CODE CONCERN** — the fix changes observable production behavior or needs a
  product decision. Logic or correctness defects, security, data handling,
  error-handling semantics, and concurrency.

A finding that straddles both tiers sorts to CODE CONCERN. Any doubt about the
tier sorts the finding to CODE CONCERN.

## The verification stage

Tiering names who might act; the verification stage between tiering and the user
gate settles it for every code concern. Each code-concern finding goes to its own
verifier agent, all in parallel, inside the run. The verifier runs a check
against the flagged HEAD and returns one of three verdicts.

**The governing rule: a verdict is conclusive only if an actual check was
executed.** Reading the source and reasoning about it, however sound, never
produces a conclusive verdict. A check is a concrete command the verifier runs
against the flagged HEAD — executing the code path with crafted inputs, forcing
the claimed error condition, or running a purpose-built test — whose captured
output demonstrates the behavior in question. Each verdict carries
`{verdict, checkCommand, checkOutput, evidence}`; a conclusive verdict whose
`checkCommand` or `checkOutput` is empty carries no executed check, so the run
downgrades it to inconclusive.

- **CONFIRMED** — the check reproduces the defect. The finding becomes
  self-healing: it joins the fix round carrying its repro. The fix re-runs the
  same repro check and shows it passes, adds the repro to the test suite as a
  regression test where the suite covers that surface, lands in one commit and
  pushes, replies to the thread with the fix SHA plus the before/after check
  output, and resolves the thread. No page.
- **REFUTED** — the check shows the code already behaves correctly in the exact
  scenario the finding claims is broken. The run replies to the thread with the
  command(s) and captured output, resolves the thread, and counts the finding
  clean. No page.
- **INCONCLUSIVE** — everything else: no runnable check exists, the check is
  infeasible in this environment, the results are ambiguous, or the fix needs a
  product decision between defensible behaviors. The verifier defaults to
  inconclusive, and any doubt sorts here. These findings, and only these, flow
  into the user gate.

A run with zero inconclusive findings never reaches the user gate.

## Self-healing flow

A self-healing finding never pages the user. This covers a finding tiered
self-healing and a code concern the verifier confirmed.

1. Fix the finding through the caller's existing fix flow.
2. Verify the fix.
3. Commit and push on the caller's branch.
4. Count the round toward convergence.

## User gate protocol

Run this protocol when one or more code-concern findings stayed inconclusive
after verification on the round's HEAD.

### Step 1 — Page the user

Run `scripts/notify_ntfy.py` with:

- `--title` naming the PR.
- `--message` summarizing each inconclusive finding, one line each, as
  `file:line — severity — one sentence`, followed by the verifier's one-line
  evidence note stating what check was attempted and why it was not decisive.
  Build the body from `templates/notification.md`.
- `--click-url` set to the Copilot review URL, so tapping the page opens the
  review.

The topic reads from the `NTFY_TOPIC` environment variable, and the server
reads from `NTFY_SERVER` with a default of `https://ntfy.sh`. A missing topic
fails loudly with a clear message. A failed page holds the gate open; it never
counts as approval.

### Step 2 — Hold and wait

Branch the hold on the caller's pacer (or on whether a durable wake surface is
present when the caller has not selected a pacer):

- **Native pacer** (`pacer=schedule_wakeup`, `pacer=workflow`, or
  `ScheduleWakeup` present): arm `ScheduleWakeup` for a 45-minute deadline.
  Where `ScheduleWakeup` is absent on that native path, use `send_later`.
- **Portable pacer** (`pacer=portable`, or no durable wake): do not call
  `ScheduleWakeup` or `send_later`. Hold with an in-session deadline poll, or
  write handoff and stop, per
  [`../_shared/pr-loop/portable-driver.md`](../_shared/pr-loop/portable-driver.md).
  Callers may override this step after the ntfy page and apply their own
  portable hold.

The clock starts when the page reaches the user, which is the moment the script
exits zero.

- If the user answers, follow their direction.
- If the deadline passes with no answer, run the caller's normal teardown and
  report the un-reviewed findings in the final report.

### Step 3 — Self-healing and confirmed findings run in parallel

Self-healing findings and confirmed code concerns on the same HEAD do not wait
for the gate. Fix, verify, commit, and push them through the caller's fix flow,
and count the round toward convergence. A confirmed finding carries its repro, so
its fix re-runs that same check and posts the before/after output on the thread.

## Gate checklist

- [ ] Every finding on HEAD carries a tier.
- [ ] Each self-healing finding is fixed, verified, and pushed.
- [ ] Each code-concern finding carries a verifier verdict from an executed check.
- [ ] Each confirmed finding is fixed with its repro re-run and pushed.
- [ ] Each refuted finding's thread carries the check evidence and is resolved.
- [ ] Each inconclusive finding appears as one line in the ntfy body with its
      evidence note.
- [ ] The page carries the PR name, the per-finding summary, and the review URL.
- [ ] `scripts/notify_ntfy.py` exited zero before the 45-minute clock started.
- [ ] The hold is armed from a delivered page (45-minute `ScheduleWakeup` / `send_later` on native pacer; portable in-session poll or handoff on `pacer=portable`).
- [ ] A failed page kept the gate open rather than approving the round.

## Files

| Path | Role |
|------|------|
| `SKILL.md` | This hub: when it applies, the tier split, the verification stage, the gate protocol. |
| `reference/tier-rubric.md` | The complete tier rubric, the three verdicts, and the executed-check standard. |
| `templates/notification.md` | The ntfy message body for an inconclusive-finding page. |
| `scripts/notify_ntfy.py` | The ntfy publish CLI. |
| `scripts/test_notify_ntfy.py` | Tests for the publish CLI. |

## Gotchas

- **A cloud MCP session refuses APPROVE reviews.** Any review this protocol posts
  is event COMMENT. A cloud session cannot post an APPROVE event, so route
  approvals through the user, never through a posted review.
- **A failed page is not consent.** A failed ntfy POST holds the gate open. It
  does not auto-approve the round. Read the script's non-zero exit as a page that
  never reached the user, and keep the run held.
- **A conclusive verdict needs an executed check.** Source reading, however
  sound, never confirms or refutes a finding. A confirmed or refuted verdict
  whose `checkCommand` or `checkOutput` is empty downgrades to inconclusive and
  pages the user.
- **Doubt sorts to INCONCLUSIVE.** When an executed check does not pin down the
  behavior, the verifier defaults to inconclusive and the finding pages the user.
  The safe default never auto-fixes a finding whose behavior a check did not show.
- **The 45-minute clock starts at page success.** The timer starts when the page
  reaches the user, which is the moment `scripts/notify_ntfy.py` exits zero, not
  the moment the finding is classified.
