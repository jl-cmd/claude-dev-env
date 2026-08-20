---
name: skill-builder
description: >-
  Skill lifecycle: classify, scaffold, write via the skill-writer-agent, self-audit, compose
  sub-skills, polish description triggers, enforce deterministic scripts. Triggers:
  build a skill, new skill workflow, improve this skill, optimize skill description,
  skill development lifecycle, skill modularity, skill composition, description
  trigger catalog, deterministic skill scripts.
---

# Skill Builder

**Core principle:** Best-practice-driven craftsman. Knows every proven pattern, applies them intentionally, self-audits after building. The expert that enforces craft standards.

Sources: [Anthropic best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices), [Lessons from Building Claude Code](references/thariq-x-post-skills.json), model skills (bugteam, pr-converge).

## Gotchas

Highest-signal content. Append a bullet each time a skill build fails in a new way.

> "The highest-signal content in any skill is the Gotchas section. These sections should be built up from common failure points that Claude runs into when using your skill."

- Story-form `description` burns always-on context and weakens selection — rewrite to capability stem + `Triggers:` list (`description-field.md`).
- Multi-capability packages fail modularity audit — split or thin orchestrator + named sub-skills (`skill-modularity.md`).
- Skipping the composition plan before Write reintroduces silent reimplementation of peer skills.
- Deterministic steps written only as prose (fenced source, giant `rg` lines, multi-step mechanical sequences) fail audit — extract to `scripts/` / `workflow/` / `templates/` / `reference/` (`deterministic-elements.md`).
- Markdown `- [ ]` checklists as the agent's progress board fail audit when a task tool exists — seed tasks via `TaskCreate` / `TodoWrite` (`deterministic-elements.md`).

## When this skill applies

Trigger for requests to **build**, **improve**, or **polish** a skill. This skill orchestrates the process — it classifies, scaffolds, gathers context, delegates writing to the `skill-writer-agent` agent, and self-audits the result.

For quick skill syntax questions or one-off SKILL.md edits, spawn the `skill-writer-agent` agent directly.

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

Classify into one of 9 types — type sets folder structure. Taxonomy and layouts: [`references/skill-types.md`](references/skill-types.md).

## Principles

These are non-negotiable. Every skill must satisfy them. Enforce via [`references/self-audit-checklist.md`](references/self-audit-checklist.md).

### Concision and defaults

> "Default assumption: Claude is already very smart. Only add context Claude doesn’t already have."

> "Don’t State the Obvious — focus on information that pushes Claude out of its normal way of thinking."

Challenge each sentence: "Does Claude really need this?"

### Degree of freedom

> "Match the level of specificity to the task’s fragility and variability."

High freedom (text guidance) for open fields. Low freedom (exact scripts, no parameters) for narrow bridges with cliffs.

> "Avoid Railroading Claude — give Claude the information it needs, but give it the flexibility to adapt."

### Progressive disclosure

Hub pattern, line caps, one-level references, TOC and path rules: [`references/progressive-disclosure.md`](references/progressive-disclosure.md).

### Modularity and composition

One skill = one capability. Multi-step work invokes **sub-skills** (peer skills) by name. Prefer compose over reimplement. Full rules: [`references/skill-modularity.md`](references/skill-modularity.md).

> "You can just reference other skills by name, and the model will invoke them if they are installed."

New-skill Gather records a composition plan before write. Self-audit modularity items are mandatory.

### Description field (trigger catalog)

The frontmatter `description` is **selection metadata** pre-loaded for every skill. Write a **trigger catalog**, not a story: short capability stem + concrete trigger phrases. No narrative, benefits language, or process dump.

Full rules: [`references/description-field.md`](references/description-field.md). Polish workflow Step 1 is the dedicated rewrite pass.

> "The description field is not a summary — it’s a description of when to trigger."

### Gotchas

Mandatory highest-signal section (see Gotchas above). Capture real failure modes; self-audit requires the section present and actionable.

### Templates and examples

> "Provide templates for output format" and "Examples help Claude understand the desired style and level of detail more clearly than descriptions alone."

Use the template pattern for structured outputs. Use the examples pattern (input/output pairs) for style-dependent work.

### Workflows and task seeds

Multi-step required work is a **task seed list** (plain bullets in a reference file) plus an instruction to register each item on the host task tool (`TaskCreate`, `TodoWrite`, or equivalent). Agents work the task list and mark complete with evidence.

Do **not** ship markdown `- [ ]` boards as the completion protocol when a task tool is available. Do **not** say "copy this checklist into your response and check it off."

Quality-critical operations still use feedback loops (run validator → fix → repeat). Spec: [`references/deterministic-elements.md`](references/deterministic-elements.md) (Task-tool tracking).

### Scripts

> "Handle error conditions rather than punting to Claude." "Make clear whether Claude should execute the script or read it as reference."

> "One of the most powerful tools you can give Claude is code — letting Claude spend its turns on composition rather than reconstructing boilerplate."

### Deterministic elements (mandatory classification)

Any skill element that is **deterministic** (same inputs → same outputs; machine-checkable success) ships as code, a fixed artifact, or a **session task seed** — not prose-only steps or markdown checkbox boards. Judgment, routing, and refusals stay in markdown.

Full rules, inventory table, task-tool tracking, CODE_RULES bar for skill scripts, and anti-patterns: [`references/deterministic-elements.md`](references/deterministic-elements.md).

New-skill Gather records a deterministic-elements inventory before write. Self-audit items register as session tasks and are mandatory on every delivery (pure-judgment skills mark script rows N/A with evidence).

### Setup and memory

> "Think through the Setup — some skills may need to be set up with context from the user. A good pattern is to store this in a config.json file."

> "Data stored in the skill directory may be deleted when you upgrade the skill, so store persistent data in `${CLAUDE_PLUGIN_DATA}`."

### Constraints and refusal cases

> bugteam pattern — non-negotiables separated from guidance, with design rationale. Explicit "first match wins" refusal conditions.

### Anti-patterns

> No Windows paths. Don’t offer too many options — provide a default with escape hatch. Avoid time-sensitive claims. Use consistent terminology. No deeply nested references.

Also: story-form descriptions; monolith multi-capability skills; silent reimplementation of peer skills; nested folders used as fake sub-skills; deterministic logic only in prose or fenced source; markdown `- [ ]` as the agent's work tracker.

## Self-audit

After every build, improvement, or polish pass, load `${CLAUDE_SKILL_DIR}/references/self-audit-checklist.md`, **register every bullet as a session task**, and complete each with evidence. Every item must pass before delivery. Fix failures, then re-audit.

## Delegation to skill-writer-agent

skill-builder orchestrates; the `skill-writer-agent` agent authors. The caller spawns it with `Agent(subagent_type="skill-writer-agent", ...)`. The handoff packet from Step 4 must include:

- Skill type and folder structure
- Gap analysis or observation findings (composition plan + description triggers + deterministic inventory)
- Degree of freedom assessment
- Initial gotchas
- Composition plan: related skills, sub-skills to invoke, split decisions
- Description trigger catalog: capability stem + trigger phrases (not prose)
- Deterministic elements inventory: each process step classified; code paths + paired tests
- Any constraints

See `${CLAUDE_SKILL_DIR}/references/delegation-map.md` for exact patterns.

## File index

| File | Purpose |
|------|---------|
| `SKILL.md` | This hub — principles, process, routing, file index |
| `references/skill-types.md` | 9-type taxonomy with folder structures per type |
| `references/progressive-disclosure.md` | Folder conventions, hub pattern, hard rules |
| `references/skill-modularity.md` | Cross-skill modularity, sub-skills, composition plan |
| `references/description-field.md` | Description as trigger catalog (not story prose) |
| `references/deterministic-elements.md` | Deterministic steps as code/task seeds; CODE_RULES; no markdown checkbox boards |
| `references/self-audit-checklist.md` | Post-build audit task seeds (register via TaskCreate / TodoWrite) |
| `references/delegation-map.md` | Subagent handoff patterns and transcript guidance |
| `workflows/new-skill.md` | Full lifecycle for new skills (6 steps) |
| `workflows/improve-skill.md` | Observation-first flow for existing skills (6 steps) |
| `workflows/polish-skill.md` | Description trigger-catalog audit and final validation (5 steps) |
| `templates/gap-analysis.md` | Gaps, composition plan, description triggers, deterministic inventory |

## Folder map

- `SKILL.md` — hub.
- `references/` — best-practice specifications and the audit checklist.
- `workflows/` — step-by-step workflows for each lifecycle phase.
- `templates/` — reusable templates for skill artifacts.
