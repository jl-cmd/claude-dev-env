# Copilot findings — tier, verify, then route

How the autoconverge Copilot gate handles each finding. The hub
([`../SKILL.md`](../SKILL.md)) points here; the orchestrating session's
user-review hold runs the [`copilot-finding-triage`](../../copilot-finding-triage/SKILL.md)
skill.

The Copilot gate tiers each finding: a **self-healing** finding (style, type
hints, imports, formatting, magic-value extraction, test-only or doc-vs-code
fixes — nothing that changes observable runtime behavior) flows into the fix
round with no user notification. A **code-concern** finding (logic, security,
data handling, error-handling semantics, concurrency — the tier whenever in
doubt) goes to a verification stage before any routing.

Each code-concern finding gets its own verifier agent, all in parallel, inside
the workflow. A verdict is conclusive only when an actual check ran: the verifier
executes a command against the flagged HEAD — running the code path with crafted
inputs, forcing the claimed error condition, or running a purpose-built test —
and captures its output. The verdict carries
`{ verdict, checkCommand, checkOutput, evidence }`; a conclusive verdict with an
empty `checkCommand` or `checkOutput` downgrades to inconclusive.

- **confirmed** — the check reproduces the defect. The finding becomes
  self-healing: it joins the fix round carrying its repro, and the fix re-runs
  that same check, adds a regression test where the suite covers the surface,
  lands in one commit, pushes, and replies on the thread with the fix SHA and the
  before/after output. No page.
- **refuted** — the check shows the code already behaves correctly in the exact
  scenario the finding claims is broken. The workflow replies on the thread with
  the command and output, resolves it, and counts it clean. No page.
- **inconclusive** — everything else, and the verifier's default: no runnable
  check exists, the check is infeasible here, the results are ambiguous, or the
  fix needs a product decision. Any doubt sorts here. Only inconclusive findings
  page the user.

A round whose code concerns all confirm or refute never returns
`blocker: "user-review"`. On one or more inconclusive findings, the workflow
stops with `converged: false`, `blocker: "user-review"`, and a `userReview`
field carrying
`{ reviewUrl, findings: [{ file, line, severity, tier, title, evidence }] }` —
`evidence` is the verifier's one-line note stating what check was attempted and
why it was not decisive.

A background workflow cannot hold for a human, so the wait belongs to the
orchestrating session. On a `blocker: "user-review"` return, run the
[`copilot-finding-triage`](../../copilot-finding-triage/SKILL.md) skill: send the
ntfy notification (the per-finding summary and evidence note plus the `reviewUrl`
Copilot review link), then hold with a 45-minute `ScheduleWakeup` for the user's
response. When the user answers within the window, follow their direction. When
the window closes with no response, run normal teardown and report the
inconclusive findings un-reviewed.
