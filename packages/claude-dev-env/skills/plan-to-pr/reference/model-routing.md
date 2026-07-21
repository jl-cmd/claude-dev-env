# Model Routing Contract

This reference fixes the model role for every stage of the Plan-to-PR workflow.
Unavailable models or unavailable model-selection tools fail closed.

## Role matrix

| Role | Required route | Required behavior |
|---|---|---|
| Planner | Luna xhigh with Sol xhigh advisor | Creates the source-grounded plan and acceptance contract; consults the warm advisor heavily at decisive planning points |
| Orchestrator | Max route | Assigns tickets, owns the ledger, delegates every work task, and reconciles results |
| Implementation worker | Fast, low-effort Luna | Changes only the ticket's allowed files and runs its acceptance check |
| Review worker | Fast, low-effort Luna | Invokes the native `/e-code-review low` correctness review against the committed diff and returns findings only |
| Repair worker | Fast, low-effort Luna | Applies only confirmed findings from the native correctness review |
| Final validator | Luna xhigh with Sol xhigh advisor | Maps commits to tasks and validates the cumulative release surface; consults the warm advisor heavily at decisive validation points |

## Routing gates

1. Bind the planner and final validator to Luna xhigh.
2. Bind the planner and final validator to a Sol xhigh advisor and consult it before routing decisions, task approval, repair plans, commit authorization, and final validation decisions.
3. Bind the orchestrator to the max route and require it to delegate work tasks.
4. Bind every implementation, review, and repair worker to fast, low-effort Luna.
5. Stop when a required tier, model, advisor, or routing tool is unavailable.
6. Do not promote workers, demote planners or validators, or substitute a role's route.

The orchestrator records the selected route and the final validator checks it
against this matrix. The native review is findings-only and has no repair flag.
The review record captures resolved model, effort, command, findings, repair status,
and surface hash. Missing native review or verifier capability fails closed.

After the PR is finalized and pushed, run `/e-simplify` with Luna xhigh for
cleanup-only fixes. Then run `/e-code-review max loop` with Luna low. A separate
Luna low repair worker applies confirmed findings, runs required checks, commits,
and pushes before the next loop. A clean max review is required; nits are fixed
and pushed before the next max review, while any non-nit finding blocks readiness.
