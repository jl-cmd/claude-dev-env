# Review Loop

Run this loop for every committed task. Store each pass in the task record.

1. A separate fast low-effort Luna review worker reads the committed task diff.
2. It invokes the active host's native findings-only correctness capability. The
   Codex binding is `/e-code-review low`; the review has no repair flag.
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
