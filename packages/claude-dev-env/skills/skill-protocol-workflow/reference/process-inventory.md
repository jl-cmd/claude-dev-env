# Process Inventory

This inventory classifies every required workflow step and names its evidence
home. Deterministic work is represented by a fixed reference or task seed;
judgment remains in the hub or companion reference.

| Step | Class | Home | Evidence | Paired test |
|---|---|---|---|---|
| Approve scope and acceptance | judgment | `SKILL.md` | Approved plan and acceptance contract | N/A: human decision |
| Seed implementation work | deterministic | `task-seed:reference/task-seeds.md` | Host task IDs and evidence | task-tool |
| Record task fields | deterministic | `reference/run-record.schema.json` and `scripts/validate_protocol.py` | Validator output and exit code | `scripts/test_validate_protocol.py` |
| Implement one deliverable | judgment | `SKILL.md` | Worker report and diff | N/A: implementation choice |
| Verify exact surface | deterministic | `task-seed:reference/task-seeds.md` | Verifier output and `verified_commit_gate` | task-tool |
| Review committed task | deterministic | `reference/review-loop.md` | Findings-only native review record | `test_task_ticket_contract.py` |
| Repair confirmed findings | deterministic | `reference/review-loop.md` | Separate repair record and confirmed findings | `test_task_ticket_contract.py` |
| Decide whether a finding is confirmed | judgment | `reference/review-loop.md` | Repair record names the confirmed finding | N/A: review judgment |
| Repeat until clean | borderline | `reference/review-loop.md` | Amended commit and clean review record | `test_task_ticket_contract.py` |
| Validate cumulative release | deterministic | `task-seed:reference/final-validation-tasks.md` | Final validator task evidence | task-tool |
| Self-audit the skill | deterministic | `task-seed:reference/self-audit-tasks.md` | Self-audit task evidence | task-tool |
