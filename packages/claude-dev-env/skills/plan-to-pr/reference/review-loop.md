# Review Loop

Run this loop for every committed task. Store each pass in the task record.

1. A separate fast low-effort Luna review worker reads the committed task diff.
2. It invokes the native findings-only `/e-code-review low` correctness
   capability; the review has no repair flag.
3. Record resolved model, effort, command, findings, repair status, and surface
   hash. Missing native review or verifier capability fails closed.
4. A separate fast low-effort Luna repair worker applies only confirmed findings.
5. Rerun the task acceptance check and fresh exact-surface verification.
6. Amend the task commit and repeat the native review until clean.

## Accepted records

Clean means the native review reports no findings for the exact committed
surface. A repaired pass is not accepted until acceptance and fresh verifier
output are recorded against the amended commit.

## Example

`review: findings=["missing field"]` → `repair: confirmed=["missing field"]` →
`acceptance: PASS` → `verification: PASS` → `amend` → `review: clean`.

## Post-PR max loop

After the PR branch is finalized and pushed, Luna max runs `/e-simplify` and
applies only cleanup fixes. Commit and push those fixes before correctness review.

Then Luna low invokes `/e-code-review max loop`. It returns findings only. A
separate Luna low repair worker applies confirmed bugs or nits, runs required
checks, commits, and pushes. Repeat the max loop until it is clean. Fix and push
all nits before the next loop; any non-nit finding blocks readiness until repaired.
