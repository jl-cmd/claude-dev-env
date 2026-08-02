---
name: show
description: Create and review inline visual explanations, diagrams, interactive widgets, mockups, charts, and illustrations.
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

Every route reads `references/core-design.md`, `references/accessibility.md`, and `references/quality-gates.md`.

The flowchart, structural, illustrative, and erd routes also read `references/subject-inventory.md`.

## Invariants

- Use sentence case, flat surfaces, restrained color, and transparent outer containers.
- Hold the smallest caption at the 16-at-680 scaled text floor set in `references/svg-contract.md`, and use font weights 400 or 500.
- Support light and dark appearance modes.
- Use color to encode meaning, with a short legend when meaning is not self-evident.
- Prefer multiple focused visuals over one dense canvas.
- SVG output uses one of two canvas tiers, with `title` and `desc` as its first children: the standard tier `viewBox="0 0 680 H"` for a single small explainer, and the large tier `viewBox="0 0 W H"` with `W` from 1360 to 2000. The large tier is the default for anything with two or more panels or more than about 6 labeled elements.
- When the visual shows code, a diff, or a plan that lives in a repo, read the real lines and tie every arrow to a `path:line` citation before drawing. When the picture and the source disagree, the picture is wrong.
- HTML output begins with a visually hidden `h2` summary.
- Examples demonstrate valid output; references define the rules.

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

