---
name: show
description: Create and review inline visual explanations, diagrams, interactive widgets, mockups, charts, and illustrations. Triggers on "/show", "show me", "draw", "diagram this", "visualize", "map this out", "make it interactive", or a request for a mockup, chart, or illustration.
---

# Show

Use this skill when a user asks to show, draw, map, visualize, explain visually, or build an interactive visual.

## Operating sequence

1. Identify the user’s intent and choose the closest route in `routing.yaml`.
2. Read the route’s references and workflow.
3. Start from the route template when one exists.
4. Keep explanatory prose outside the visual.
5. Run the route validators before returning the result.
6. Split dense visuals into focused visuals with connective prose.

## Routes

| Intent | Route | Primary output |
|---|---|---|
| Steps, decisions, lifecycle, transformation | `flowchart` | SVG |
| Architecture, containment, hierarchy | `structural` | SVG |
| Mechanism, intuition, spatial metaphor | `illustrative` | SVG or HTML |
| Entity or class relationships | `erd` | HTML/SVG |
| Controls that change a visual explanation | `interactive` | HTML |
| UI surface, form, card, dashboard | `mockup` | HTML |
| Quantitative or geographic data | `chart` | HTML/SVG |
| Illustration or generative art | `art` | HTML or raster |

Each route's reference list lives in `routing.yaml`.

## Invariants

- Use sentence case, flat surfaces, and a flat colorful palette in the style of `samples/` — three to four fixed hues, tinted fills, and neutral grays, per `references/core-design.md`.
- Use color to encode meaning, with a short legend when the meaning needs one.
- SVG output follows the canvas tiers, text floor, and opaque warm-white background rect set in `references/svg-contract.md`, with `title` and `desc` as its first children, and uses font weights 400 or 500.
- Prefer multiple focused visuals over one dense canvas.
- When the visual shows code, a diff, or a plan that lives in a repo, read the real lines and tie every arrow to a `path:line` citation before drawing. When the picture and the source disagree, the picture is wrong.
- HTML output begins with a visually hidden `h2` summary.
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

