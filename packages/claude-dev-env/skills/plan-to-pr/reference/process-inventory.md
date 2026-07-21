# Process Inventory

This inventory classifies every required workflow step and names its evidence
home. Deterministic work is represented by a fixed reference or task seed;
judgment remains in the hub or companion reference.

| Step | Class | Home | Evidence | Paired test |
|---|---|---|---|---|
| Create and validate native plan packet | deterministic | `reference/packet-contract.md` and `reference/packet-schema.json` | Approved packet, validation result, and packet path | `test_skill_contract.py` and `test_task_ticket_contract.py` |
| Approve scope and acceptance | judgment | `SKILL.md` | Approved plan and acceptance contract | N/A: human decision |
| Seed implementation work after packet approval | deterministic | `task-seed:reference/task-seeds.md` | Host task IDs, packet path, and evidence | task-tool |
| Record task fields | deterministic | `reference/run-record.schema.json` and `scripts/validate_protocol.py` | Validator output and exit code | `scripts/test_validate_protocol.py` |
| Implement one deliverable | judgment | `SKILL.md` | Worker report and diff | N/A: implementation choice |
| Verify exact surface | deterministic | `task-seed:reference/task-seeds.md` | Verifier output and `verified_commit_gate` | task-tool |
| Review committed task | deterministic | `reference/review-loop.md` | Findings-only native review record | `test_task_ticket_contract.py` |
| Repair confirmed findings | deterministic | `reference/review-loop.md` | Separate repair record and confirmed findings | `test_task_ticket_contract.py` |
| Decide whether a finding is confirmed | judgment | `reference/review-loop.md` | Repair record names the confirmed finding | N/A: review judgment |
| Repeat until clean | borderline | `reference/review-loop.md` | Amended commit and clean review record | `test_task_ticket_contract.py` |
| Validate cumulative release | deterministic | `task-seed:reference/final-validation-tasks.md` | Final validator task evidence | task-tool |
| Self-audit the workflow | deterministic | `task-seed:reference/self-audit-tasks.md` | Self-audit task evidence | task-tool |
| Run post-PR cleanup | deterministic | `SKILL.md` and `reference/model-routing.md` | Luna xhigh `/e-simplify` result and pushed cleanup commit | task-tool |
| Run post-PR max review | deterministic | `reference/review-loop.md` | Luna low max-loop findings, repairs, pushes, and clean result | task-tool |
