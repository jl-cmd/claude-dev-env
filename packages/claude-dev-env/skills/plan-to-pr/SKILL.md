---
name: plan-to-pr
description: >-
  Coordinates source-grounded implementation through a validated plan packet,
  planned task tickets, fixed model routing, verified commits, independent Luna
  review, and publication gates. Triggers: "Plan-to-PR", "plan to PR",
  "implement this with one task per commit", "run the Plan-to-PR workflow",
  "validate Plan-to-PR", "publish the PR".
---

# Plan-to-PR

## Purpose and boundary

Use this skill for source-grounded implementation with one deliverable, one
allowed file set, one acceptance check, and one commit per task. The planning
phase creates and validates a tool-neutral `docs/plans/<slug>/` packet
before any `TaskCreate` or `TodoWrite` seeding.

The skill coordinates planning, task records, model routing, commit order,
review, verification, and publication. It does not replace the orchestrator or
advisor capabilities used by later phases.

## Native planning phase

Run this phase before task seeding and before implementation:

1. The Luna max planner reads the request, repository guidance, relevant
   source, tests, and documentation, then selects a unique lowercase slug.
2. The planner consults a Sol xhigh advisor heavily at scope, dependency,
   task-boundary, acceptance, and risk decisions. The advisor supports planning
   decisions and packet review.
3. The planner writes the packet files and validates them against
   [`reference/packet-contract.md`](reference/packet-contract.md) and
   [`reference/packet-schema.json`](reference/packet-schema.json).
4. The planner repairs packet findings and repeats deterministic validation
   until the packet passes. A failed validation blocks task seeding.
5. Only a passing packet with `status: approved` may seed host tasks. Record the
   packet path and validation result in the task ledger.

The packet is the sole planning handoff. It contains its own scope, evidence,
task boundaries, acceptance checks, risks, and implementation order. Do not
seed tasks from conversational notes or an incomplete packet.

## Capability boundary

This skill owns the native planning packet, task records, routing, review,
verification, and publication decisions. Later execution uses the companion
orchestrator and advisor capabilities.

## Refusal cases

Refuse the first matching case and stop:

- The request has no source-grounded plan packet.
- The packet is missing, invalid, outside `docs/plans/<slug>/`, or not approved.
- A requested change spans files outside the packet's allowed file set.
- A task contains more than one deliverable, acceptance check, or commit.
- A required task tool, verifier, model tier, advisor, review path, or gate is unavailable.
- The user asks to bypass verification, `verified_commit_gate`, independent
  review, final validation, or a publication gate.

Return exactly: `Plan-to-PR blocked: <missing input or capability>.`

## Runtime and task seeding

The packet and task-run validators use Python 3 standard library only. From this
skill directory, create a packet skeleton with:

`python scripts/create_packet.py --repo-root <repository> --slug <slug> --base-ref <base-ref>`

After the planner fills the packet, validate it with:

`python scripts/validate_packet.py <repository>/docs/plans/<slug>`

Run `python scripts/validate_protocol.py <record.json>` for each task record;
exit `0` means valid and exit `2` means invalid.

After packet approval, seed one host task for every packet task with
`TaskCreate`, `TodoWrite`, or its equivalent. Each task records exactly one
deliverable, one allowed file set, one acceptance check, and one commit. Mark a
task complete only with verifier output and its commit identity. Use the fixed
contracts in `reference/task-ticket.md`, `reference/model-routing.md`,
`reference/task-seeds.md`, `reference/final-validation-tasks.md`, and
`reference/self-audit-tasks.md`. The fixed fields live in those references.

## Model contract

The planner and final validator use Luna max with Sol xhigh advisory heavily
at decisive points. The orchestrator uses the max route and delegates every work
task. Every implementation,
review, and repair worker uses fast, low-effort Luna. Unavailable models or routing tools
fail closed; never promote workers,
demote planners or validators, or substitute a role route.

The planner owns the approved packet. The orchestrator owns task assignment,
ledger state, and result reconciliation. Workers change only their ticket's
files and run its acceptance check. The final validator checks the complete
history and publication gates.

## One-task and one-commit protocol

For each seeded task:

1. The orchestrator issues the standalone task ticket.
2. One worker implements one deliverable within the ticket's allowed files.
3. The worker runs the one acceptance check and reports exact output and blockers.
4. A fresh verifier checks the task diff, baseline, named gates, and ticket-to-diff
   scope. It must pass `verified_commit_gate` for the exact surface.
5. The orchestrator creates exactly one commit and records its hash.

No task borrows files, acceptance checks, or commit history from another task.
Unrelated changes remain untouched and uncommitted.

## Review and repair

Before every commit, require fresh verification and `verified_commit_gate`.
After the commit, a separate fast low-effort Luna review worker runs native
findings-only correctness review at `/e-code-review low`. The review returns
findings only and has no repair flag.

A separate fast low-effort Luna repair worker applies only confirmed findings.
Record resolved model, effort, command, findings, repair status, and surface
hash. Rerun the task acceptance check and fresh exact-surface verification, amend the task commit,
and repeat native review until clean. The max review is the correctness
gate after cleanup.

## Final validation and publication

The Luna max final validator maps every commit to one packet task and checks
cumulative behavior, the allowed-file ledger, acceptance checks, verifier
output, `verified_commit_gate` evidence, and post-commit review records. Any
unmapped commit, missing record, failed gate, or unresolved finding blocks
publication.

Run the workflow self-audit and retain its evidence. Publish only when final validation
and self-audit pass. After the branch is finalized and pushed, run Luna max `/e-simplify`
for cleanup-only fixes, then Luna low `/e-code-review max loop` with a separate
Luna low repair worker. commit, and push every validated repair;
finish only when the max review is clean.

## Companion references

- [`reference/packet-contract.md`](reference/packet-contract.md) — native planning packet contract.
- [`reference/packet-schema.json`](reference/packet-schema.json) — machine-readable packet schema.
- [`scripts/create_packet.py`](scripts/create_packet.py) — deterministic packet skeleton creator.
- [`scripts/validate_packet.py`](scripts/validate_packet.py) — deterministic packet validator.
- [`reference/model-routing.md`](reference/model-routing.md) — fixed model and gate matrix.
- [`reference/task-ticket.md`](reference/task-ticket.md) — task, commit, and review record contract.
- [`reference/review-loop.md`](reference/review-loop.md) — review and repair loop.
- [`reference/process-inventory.md`](reference/process-inventory.md) — evidence homes.
- [`reference/run-record.schema.json`](reference/run-record.schema.json) — machine-checkable task-run record.

Run `scripts/validate_run.py` with the task records and commit set during final
validation. Add `--worktree PATH` when the commit set belongs to another tree.
