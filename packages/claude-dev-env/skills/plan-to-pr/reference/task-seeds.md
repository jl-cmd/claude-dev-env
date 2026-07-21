# Task Seeds

Register each item as one host task with `TaskCreate`, `TodoWrite`, or the host
equivalent before implementation. Mark it complete only with evidence.

1. Approve the plan, task scope, acceptance check, and allowed files.
2. Capture the baseline and create one task record from the run-record schema.
3. Implement the single deliverable within the allowed file set.
4. Run the acceptance check and record its exact output.
5. Run fresh exact-surface verification and `verified_commit_gate`.
6. Create exactly one task commit and record its identity.
7. Run the separate native review and record findings-only output.
8. Run separate Luna repair only for confirmed findings; rerun acceptance and
   exact-surface verification before amending and reviewing again.
