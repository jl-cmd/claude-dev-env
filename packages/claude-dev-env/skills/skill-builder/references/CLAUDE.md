# skill-builder/references

Best-practice specifications and the mandatory self-audit checklist for the `/skill-builder` skill.

## Key files

| File | Purpose |
|---|---|
| `self-audit-checklist.md` | 38-point checklist run after every build, improvement, or polish pass. Every item must pass before delivery. |
| `skill-types.md` | 9-type skill taxonomy with folder structures per type (Library & API Reference, Product Verification, Data Fetching, Business Process, Code Scaffolding, Code Quality, CI/CD, Runbooks, Infrastructure). |
| `progressive-disclosure.md` | Hub pattern, folder conventions, and hard rules: SKILL.md under 500 lines, detail in reference/, scripts execute without context load, references one level deep. |
| `delegation-map.md` | Subagent handoff patterns and transcript guidance for the skill-builder → skill-writer handoff. |
| `thariq-x-post-skills.json` | Source reference data from Anthropic lessons on building Claude Code skills. |

## Conventions

- These files are loaded on demand by `SKILL.md` routing — not all are loaded on every run.
- `self-audit-checklist.md` is always loaded at the end of a build cycle.
- `thariq-x-post-skills.json` is source reference data, not executable content.
