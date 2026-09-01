# orchestrator

Turns the session into the orchestrator. Executors consult this session.
The human is the next hop. This skill does not bind `session-advisor`.

## Key files

| File | Role |
|---|---|
| `SKILL.md` | Process, routing, spawn ticket, constraints |
| `reference/consult-the-orchestrator.md` | When and how executors consult this session |
| `reference/executor-consult-block.md` | Paste parts for every spawn ticket |
| `reference/host-detect.md` | Host profile for worker-model routing |
| `scripts/status_gate.py` | Status file, latch, and re-arm gate |
| `test_orchestrator_skill_contract.py` | Skill-text contract |

## Subdirectories

| Directory | Role |
|---|---|
| `reference/` | Consult contract and ticket paste parts |
| `scripts/` | Deterministic status_gate |
