# Code Standards

> **Canonical review contract:** [`CODE_RULES.md`](../docs/CODE_RULES.md) — the human and AI review contract for code quality, loaded on demand.
> **Checked-in pointer:** [`.cursor/BUGBOT.md`](../../../.cursor/BUGBOT.md) — the file Cursor BugBot reads; it points at `CODE_RULES.md`.
> **Production enforcement.** The staged policy lint runs `hooks/blocking/code_rules_enforcer.py` over each changed file. No write-time hook runs it. Use `python packages/claude-dev-env/scripts/cde_lint.py --staged` before you commit, and CI runs the same lint against the merge base. Each mechanical rule carries a synchronization test.

## Policy surface map

| Layer | Path | Role |
|---|---|---|
| Contract | `docs/CODE_RULES.md` | Full review criteria for PR agents, loaded on demand |
| Pointer | `.cursor/BUGBOT.md` | Checked-in file Cursor BugBot reads; points at `CODE_RULES.md` |
| Enforcer | `hooks/blocking/code_rules_enforcer.py` | Hand-maintained checks the staged policy lint runs; not generated from the docs |
| Lint | `scripts/cde_lint.py` | Runs the enforcer and the other policy rules over staged or changed files |
| Session rules | `rules/*.md` | Runtime session policy (questions, tasks, shell) |

Load `CODE_RULES.md` when reviewing a PR, resolving a policy conflict, or generating code. Prefer linking this ref over restating rules.

Two standards live in `CODE_RULES.md` in full:

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
