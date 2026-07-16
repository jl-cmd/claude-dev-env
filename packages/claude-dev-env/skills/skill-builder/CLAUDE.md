# skill-builder

Orchestrates the skill-building lifecycle: classify type, scaffold folders, write via `skill-writer`, enforce modularity (sub-skills / composition), write description as a trigger catalog, require deterministic steps as code, self-audit, and refine from real usage.

**Trigger:** build a skill, new skill workflow, improve this skill, optimize skill description, skill development lifecycle, skill modularity, description trigger catalog, deterministic skill scripts.

## Purpose

Enforces craft standards for new and existing skills. For quick one-off SKILL.md edits, use `/skill-writer` directly. This skill classifies, scaffolds, gathers context (composition plan, description triggers, deterministic inventory), delegates writing, and self-audits.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Hub — routing, principles, file index |
| `references/skill-types.md` | 9-type taxonomy with folder structures per type |
| `references/progressive-disclosure.md` | Hub pattern, folder conventions, hard rules |
| `references/skill-modularity.md` | Cross-skill modularity, sub-skills, composition plan |
| `references/description-field.md` | Description as trigger catalog (not story prose) |
| `references/deterministic-elements.md` | Deterministic steps as code/task seeds; no markdown checkbox boards |
| `references/self-audit-checklist.md` | Post-build audit task seeds (TaskCreate / TodoWrite) |
| `references/delegation-map.md` | Subagent handoff patterns and transcript guidance |
| `references/thariq-x-post-skills.json` | Source reference — lessons from building Claude Code skills |
| `workflows/new-skill.md` | Full lifecycle for new skills (6 steps) |
| `workflows/improve-skill.md` | Observation-first flow for existing skills (6 steps) |
| `workflows/polish-skill.md` | Description trigger-catalog audit and final validation (5 steps) |
| `templates/gap-analysis.md` | Gaps, composition plan, description triggers, deterministic inventory |

## Subdirectories

| Directory | Purpose |
|---|---|
| `references/` | Best-practice specs and the audit checklist |
| `workflows/` | Step-by-step workflows for each lifecycle phase |
| `templates/` | Reusable templates for skill artifacts |

## Routing

- **New skill** → `workflows/new-skill.md`
- **Improve existing** → `workflows/improve-skill.md`
- **Final polish only** → `workflows/polish-skill.md`
- **Ambiguous** → ask the user which one applies

## Conventions

- Every build ends with the self-audit at `references/self-audit-checklist.md`; fix failures before delivery.
- Modularity items, description trigger-catalog items, and deterministic-element classification are mandatory on every delivery.
- `skill-builder` orchestrates; `skill-writer` authors. Handoff packet must include type, gap analysis, composition plan, description trigger catalog, deterministic inventory, degree-of-freedom assessment, and constraints.
- Claude A / Claude B: Claude A (this session) designs; Claude B (subagents) tests the built skill on real tasks.
