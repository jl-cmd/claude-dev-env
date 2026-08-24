# Code Standards

> **Checked-in review contract:** [`.cursor/BUGBOT.md`](../../../.cursor/BUGBOT.md) — the human and AI review contract for code quality.
> **Compact projection:** [`CODE_RULES.md`](../docs/CODE_RULES.md) — validated summary for generation load.
> **Production enforcement:** `hooks/blocking/code_rules_enforcer.py` — hand-maintained Write/Edit gates; each mechanical rule carries a synchronization test.

## Policy surface map

| Layer | Path | Role |
|---|---|---|
| Contract | `.cursor/BUGBOT.md` | Full review criteria for PR agents |
| Projection | `docs/CODE_RULES.md` | Compact always-load reference; must not diverge from AGENTS |
| Enforcer | `hooks/blocking/code_rules_enforcer.py` | Hand-maintained blockers; not generated from the docs |
| Session rules | `rules/*.md` | Runtime session policy (questions, tasks, shell) |

Load `.cursor/BUGBOT.md` when reviewing a PR or resolving a policy conflict. Load `CODE_RULES.md` when generating code under the compact checklist. Prefer linking these refs over restating rules.

Two standards live in the canonical policy in full (and in the projection by name):

- **TDD** — CODE_RULES §8 / AGENTS Tests: red, green, refactor; no production code before a failing test.
- **Right-sized engineering** — CODE_RULES §7 / AGENTS Design: functions over classes; concrete over abstract; add an abstraction at the commit that introduces its second concrete implementation.

BDD is the outer process and TDD is the inner loop: [`bdd.md`](bdd.md) discovers and formulates the behavior a feature needs, then each formulated behavior is built through the TDD cycle.

## Session policies (ref docs, not restated here)

| Concern | Rule file |
|---|---|
| Question routing | [`ask-user-question-required.md`](ask-user-question-required.md) |
| Task tracking / worker completion | [`workers-done-before-complete.md`](workers-done-before-complete.md) |
| Multi-step task list | skill `task-build` (see agents catalog) |

## Validation

Mechanical enforcer coverage is checked by the existing `hooks/blocking/test_code_rules_enforcer*.py` suite.
