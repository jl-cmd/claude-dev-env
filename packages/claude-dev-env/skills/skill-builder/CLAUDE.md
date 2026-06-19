# skill-builder

Orchestrates the complete skill-building lifecycle: classify the skill type, scaffold folders, write via `skill-writer`, self-audit against a 38-point checklist, and refine from real usage observations.

**Trigger:** "build a skill", "new skill workflow", "improve this skill", "optimize skill description", "skill development lifecycle".

## Purpose

The expert that enforces craft standards. For quick one-off SKILL.md edits, use `/skill-writer` directly. This skill classifies, scaffolds, gathers context, delegates writing, and self-audits the result.

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Hub — routing, 9-type taxonomy table, core principles, file index |
| `references/skill-types.md` | 9-type taxonomy with folder structures per type |
| `references/progressive-disclosure.md` | Hub pattern, folder conventions, hard rules |
| `references/self-audit-checklist.md` | 38-point mandatory post-build audit |
| `references/delegation-map.md` | Subagent handoff patterns and transcript guidance |
| `references/thariq-x-post-skills.json` | Source reference — lessons from building Claude Code skills |
| `workflows/new-skill.md` | Full lifecycle for new skills (6 steps) |
| `workflows/improve-skill.md` | Observation-first flow for existing skills (6 steps) |
| `workflows/polish-skill.md` | Description audit and final validation (5 steps) |
| `templates/gap-analysis.md` | Template for documenting skill gaps |

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

- Every build ends with the 38-point self-audit at `references/self-audit-checklist.md`; fix failures before delivery.
- `skill-builder` orchestrates; `skill-writer` authors. The handoff packet must include type, gap analysis, degree-of-freedom assessment, and constraints.
- The Claude A / Claude B pattern: Claude A (this session) designs; Claude B (subagents) tests by running the built skill on real tasks.
