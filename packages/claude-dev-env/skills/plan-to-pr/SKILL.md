---
name: plan-to-pr
description: >-
  Coordinates source-grounded implementation through planned task tickets, fixed
  model routing, verified commits, independent Luna review, and publication gates.
  Triggers: "Plan-to-PR", "plan to PR", "implement this with one task per commit",
  "run the Plan-to-PR workflow", "validate Plan-to-PR", "publish the PR".
---

# Plan-to-PR

## Contents

- [When this applies](#when-this-applies)
- [Process classification](#process-classification)
- [Gotchas](#gotchas)
- [Capability boundary](#capability-boundary)
- [Refusal cases](#refusal-cases)
- [Runtime prerequisites](#runtime-prerequisites)
- [Task seeding](#task-seeding)
- [Peer-skill composition](#peer-skill-composition)
- [Model contract](#model-contract)
- [One-task and one-commit protocol](#one-task-and-one-commit-protocol)
- [Review and verification order](#review-and-verification-order)
- [Final validation and publication](#final-validation-and-publication)
- [Companion references](#companion-references)
- [File index](#file-index)
- [Folder map](#folder-map)

## When this applies

Use this skill for source-grounded implementation with an approved plan,
one deliverable per task, one allowed file set, one acceptance check, and one
commit. Refuse the first matching case under [Refusal cases](#refusal-cases).

## Process classification

This skill is an orchestrator/business-process workflow. It coordinates fixed
task, routing, review, verification, and publication decisions across peer
skills and deterministic validation scripts.

## Gotchas

- A passing acceptance check does not replace a commit, review, repair,
  reverification, or verifier record.
- Native review is findings-only. A separate fast low-effort Luna repair worker
  handles confirmed findings, followed by acceptance and exact-surface verification.
- Missing task tools, native review binding, or verifier capability fails closed.

## Runtime prerequisites

The validator uses Python 3 standard library only; no third-party packages are
required. Run `python scripts/validate_protocol.py <record.json>` from this
skill directory. Exit `0` means the record is valid; exit `2` means validation
failed and the concise reason is written to stderr.

## Capability boundary

This skill coordinates a multi-task implementation from an approved plan
through publication. It owns composition, task records, model routing, commit
order, verification order, and final release decisions. It does not replace the
peer skills that plan, orchestrate, or advise.

## Refusal cases

Refuse the first matching case and stop:

- No approved plan, task scope, or acceptance contract is available.
- A requested change spans files outside the plan's allowed file set.
- A task contains more than one deliverable, acceptance check, or commit.
- A required tool, peer skill, verifier, model tier, or review path is unavailable.
- The user asks to bypass verification, `verified_commit_gate`, independent review,
  final validation, or a publication gate.

Return exactly: `Plan-to-PR blocked: <missing input or capability>.`

## Task seeding

Read the approved plan and seed one host task for every planned deliverable before
implementation. Each task records exactly one deliverable, one allowed file set,
one acceptance check, and one commit. Register tasks with the host task tool
(`TaskCreate`, `TodoWrite`, or its equivalent), then mark each task complete only
with its verifier output and commit identity.

The standalone task record and its fixed fields live in
[`reference/task-ticket.md`](reference/task-ticket.md). The fixed routing and gate
matrix lives in [`reference/model-routing.md`](reference/model-routing.md). Fail
closed if either required reference is absent.

Seed the ordered catalog in [`reference/task-seeds.md`](reference/task-seeds.md)
before implementation. Seed [`reference/final-validation-tasks.md`](reference/final-validation-tasks.md)
before final validation and [`reference/self-audit-tasks.md`](reference/self-audit-tasks.md)
before self-audit. If no host task tool exists, stop and report the blocker.

## Peer-skill composition

Use these three named peer skills. Invoke them at the stated point, record their
produced artifact, and stop when the skill is missing.

| Peer skill | When to invoke | Produces | Missing behavior |
|---|---|---|---|
| `anthropic-plan` | Before any implementation, when the request needs a source-grounded plan | Approved `docs/plans/<slug>/` packet and acceptance contract | Refuse implementation and report that planning is unavailable |
| `orchestrator` | After approval, when multiple tasks need delegated execution and ledger control | Run charter, task ledger, assignment records, and reconciled results | Refuse execution and report that orchestration is unavailable |
| `team-advisor` | Before hard decisions, task completion, commits, or when blocked | A reachable high-tier advisor decision using the shared advisor protocol | Refuse the gated decision; do not answer for the advisor |

Do not reproduce the peers' fixed tables or workflows here. Follow the companion
references and the installed peer skill contracts instead.

## Model contract

The planner and final validator use Luna xhigh and consult a Sol xhigh advisor
heavily at decisive points. The orchestrator uses the max route and
delegates every work task to fast, low-effort Luna workers. Every implementation,
review, and repair worker uses fast, low-effort Luna. The exact model names, floor
rules, advisor cadence, and fallback behavior are defined only in
[`reference/model-routing.md`](reference/model-routing.md).

Unavailable models fail closed. Never silently promote a worker, demote a planner,
reuse a review worker as the final validator, or continue with an unverified route.

The planner creates the approved plan. The orchestrator owns task assignment,
ledger state, and result reconciliation. Workers change only their ticket's files
and run its acceptance check. Reviewers inspect the committed task surface and
repair only verified findings. The final validator checks the complete history and
publication gates.

## One-task and one-commit protocol

For each seeded task:

1. The orchestrator issues the standalone task ticket.
2. One worker implements one deliverable within the ticket's allowed file set.
3. The worker runs the one acceptance check and reports exact output and blockers.
4. A fresh verifier checks the task diff, baseline, named gates, and ticket-to-diff
   scope. It must pass `verified_commit_gate` for the exact surface.
5. The orchestrator creates exactly one commit for the task and records its hash.

No task may borrow files, acceptance checks, or commit history from another task.
Unrelated changes remain untouched and uncommitted.

## Review and verification order

Before every commit, require fresh verification and `verified_commit_gate` against
the exact task surface. A passing test alone is not a commit authorization.

After the commit, a separate fast low-effort Luna review worker invokes the
native low-effort correctness review capability at `/e-code-review low`. The
review reads the committed diff and returns findings only; it has no repair
flag. Fail closed if the native review or required verifier is unavailable.

A separate fast low-effort Luna repair worker applies only confirmed findings.
Record the resolved model, effort, command, findings, repair status, and
surface hash. After repairs, rerun the task acceptance check and fresh
exact-surface verification, amend the task commit, and repeat the native review
until clean.
Do not let the implementer self-review or let the final validator stand in for
this independent pass.

## Final validation and publication

The final validator examines every commit in order and maps each commit to one
planned task. It validates cumulative behavior, the complete allowed-file ledger,
all acceptance checks, fresh verifier output, `verified_commit_gate` evidence, and
the post-commit review records. Any unmapped commit, missing record, failed gate,
or unresolved finding blocks publication.

Run the workflow self-audit and retain its evidence. Confirm all required
references, peer skills, tools, and model routes are available. Publish only when
the final validator and self-audit both pass; otherwise report the exact blocker
and stop without publishing.

## Post-PR cleanup and max review

After the PR branch is finalized and pushed, run a Luna xhigh `/e-simplify` pass.
Apply its validated cleanup fixes directly, then commit and push those changes.
This pass is cleanup-only and does not replace correctness review.

Next, run a Luna low `/e-code-review max loop` pass. The review returns findings;
a separate Luna low repair worker applies confirmed bugs or nits. Run the required
checks, commit, and push every repair, then repeat the max loop. Finish only when
the review is clean; nits must be fixed and pushed before the next loop, and any
non-nit finding blocks publication until repaired. Do not add a repair flag to
the review command.

## Companion references

- [`reference/model-routing.md`](reference/model-routing.md) — fixed model and gate matrix.
- [`reference/task-ticket.md`](reference/task-ticket.md) — standalone task, commit,
  and review record contract.
- [`reference/review-loop.md`](reference/review-loop.md) — native review and repair loop.
- [`reference/process-inventory.md`](reference/process-inventory.md) — process classification and evidence homes.

The hub names these contracts without reimplementing their fixed tables.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Hub, routing, gates, and direct reference index |
| `reference/model-routing.md` | Model roles and route gates |
| `reference/task-ticket.md` | Human-readable task-ticket contract |
| [`reference/run-record.schema.json`](reference/run-record.schema.json) | Machine-checkable task-run record |
| `scripts/validate_protocol.py` | Deterministic task-run record validator |
| `reference/review-loop.md` | Native review and repair loop |
| `reference/process-inventory.md` | Process classification and evidence homes |
| `reference/task-seeds.md` | Ordered implementation task catalog |
| `reference/final-validation-tasks.md` | Final-validation task seeds |
| `reference/self-audit-tasks.md` | Workflow self-audit task seeds |
| `test_skill_contract.py` | Hub and routing contract tests |
| `test_task_ticket_contract.py` | Task-record and reference contract tests |
| `scripts/test_validate_protocol.py` | CLI validation tests |
| `scripts/validate_run.py` | Deterministic set-level task-record validator |
| `scripts/test_validate_run.py` | Set-level validator tests |
| `scripts/config/__init__.py` | Validator configuration package marker |
| `scripts/config/constants.py` | Validator constants |

Run [`scripts/validate_protocol.py`](scripts/validate_protocol.py) with a completed
task-run record before final validation. Exit `0` means the host-neutral
contract and evidence are valid. Exit `2` means validation failed; the concise
reason is printed to stderr.

Run [`scripts/validate_run.py`](scripts/validate_run.py) with a JSON list of
task-run records and either `--base-head BASE..HEAD` or `--commits HASH[,HASH]`
to validate the complete task-record set against its commit set. Add
`--worktree PATH` when the commit set belongs to another worktree.

## Folder map

- `reference/` — fixed contracts, catalogs, inventories, and task seeds.
- `scripts/` — deterministic validator and its tests.
- `scripts/config/` — validator configuration package and constants.
- `SKILL.md` — the one-level workflow hub.
