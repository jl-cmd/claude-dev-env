# _shared (under skills/)

Skill-install shared assets. **Two homes:**

| Home | Path | Holds |
|---|---|---|
| **Skills shared** (this tree) | `~/.claude/skills/_shared/` | Skill-local PR-loop helpers (`portable-driver`, converge scripts), end-of-run gotcha protocol, and canonical-path stubs |
| **Top-level shared** | `~/.claude/_shared` | Advisor protocol, PR-loop contracts, runtime gate/preflight/review scripts |

Open a stub here, then load the `@~/.claude/_shared/...` target it names.

## Subdirectories

| Directory | Role |
|---|---|
| `advisor/` | Canonical path stubs for `@~/.claude/_shared/advisor/` (protocol + scripts) |
| `pr-loop/` | Skill-local converge helpers and stubs for contracts/runtime scripts under `@~/.claude/_shared/pr-loop/` |

## Shared reference docs (this tree)

| File | Role |
|---|---|
| `end-of-run-gotcha-recommendations.md` | End-of-run protocol: recommend pasteable skill gotchas (and split ref docs) from issues this run hit |

## Canonical-path stubs (load via `@`)

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

Files here are skills support assets (no `SKILL.md`). They install via `packages/claude-dev-env/bin/install.mjs`.