---
name: show
description: Create and review inline visual explanations, diagrams, interactive widgets, mockups, charts, and illustrations. Triggers on "/show", "show me", "draw", "diagram this", "visualize", "map this out", "make it interactive", or a request for a mockup, chart, or illustration.
---

# Show

Use this skill when a user asks to show, draw, map, visualize, explain visually, or build an interactive visual.

## Routes

Pick the row whose intent matches the request, then follow `workflows/create-visual.md`.

| Intent | Route |
|---|---|
| Steps, decisions, lifecycle, transformation | `flowchart` |
| Architecture, containment, hierarchy | `structural` |
| Mechanism, intuition, spatial metaphor | `illustrative` |
| Entity or class relationships | `erd` |
| Controls that change a visual explanation | `interactive` |
| UI surface, form, card, dashboard | `mockup` |
| Quantitative or geographic data | `chart` |
| Illustration or generative art | `art` |

Each route's references and template live in `routing.yaml`; the template sets the output type.

## Invariants

- Design, palette, and color meaning follow `references/core-design.md`.
- SVG output follows `references/svg-contract.md`; HTML output follows `references/host-and-html.md`.
- Prefer multiple focused visuals over one dense canvas, and keep explanatory prose outside the visual.
- Keep one diagram family per visual.
- When the visual shows code, a diff, or a plan that lives in a repo, read the real lines and tie every arrow to a `path:line` citation before drawing. When the picture and the source disagree, the picture is wrong.
- `samples/` holds good examples the user has picked out. Read them on demand to study what works; the rules stay in the references.

## Workflows

- New visual: `workflows/create-visual.md`
- Review or repair: `workflows/review-visual.md`

## Validation

Run from any working directory:

```text
python <skill-root>/scripts/validate-package.py
python <skill-root>/scripts/validate-artifact.py <artifact>
```

The package is complete only when package checks, artifact checks, and rendered inspection all pass.

