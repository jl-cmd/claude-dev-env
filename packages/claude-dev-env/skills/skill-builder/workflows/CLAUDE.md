# skill-builder/workflows

Step-by-step workflow files for each skill lifecycle phase, loaded on demand by `SKILL.md` routing.

## Key files

| File | Purpose |
|---|---|
| `new-skill.md` | Full lifecycle for creating a new skill: 6 steps from intent capture through type classification, folder scaffolding, writing via skill-writer, self-audit, and delivery. |
| `improve-skill.md` | Observation-first flow for improving an existing skill: 6 steps starting from real usage failures, gap analysis, targeted rewrite, and re-audit. |
| `polish-skill.md` | Description audit and final validation: 5 steps for description optimization, trigger phrase review, and checklist sign-off. |

## Conventions

- `SKILL.md` routes to exactly one workflow file per invocation based on the user's intent (new / improve / polish).
- Each workflow references `../references/self-audit-checklist.md` at its final step.
- Load only the workflow that matches the active task; the other two stay out of context.
