# Task Ticket Contract

Each ticket is created from an approved native plan packet after packet validation
passes. It describes one independently verifiable deliverable. The orchestrator
must reject a ticket that combines deliverables, file sets, acceptance checks, or
commits.

## Required ticket fields

| Field | Contract |
|---|---|
| Task identity | One stable task name and one planned task mapping |
| Deliverable | Exactly one concrete output |
| Allowed files | The complete file set the worker may change |
| Acceptance check | Exactly one command or deterministic check |
| Baseline | Fresh output captured before implementation |
| Worker route | The model role and selected route from `reference/model-routing.md`; planner and final-validator records include Luna max plus Sol xhigh advisor evidence, and orchestrator records the max route |
| Commit record | Exactly one commit hash for this ticket |
| Review record | Separate fast low-effort Luna review output that invokes native `/e-code-review low` and returns findings only, followed by separate fast low-effort Luna repair output, including resolved model, effort, command, findings, repair status, and surface hash |
| Verification record | Fresh verifier output and `verified_commit_gate` result for the exact surface |

## Execution contract

The worker changes only the allowed files, runs the acceptance check, and reports
the exact output. A fresh verifier checks the ticket against the diff before one
commit is created. The commit hash is recorded before the separate review pass.

## Review and completion contract

A separate fast low-effort Luna review worker invokes native `/e-code-review low`
after the commit. It reads the committed diff, returns findings only, and has no
repair flag. A separate fast low-effort Luna repair worker applies only confirmed findings. The record names
the resolved model, effort, command, findings, repair status, and surface hash.
Confirmed repairs require the acceptance check and fresh exact-surface verification
again; amend the task commit and repeat the native review until clean. Missing
native review or required verifier capability fails closed. The
final validator maps the commit to this ticket and rejects missing or extra
records.
