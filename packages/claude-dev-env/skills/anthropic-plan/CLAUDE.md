# anthropic-plan

**Trigger:** `/anthropic-plan`, `/plan`, "plan this first", "think before coding", "make a plan", "scope this out", "don't code yet", and non-trivial requests that need source-grounded design before build work.

Creates a repo-local plan packet under `docs/plans/<slug>/` by running the `plan-packet.mjs` workflow. The packet holds context, spec, implementation steps, validation, and a handoff prompt for the build agent. The skill stops before any production code changes.

## Subdirectories

| Directory | Role |
|---|---|
| `scripts/` | Python validator (`validate_packet.py`) that checks the packet's required files, placeholders, and consistency. |
| `templates/` | Template files the workflow renders when building the packet (`README.md`, `build-prompt.md`, `reuse-audit.md`, `source-map.md`, `visual-plan.template.html`). |
| `workflow/` | The `.mjs` workflow scripts and their test files. |

## Key files

| File | Role |
|---|---|
| `SKILL.md` | Entry point. Full planning protocol, workflow contract, packet shape, and validation rules. |
| `workflow/plan-packet.mjs` | Main workflow script. Reads repo context, writes the packet, runs the validator, spawns `plan-packet-validator`, runs the reuse audit, builds the visual HTML, and returns the packet path. |
| `workflow/plan-packet.contract.test.mjs` | Contract tests for the workflow script. |
| `packages/claude-dev-env/skills/anthropic-plan/scripts/validate_packet.py` | Deterministic validator: checks required files, open questions, source-map strength, TDD coverage, and `packet.json` consistency. Exits with code 2 on failure. |
| `templates/visual-plan.template.html` | Template for the single-file offline visual HTML the workflow builds after validation. |

## Entry point

```js
Workflow({
  scriptPath: "$HOME/.claude/skills/anthropic-plan/workflow/plan-packet.mjs",
  args: { task: "<user request>", cwd: "<working directory>" }
})
```

The session must be in a worktree (path has `.claude/worktrees/`) before calling the workflow.
