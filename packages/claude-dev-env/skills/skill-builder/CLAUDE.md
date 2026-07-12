# skill-builder

Orchestrates the skill-building lifecycle: classify type, scaffold folders, write via `skill-writer`, enforce modularity (sub-skills / composition), write description as a trigger catalog, self-audit, and refine from real usage.

**Trigger:** build a skill, new skill workflow, improve this skill, optimize skill description, skill development lifecycle, skill modularity, description trigger catalog.

## Purpose

Enforces craft standards for new and existing skills. For quick one-off SKILL.md edits, use `/skill-writer` directly. This skill classifies, scaffolds, gathers context (including composition plan and description triggers), delegates writing, and self-audits.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Hub — routing, principles, file index |
| `references/skill-types.md` | 9-type taxonomy with folder structures per type |
| `references/progressive-disclosure.md` | Hub pattern, folder conventions, hard rules |
| `references/skill-modularity.md` | Cross-skill modularity, sub-skills, composition plan |
| `references/description-field.md` | Description as trigger catalog (not story prose) |
| `references/self-audit-checklist.md` | Mandatory post-build audit |
| `references/delegation-map.md` | Subagent handoff patterns and transcript guidance |
| `references/thariq-x-post-skills.json` | Source reference — lessons from building Claude Code skills |
| `workflows/new-skill.md` | Full lifecycle for new skills (6 steps) |
| `workflows/improve-skill.md` | Observation-first flow for existing skills (6 steps) |
| `workflows/polish-skill.md` | Description trigger-catalog audit and final validation (5 steps) |
| `templates/gap-analysis.md` | Gaps, composition plan, description triggers |

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
- Modularity items and description trigger-catalog items are mandatory on every delivery.
- `skill-builder` orchestrates; `skill-writer` authors. Handoff packet must include type, gap analysis, composition plan, description trigger catalog, degree-of-freedom assessment, and constraints.
- Claude A / Claude B: Claude A (this session) designs; Claude B (subagents) tests the built skill on real tasks.
