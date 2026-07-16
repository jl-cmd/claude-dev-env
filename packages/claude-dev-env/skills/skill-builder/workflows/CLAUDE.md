# skill-builder/workflows

Step-by-step workflow files for each skill lifecycle phase, loaded on demand by `SKILL.md` routing.

## Key files

| File | Purpose |
|---|---|
| `new-skill.md` | Full lifecycle: classify, scaffold, gather (composition + description triggers + deterministic inventory), write via skill-writer, self-audit, deliver. |
| `improve-skill.md` | Observation-first improve: diagnose activation/modularity/quality/deterministic prose, targeted fix, re-audit. |
| `polish-skill.md` | Description trigger-catalog audit; progressive disclosure + modularity + deterministic audit; checklist sign-off. |

## Conventions

- `SKILL.md` routes to exactly one workflow file per invocation based on the user's intent (new / improve / polish).
- Each workflow references `../references/self-audit-checklist.md` at its final verification step.
- New and improve load `skill-modularity.md`, `description-field.md`, and `deterministic-elements.md` when gathering or diagnosing.
- Polish Step 1 is the dedicated description rewrite pass; Step 2 covers structure, modularity, and deterministic placement.
- Load only the workflow that matches the active task; the other two stay out of context.
