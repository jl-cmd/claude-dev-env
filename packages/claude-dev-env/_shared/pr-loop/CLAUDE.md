# _shared/pr-loop

Runtime documents and scripts shared by every PR-loop skill. Changes here affect `bugteam`, `pr-converge`, `findbugs`, `fixbugs`, and `qbug` simultaneously — treat this as a breaking-change surface.

## Key documents

| File | Purpose |
|---|---|
| `audit-contract.md` | Canonical finding schema (Shape A / Shape B) and loop contract; defines the JSON shapes every audit skill must emit |
| `audit-reply-template.md` | Canonical reply skeleton Claude posts to each unresolved review thread; single source of truth for reply structure |
| `fix-protocol.md` | Ordered sequence a fix lens follows: read, capture SHA, TDD, apply, validate, self-audit, commit, push, reply + resolve |
| `gh-payloads.md` | How to build GitHub review and reply payloads via MCP tools; describes the one-review-per-loop pattern |
| `state-schema.md` | Fields each PR-loop workflow tracks across iterations; documents common fields and per-skill extensions |
| `code-rules-gate.md` | Reference for the CODE_RULES pre-commit gate check; describes what the gate blocks and when it runs |

## Subdirectory

| Entry | Description |
|---|---|
| `scripts/` | Python scripts and constants consumed at runtime by the PR-loop skills |

## Breaking-change rule

Any shape change in `audit-contract.md` or `audit-reply-template.md` requires updating every consuming skill in the same commit.
