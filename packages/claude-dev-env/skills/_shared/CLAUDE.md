# _shared (under skills/)

Skill-install shared assets. **Two homes exist** — do not confuse them:

| Home | Path | Holds |
|---|---|---|
| **Skills shared** (this tree) | `~/.claude/skills/_shared/` | Skill-local PR-loop helpers (`portable-driver`, converge scripts), end-of-run gotcha protocol, **and redirect stubs** |
| **Top-level shared** (canonical runtime) | `~/.claude/_shared/` | Advisor protocol, PR-loop contracts, runtime gate/preflight/review scripts |

When a path is missing here but exists under `~/.claude/_shared/`, open the redirect stub or load the `@~/.claude/_shared/...` target directly.

## Subdirectories

| Directory | Role |
|---|---|
| `advisor/` | **Redirect** → `@~/.claude/_shared/advisor/` (protocol + scripts) |
| `pr-loop/` | Skill-local converge helpers **plus** redirects for contracts/runtime scripts that live under `@~/.claude/_shared/pr-loop/` |

## Shared reference docs (live here)

| File | Role |
|---|---|
| `end-of-run-gotcha-recommendations.md` | End-of-run protocol: recommend pasteable skill gotchas (and split ref docs) from issues this run hit |

## Redirect stubs (canonical under `~/.claude/_shared/`)

| Stub here | Load instead |
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

Files here are not skills themselves and have no `SKILL.md`. They install alongside each consuming skill via the install pipeline in `packages/claude-dev-env/bin/install.mjs`.
