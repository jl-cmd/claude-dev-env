# pr-loop

Runtime documents and scripts shared by every PR-loop skill. Changes here affect ugteam, pr-converge, indbugs, ixbugs, qbug, and utoconverge simultaneously — treat this as a breaking-change surface.

## Key documents

| File | Purpose |
|---|---|
| udit-contract.md | Canonical finding schema (Shape A / Shape B) and loop contract; defines the JSON shapes every audit skill must emit |
| udit-reply-template.md | Canonical reply skeleton Claude posts to each unresolved review thread; single source of truth for reply structure |
| post-audit-thread-contract.md | Single source of truth for the post_audit_thread.py invocation string, exit-code table, and per-caller policy |
| ix-protocol.md | Ordered sequence a fix lens follows: read, capture SHA, TDD, apply, validate, self-audit, commit, push, reply + resolve |
| gh-payloads.md | How to build GitHub review and reply payloads via MCP tools; describes the one-review-per-loop pattern |
| state-schema.md | Fields each PR-loop workflow tracks across iterations; documents common fields and per-skill extensions |
| code-rules-gate.md | Reference for the CODE_RULES pre-commit gate check; describes what the gate blocks and when it runs |
| precatch-rubric.md | Shared pre-catch lane checklist that autoconverge lenses and pr-converge CODE_REVIEW read on demand |
| worker-spawn.md | Worker-spawn tier protocol and Claude-only slash-step host routing |
| portable-driver.md | Continuous in-session pacer when Workflow / ScheduleWakeup are absent |

## Subdirectories

| Directory | Role |
|---|---|
| prompts/ | XML agent prompt templates |
| scripts/ | Python scripts for gates, permissions, loop state, prompt building, outcomes, path resolution, pacer selection, and preflight |

## Breaking-change rule

Any shape change in udit-contract.md or udit-reply-template.md requires updating every consuming skill in the same commit.
