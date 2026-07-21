# Model Routing Contract

This reference fixes the model role for every stage of the skill protocol.
Unavailable models or unavailable model-selection tools fail closed.

## Role matrix

| Role | Required route | Required behavior |
|---|---|---|
| Planner | Strongest reachable high-level tier | Creates the source-grounded plan and acceptance contract |
| Orchestrator | Fixed mid-level tier | Assigns tickets, owns the ledger, and reconciles results |
| Implementation worker | Fast, low-effort Luna | Changes only the ticket's allowed files and runs its acceptance check |
| Review worker | Fast, low-effort Luna | Invokes the active host's native correctness review capability; Codex binds that capability to `/e-code-review low` against the committed diff and returns findings only |
| Repair worker | Fast, low-effort Luna | Applies only confirmed findings from the native correctness review |
| Final validator | Same high-level tier as the planner | Maps commits to tasks and validates the cumulative release surface |

## Routing gates

1. Bind the planner and final validator to the same high-level tier.
2. Bind the orchestrator to the fixed mid-level tier.
3. Bind every implementation, review, and repair worker to fast, low-effort Luna.
4. Stop when a required tier, model, or routing tool is unavailable.
5. Do not promote workers, demote validators, or substitute a role's route.

The orchestrator records the selected route and the final validator checks it
against this matrix. The native review is findings-only and has no repair flag.
The review record captures resolved model, effort, command, findings, repair status,
and surface hash. Missing native review or verifier capability fails closed.
