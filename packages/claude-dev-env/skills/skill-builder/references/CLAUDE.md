# skill-builder/references

Best-practice specifications and the mandatory self-audit checklist for the `/skill-builder` skill.

## Key files

| File | Purpose |
|---|---|
| `self-audit-checklist.md` | Checklist after every build, improvement, or polish pass. Every item must pass before delivery. |
| `skill-types.md` | 9-type skill taxonomy with folder structures per type. |
| `progressive-disclosure.md` | Hub pattern, folder conventions, hard rules: SKILL.md under 500 lines, one-level references. |
| `skill-modularity.md` | Cross-skill modularity: one capability, sub-skills by name, composition plan, anti-monolith. |
| `description-field.md` | Frontmatter description as trigger catalog (capability stem + Triggers). No story prose. |
| `deterministic-elements.md` | Classify process steps; deterministic ones ship as code/artifacts under CODE_RULES. |
| `delegation-map.md` | Subagent handoff patterns and transcript guidance for skill-builder → skill-writer. |
| `thariq-x-post-skills.json` | Source reference data from Anthropic lessons on building Claude Code skills. |

## Conventions

- These files load on demand from `SKILL.md` routing — not all on every run.
- `self-audit-checklist.md` always loads at the end of a build cycle.
- Load `skill-modularity.md` during Gather and when scope/overlap is diagnosed.
- Load `description-field.md` during Gather, polish Step 1, and any activation diagnosis.
- Load `deterministic-elements.md` during Gather, when prose-as-code is diagnosed, and on polish structure audit.
- `thariq-x-post-skills.json` is source reference data, not executable content.
