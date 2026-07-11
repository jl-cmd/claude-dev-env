---
name: copilot-finding-triage
description: >-
  Sorts each Copilot gate finding from a converge run into one of two tiers and
  routes it: a self-healing finding is auto-fixed, pushed, and counted toward
  convergence with no user page, while a code concern pages the user over ntfy
  and holds the run behind a 45-minute gate. Triggers: 'copilot finding triage',
  'user review gate', 'tier copilot findings', 'triage the copilot gate'.
---

# Copilot Finding Triage

After a converge run's Copilot gate returns its findings, this skill sorts each
one into a tier and acts on it. Findings scoped to style, type hints, or tests
heal themselves inside the run. A logic, security, or behavior finding pages the user
and holds the run until they answer or a 45-minute deadline passes.

## When this applies

Reach for this skill when a Copilot review on the round's HEAD returns findings
inside one of these callers:

- `autoconverge` — the single-run converge workflow, at its Copilot wait-gate.
- `pr-converge` — the looping converge workflow, at each Copilot tick.
- `copilot-review` — the standalone Copilot babysitter.

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

A finding that straddles both tiers sorts to CODE CONCERN. Any doubt routes to
the user gate.

## Self-healing flow

A self-healing finding never pages the user.

1. Fix the finding through the caller's existing fix flow.
2. Verify the fix.
3. Commit and push on the caller's branch.
4. Count the round toward convergence.

## User gate protocol

Run this protocol when one or more CODE CONCERN findings sit on the round's HEAD.

### Step 1 — Page the user

Run `scripts/notify_ntfy.py` with:

- `--title` naming the PR.
- `--message` summarizing each code-concern finding, one line each, as
  `file:line — severity — one sentence`. Build the body from
  `templates/notification.md`.
- `--click-url` set to the Copilot review URL, so tapping the page opens the
  review.

The topic reads from the `NTFY_TOPIC` environment variable, and the server
reads from `NTFY_SERVER` with a default of `https://ntfy.sh`. A missing topic
fails loudly with a clear message. A failed page holds the gate open; it never
counts as approval.

### Step 2 — Hold and wait

Arm `ScheduleWakeup` for a 45-minute deadline. Where `ScheduleWakeup` is absent,
use `send_later`. The clock starts when the page reaches the user, which is the
moment the script exits zero.

- If the user answers, follow their direction.
- If the deadline passes with no answer, run the caller's normal teardown and
  report the un-reviewed findings in the final report.

### Step 3 — Self-healing findings run in parallel

Self-healing findings on the same HEAD do not wait for the gate. Fix, verify,
commit, and push them through the caller's fix flow, and count the round toward
convergence.

## Gate checklist

- [ ] Every finding on HEAD carries a tier.
- [ ] Each self-healing finding is fixed, verified, and pushed.
- [ ] Each code-concern finding appears as one line in the ntfy body.
- [ ] The page carries the PR name, the per-finding summary, and the review URL.
- [ ] `scripts/notify_ntfy.py` exited zero before the 45-minute clock started.
- [ ] The wakeup is armed for 45 minutes from a delivered page.
- [ ] A failed page kept the gate open rather than approving the round.

## Files

| Path | Role |
|------|------|
| `SKILL.md` | This hub: when it applies, the tier split, the gate protocol. |
| `reference/tier-rubric.md` | The complete tier rubric and the behavior-safe test. |
| `templates/notification.md` | The ntfy message body for a code-concern page. |
| `scripts/notify_ntfy.py` | The ntfy publish CLI. |
| `scripts/test_notify_ntfy.py` | Tests for the publish CLI. |

## Gotchas

- **A cloud MCP session refuses APPROVE reviews.** Any review this protocol posts
  is event COMMENT. A cloud session cannot post an APPROVE event, so route
  approvals through the user, never through a posted review.
- **A failed page is not consent.** A failed ntfy POST holds the gate open. It
  does not auto-approve the round. Read the script's non-zero exit as a page that
  never reached the user, and keep the run held.
- **Doubt sorts to CODE CONCERN.** When a finding could sit in either tier,
  classify it as a code concern and page the user. The safe default never
  auto-fixes a finding that might change runtime behavior.
- **The 45-minute clock starts at page success.** The timer starts when the page
  reaches the user, which is the moment `scripts/notify_ntfy.py` exits zero, not
  the moment the finding is classified.
