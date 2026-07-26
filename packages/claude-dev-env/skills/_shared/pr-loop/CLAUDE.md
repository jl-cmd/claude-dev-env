# pr-loop

Runtime documents and scripts shared by every PR-loop skill: `bugteam`, `pr-converge`, `autoconverge`, `findbugs`, `fixbugs`, and `qbug`. Provides the loop contracts, the XML prompt template, the portable converge driver protocol, Python runtime scripts, and named constants those skills invoke during each loop tick. Changes here affect every consumer simultaneously — treat this as a breaking-change surface.

## Key documents

| File | Purpose |
|---|---|
| `audit-contract.md` | Canonical finding schema (Shape A / Shape B) and loop contract; defines the JSON shapes every audit skill must emit |
| `audit-reply-template.md` | Canonical reply skeleton Claude posts to each unresolved review thread; single source of truth for reply structure |
| `post-audit-thread-contract.md` | Single source of truth for the `post_audit_thread.py` invocation string, exit-code table, and per-caller policy (bugteam exit 2 = hard blocker; autoconverge clean-audit failed post = recorded bypass) |
| `fix-protocol.md` | Ordered sequence a fix lens follows: read, capture SHA, TDD, apply, validate, self-audit, commit, push, reply + resolve |
| `gh-payloads.md` | How to build GitHub review and reply payloads via MCP tools; describes the one-review-per-loop pattern |
| `state-schema.md` | Fields each PR-loop workflow tracks across iterations; documents common fields and per-skill extensions |
| `code-rules-gate.md` | Reference for the CODE_RULES pre-commit gate check; describes what the gate blocks and when it runs |
| `precatch-rubric.md` | Shared pre-catch lane checklist — deterministic sweep, doc-vs-code parity, test-assertion completeness, PR-description parity, adversarial audit — that autoconverge's lenses and pr-converge's CODE_REVIEW step read on demand |
| `worker-spawn.md` | Worker-spawn tier protocol and Claude-only slash-step host routing: three tiers, CLI/API inputs, JSON result shape, host detection, code-review modes via `detect_host_profile` + `invoke_code_review`, leader-socket rule, cloud setup; documents `scripts/resolve_worker_spawn.py` |
| `portable-driver.md` | Continuous in-session pacer when Workflow / ScheduleWakeup are absent. |
| `prompts/pr-consistency-audit.xml` | Structured prompt artifact for the cross-file consistency audit agent. |

## Subdirectories

| Directory | Role |
|---|---|
| `prompts/` | XML agent prompt templates. |
| `scripts/` | Python scripts and constants consumed at runtime by the PR-loop skills: loop state management, prompt building, outcome recording, path resolution, pacer selection, preflight checks, the CODE_RULES gate, and review posting. |

## Breaking-change rule

Any shape change in `audit-contract.md` or `audit-reply-template.md` requires updating every consuming skill in the same commit.
