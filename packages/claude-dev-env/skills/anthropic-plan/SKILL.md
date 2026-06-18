---
name: anthropic-plan
description: Workflow-backed implementation planning that creates a deep repo-local packet under docs/plans/<slug>/ before any code changes. Use for /anthropic-plan, /plan, "plan this first", "think before coding", "make a plan", "scope this out", "don't code yet", and non-trivial implementation requests that need source-grounded design, TDD steps, and validator approval before build work.
---

# Anthropic Plan

Create a source-grounded plan packet through the Claude Code Workflow runtime. The output is a repo-local `docs/plans/<slug>/` folder with context, spec, implementation, validation, and handoff docs. Stop before implementation.

## Launch

Call the workflow with the user request and current working directory. The payload goes in `args` — the Workflow tool exposes `args` to the script as its global `args`, and substitutes the user's full request for `$ARGUMENTS`:

```js
Workflow({
  scriptPath: "$HOME/.claude/skills/anthropic-plan/workflow/plan-packet.mjs",
  args: {
    task: "$ARGUMENTS",
    cwd: "<current working directory>"
  }
})
```

If the Workflow tool is unavailable, say `anthropic-plan requires the Workflow tool; aborting` and stop.

## Self-healing writes

The workflow writes the packet into the live checkout under `docs/plans/<slug>/`. When a session isolates writes into a worktree and blocks a direct write, the workflow stages each packet file through the Write tool — so the plain-language and historical-clutter checks still run — then copies the staged tree into the checkout. The packet lands under `docs/plans/<slug>/` in either session mode.

## Workflow Contract

The workflow handles the full planning loop:

1. Resolve repo root and packet path.
2. Read project instructions, rules, relevant skills, manifests, docs, tests, hooks, agents, commands, configs, and workflows.
3. Build a source inventory and extract source facts into `context/source-map.md`.
4. Write the packet under `docs/plans/<slug>/`.
5. Run `scripts/validate_packet.py`.
6. Spawn `plan-packet-validator` in fresh context.
7. Repair packet findings up to the workflow cap.
8. Run the reuse audit: search the codebase for existing equivalents of each new file/symbol the packet introduces, write `validation/reuse-audit.md`, and gate approval on any unjustified reproduction.
9. Build a single-file offline visual HTML of the finished packet from `templates/visual-plan.template.html` and write it beside the packet as `visual-plan.html`.
10. Return packet path, validation state, and findings.
11. Stop before implementation.

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

The reuse audit writes `validation/reuse-audit.md` with a per-item verdict for every new file or symbol the packet introduces and gates approval on any unjustified reproduction of existing behavior.

## Visualize

After validation and before approval, the workflow builds a single-file offline visual HTML of the finished packet from `templates/visual-plan.template.html` and writes it beside the packet as `visual-plan.html`. The file inlines all CSS and JavaScript and references no external assets, so it opens offline. It renders the packet as diagrams and compact cards — a stat hero, scenario strips, is/isn't cards, edit-recipe step sequences for the file-by-file change, reuse-audit verdict badges, and a checklist — rather than reproducing the markdown. Every label is written for the reviewer: the diagram says what each step does in plain words and leaves out code symbols (function names, selectors, test names), while each touched file keeps its repo-relative path dimmed for the build agent. Because it is generated after validation, `visual-plan.html` is not a required packet file.

## Rules

- Write docs only.
- Do not edit production code.
- Do not run implementation commands.
- Ask the user only for product choices that cannot be derived from local context.
- Fold resolved answers into the packet. Never leave an `Open Questions` section.
