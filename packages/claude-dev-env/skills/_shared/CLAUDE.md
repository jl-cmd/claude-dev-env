# skills/_shared

**Map** for skill-install shared assets. Open a stub, then load the `@` target.

## Two homes

| Home | Path | Holds |
|---|---|---|
| **Skills shared** | `~/.claude/skills/_shared/` | Converge helpers, end-of-run gotcha ref, and `@` stubs |
| **Top-level shared** | `~/.claude/_shared/` | Advisor protocol, PR-loop contracts, runtime scripts |


## Reference docs (this tree)

| File | Role |
|---|---|
| **`end-of-run-gotcha-recommendations.md`** | End-of-run pasteable gotcha protocol for every skill |

## Subdirectories

| Directory | Role |
|---|---|
| **`advisor/`** | Stubs → `@~/.claude/_shared/advisor/` |
| **`pr-loop/`** | Local converge helpers + stubs → `@~/.claude/_shared/pr-loop/` |
| **`references/`** | Word-for-word Google review-guide docs that more than one skill links (`small-cls.md`) |

## Canonical-path stubs

| Stub here | Load |
|---|---|
| `advisor/advisor-protocol.md` | `@~/.claude/_shared/advisor/advisor-protocol.md` |
| `advisor/CLAUDE.md` | `@~/.claude/_shared/advisor/CLAUDE.md` |
| `advisor/scripts/README.md` | `@~/.claude/_shared/advisor/scripts/` |
| `pr-loop/audit-contract.md` | `@~/.claude/_shared/pr-loop/audit-contract.md` |
| `pr-loop/audit-reply-template.md` | `@~/.claude/_shared/pr-loop/audit-reply-template.md` |
| `pr-loop/code-rules-gate.md` | `@~/.claude/_shared/pr-loop/code-rules-gate.md` |
| `pr-loop/fix-protocol.md` | `@~/.claude/_shared/pr-loop/fix-protocol.md` |
| `pr-loop/gh-payloads.md` | `@~/.claude/_shared/pr-loop/gh-payloads.md` |
| `pr-loop/post-audit-thread-contract.md` | `@~/.claude/_shared/pr-loop/post-audit-thread-contract.md` |
| `pr-loop/precatch-rubric.md` | `@~/.claude/_shared/pr-loop/precatch-rubric.md` |
| `pr-loop/state-schema.md` | `@~/.claude/_shared/pr-loop/state-schema.md` |
| `pr-loop/worker-spawn.md` | `@~/.claude/_shared/pr-loop/worker-spawn.md` |
| `pr-loop/scripts/RUNTIME_SCRIPTS.md` | `@~/.claude/_shared/pr-loop/scripts/` |

Install via `packages/claude-dev-env/bin/install.mjs`.
