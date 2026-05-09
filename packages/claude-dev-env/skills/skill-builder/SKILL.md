---
name: skill-builder
description: >-
  Orchestrates the complete skill-building lifecycle using best-practice-driven
  development. Routes through type classification, folder scaffolding, skill
  writing (via skill-writer), self-audit against a 38-point checklist, and
  iterative refinement from real usage observations. Use when creating new
  skills, improving existing skills, or optimizing skill descriptions.
  Triggers: 'build a skill', 'new skill workflow', 'improve this skill',
  'optimize skill description', 'skill development lifecycle'.
---

# Skill Builder

**Core principle:** Best-practice-driven craftsman. Knows every proven pattern, applies them intentionally, self-audits after building. The expert that enforces craft standards.

Sources: [Anthropic best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices), [Lessons from Building Claude Code](references/thariq-x-post-skills.json), model skills (bugteam, pr-converge).

## Gotchas

Highest-signal content. Append a bullet each time a skill build fails in a new way.

> "The highest-signal content in any skill is the Gotchas section. These sections should be built up from common failure points that Claude runs into when using your skill."

## When this skill applies

Trigger for requests to **build**, **improve**, or **polish** a skill. This skill orchestrates the process — it classifies, scaffolds, gathers context, delegates writing to `/skill-writer`, and self-audits the result.

For quick skill syntax questions or one-off SKILL.md edits, use `/skill-writer` directly instead.

**Refusal cases — first match wins:**

- **No clear task or domain.** Respond exactly: `What should this skill do? Give me a one-sentence description of the capability.`

## The Process

Each workflow file provides step-by-step instructions. After routing below, open the corresponding workflow file and follow it.

### Routing

Assess the user’s intent:

**Creating a new skill?**
Read `${CLAUDE_SKILL_DIR}/workflows/new-skill.md` and follow it.

**Improving an existing skill?**
Read `${CLAUDE_SKILL_DIR}/workflows/improve-skill.md` and follow it.

**Final polish only (description optimization, trigger audit)?**
Read `${CLAUDE_SKILL_DIR}/workflows/polish-skill.md` and follow it.

**Ambiguous?** Ask: "Are you creating a new skill, improving an existing one, or doing a final polish pass?"

### The Claude A / Claude B pattern

You and the user are **Claude A** — the expert who designs and refines the skill. Subagents running the built skill on real tasks are **Claude B** — the agent using the skill to perform actual work.

> "Work with one instance of Claude (‘Claude A’) to create a Skill that is used by other instances (‘Claude B’). Claude A helps you design and refine instructions, while Claude B tests them in real tasks."

The feedback loop: observe Claude B’s behavior, bring insights back, refine the skill, test again.

## Skill type routing

> "After cataloging all of our skills, we noticed they cluster into a few recurring categories."

Classify the skill into one of 9 types. The type determines folder structure. See `${CLAUDE_SKILL_DIR}/references/skill-types.md` for full details.

| # | Type | Key folders |
|---|---|---|
| 1 | Library & API Reference | reference/, examples/ |
| 2 | Product Verification | scripts/, reference/ |
| 3 | Data Fetching & Analysis | reference/, scripts/ |
| 4 | Business Process & Team Automation | templates/, scripts/ |
| 5 | Code Scaffolding & Templates | templates/, scripts/ |
| 6 | Code Quality & Review | reference/, scripts/ |
| 7 | CI/CD & Deployment | workflows/, scripts/ |
| 8 | Runbooks | reference/, templates/ |
| 9 | Infrastructure Operations | reference/, scripts/ |

## Principles

These are non-negotiable. Every skill must satisfy them. The self-audit checklist enforces them.

### Concision and defaults

> "Default assumption: Claude is already very smart. Only add context Claude doesn’t already have."

> "Don’t State the Obvious — focus on information that pushes Claude out of its normal way of thinking."

Challenge each sentence: "Does Claude really need this?"

### Degree of freedom

> "Match the level of specificity to the task’s fragility and variability."

High freedom (text guidance) for open fields. Low freedom (exact scripts, no parameters) for narrow bridges with cliffs.

> "Avoid Railroading Claude — give Claude the information it needs, but give it the flexibility to adapt."

### Progressive disclosure

> "Keep SKILL.md body under 500 lines."

SKILL.md is a hub. Detail lives in reference/, scripts execute without being read into context. References one level deep. Files over 100 lines get a TOC. Forward slashes only.

See `${CLAUDE_SKILL_DIR}/references/progressive-disclosure.md` for the full specification.

### Description field

> "Always write in third person. The description is critical for skill selection: Claude uses it to choose the right Skill from potentially 100+ available Skills."

Include what the skill does AND specific trigger phrases. Max 1024 chars.

> "The description field is not a summary — it’s a description of when to trigger."

### Gotchas

> "Build a Gotchas Section — the highest-signal content in any skill."

Mandatory section. Built from real failure observations. Updated over time as new failure modes surface.

### Templates and examples

> "Provide templates for output format" and "Examples help Claude understand the desired style and level of detail more clearly than descriptions alone."

Use the template pattern for structured outputs. Use the examples pattern (input/output pairs) for style-dependent work.

### Workflows and checklists

> "For particularly complex workflows, provide a checklist that Claude can copy into its response and check off as it progresses."

Multi-step processes get `[ ]` checklists. Quality-critical operations get feedback loops (run validator → fix → repeat).

### Scripts

> "Handle error conditions rather than punting to Claude." "Make clear whether Claude should execute the script or read it as reference."

> "One of the most powerful tools you can give Claude is code — letting Claude spend its turns on composition rather than reconstructing boilerplate."

### Setup and memory

> "Think through the Setup — some skills may need to be set up with context from the user. A good pattern is to store this in a config.json file."

> "Data stored in the skill directory may be deleted when you upgrade the skill, so store persistent data in `${CLAUDE_PLUGIN_DATA}`."

### Constraints and refusal cases

> bugteam pattern — non-negotiables separated from guidance, with design rationale. Explicit "first match wins" refusal conditions.

### Anti-patterns

> No Windows paths. Don’t offer too many options — provide a default with escape hatch. Avoid time-sensitive claims. Use consistent terminology. No deeply nested references.

## Self-audit

After every build, improvement, or polish pass, run the mandatory checklist at `${CLAUDE_SKILL_DIR}/references/self-audit-checklist.md`. Every item must pass before delivery. Fix failures, then re-audit.

## Delegation to skill-writer

skill-builder orchestrates; skill-writer authors. The handoff packet from Step 4 must include:

- Skill type and folder structure
- Gap analysis or observation findings
- Degree of freedom assessment
- Initial gotchas
- Any constraints

See `${CLAUDE_SKILL_DIR}/references/delegation-map.md` for exact patterns.

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | This hub — principles, process, routing, file index |
| `references/skill-types.md` | 9-type taxonomy with folder structures per type |
| `references/progressive-disclosure.md` | Folder conventions, hub pattern, hard rules |
| `references/self-audit-checklist.md` | 38-point mandatory post-build audit |
| `references/delegation-map.md` | Subagent handoff patterns and transcript guidance |
| `workflows/new-skill.md` | Full lifecycle for new skills (6 steps) |
| `workflows/improve-skill.md` | Observation-first flow for existing skills (6 steps) |
| `workflows/polish-skill.md` | Description audit and final validation (5 steps) |
| `templates/gap-analysis.md` | Template for documenting skill gaps |

## Folder map

- `SKILL.md` — hub.
- `references/` — best-practice specifications and the audit checklist.
- `workflows/` — step-by-step workflows for each lifecycle phase.
- `templates/` — reusable templates for skill artifacts.
