---
name: anthropic-plan
description: Workflow-backed implementation planning that creates a deep repo-local packet under docs/plans/<slug>/ before any code changes. Use for /anthropic-plan, /plan, "plan this first", "think before coding", "make a plan", "scope this out", "don't code yet", and non-trivial implementation requests that need source-grounded design, TDD steps, and validator approval before build work.
---

# Anthropic Plan

Create a source-grounded plan packet through the Claude Code Workflow runtime. The output is a repo-local `docs/plans/<slug>/` folder with context, spec, implementation, validation, and handoff docs. Stop before implementation.

## Launch

Call the workflow with the user request and current working directory:

```js
Workflow({
  scriptPath: "$HOME/.claude/skills/anthropic-plan/workflow/plan-packet.mjs",
  input: {
    task: "$ARGUMENTS",
    cwd: "<current working directory>"
  }
})
```

If the Workflow tool is unavailable, say `anthropic-plan requires the Workflow tool; aborting` and stop.

## Workflow Contract

The workflow handles the full planning loop:

1. Resolve repo root and packet path.
2. Read project instructions, rules, relevant skills, manifests, docs, tests, hooks, agents, commands, configs, and workflows.
3. Build a source inventory and extract source facts into `context/source-map.md`.
4. Write the packet under `docs/plans/<slug>/`.
5. Run `scripts/validate_packet.py`.
6. Spawn `plan-packet-validator` in fresh context.
7. Repair packet findings up to the workflow cap.
8. Return packet path, validation state, and findings.
9. Stop before implementation.

## Packet Shape

Required root: `docs/plans/<slug>/`

Required top-level files and folders:

- `README.md`
- `packet.json`
- `context/`
- `spec/`
- `implementation/`
- `validation/`
- `handoff/`

The packet depth rule is strict: `README.md` is a thin hub, first-level folders group purpose, and second-level files carry detail. Add `context/subsystems/<name>.md` only when the planner finds more than twelve source files or more than three subsystems.

## Validation

The deterministic validator checks required files, placeholders, `Open Questions`, source-map strength, TDD coverage, standalone handoff prompts, and `packet.json` consistency.

The `plan-packet-validator` agent checks source accuracy, scope, enough implementation detail for a blind build agent, real TDD order, invented APIs or commands, and end-to-end acceptance criteria.

## Rules

- Write docs only.
- Do not edit production code.
- Do not run implementation commands.
- Ask the user only for product choices that cannot be derived from local context.
- Fold resolved answers into the packet. Never leave an `Open Questions` section.
