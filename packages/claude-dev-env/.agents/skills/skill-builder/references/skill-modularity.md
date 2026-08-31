# Skill modularity and composition

Source: [Lessons from Building Claude Code](thariq-x-post-skills.json) — Composing Skills; skill type notes on skill dependencies; Anthropic progressive disclosure (within-skill layering).

## Two modularity layers

| Layer | What it controls | Where enforced |
|---|---|---|
| **Within skill** | SKILL.md stays a hub; detail lives in companion files | `progressive-disclosure.md`, self-audit line-cap items |
| **Across skills** | One skill = one capability; multi-step work invokes sibling skills by name | This file, self-audit modularity items, new/improve workflows |

Both layers apply. Progressive disclosure alone does not make a multi-capability skill modular.

## Core rules

### One capability per skill

A skill owns **one** clear job a user can name in one sentence. Signals it is too large:

- Description needs "and" for unrelated jobs
- Process has independent branches that never share gotchas or scripts
- Claude B only ever needs half the package for a typical task
- Gotchas cluster into two or more unrelated failure domains

When those hold, split or restructure as an orchestrator + sub-skills (below).

### Compose by name (sub-skills)

> "You can just reference other skills by name, and the model will invoke them if they are installed."

There is no native dependency installer. Composition works by:

1. Naming the sibling skill (`/skill-name` or the skill's trigger description).
2. Stating **when** to invoke it (which process step).
3. Stating **what** it must produce for the next step.
4. Stating what to do if it is missing (refuse, degrade, or ask the user).

**Sub-skill** means a focused skill another skill invokes — not a nested folder inside the parent package. Sub-skills are peer skills in the skill library.

### Prefer invoke over reimplement

When an existing skill already owns a step (PR scope resolve, self-audit handoff pattern, commit protocol, etc.), the new skill **names and invokes** that skill. It does not paste a second copy of that process into its own SKILL.md.

Exception: the existing skill is wrong for this domain, and the gap analysis records why a local procedure is required.

### Orchestrator skills

Some capabilities are multi-step by nature (lifecycle skills, PR loops). The modular shape is:

```
orchestrator-skill/          # thin: routing, order, refusal, handoff packets
  SKILL.md                   # invokes named sub-skills at each step
sibling-skill-a/             # one capability
sibling-skill-b/             # one capability
```

The orchestrator owns sequence and gates. Sub-skills own domain detail. skill-builder itself follows this shape: it orchestrates and delegates writing to the `skill-writer-agent` agent (spawned via the Agent tool).

### Within-skill vs split

| Situation | Choice |
|---|---|
| One capability, large reference surface | Stay one skill; use progressive disclosure |
| Two capabilities that users invoke separately | Two skills |
| Multi-step workflow that always runs end-to-end | Orchestrator skill + named sub-skills for reusable steps |
| Overlap with an existing skill | Shrink the new skill; invoke the existing one; tighten both descriptions |

## Composition plan (required before write)

Every new skill and every improve pass that changes scope records a composition plan in the gap analysis:

1. **Capability sentence** — one job.
2. **Related skills inventory** — existing skills that touch the same domain (scan installed skills and the package tree).
3. **Reuse** — which steps invoke which skills.
4. **Split** — if more than one capability, list the skills to create or keep separate.
5. **Missing** — sub-skills that do not exist yet (build them first or as sibling packages in the same change).

## How to document sub-skills in SKILL.md

In Process or a dedicated **Sub-skills** section:

```markdown
## Sub-skills

| Skill | When | Produces |
|---|---|---|
| `/reviewer-gates` | Step 1 — gate external reviewers | opt-out, Copilot quota, Bugbot trigger decisions |

If a listed skill is not installed, respond: `[exact refusal or degrade line]`.
```

Self-audit requires this table (or equivalent) whenever the skill composes others. skill-builder itself delegates SKILL.md authoring to the `skill-writer-agent` agent, spawned via the Agent tool.

## Anti-patterns

- **Monolith skill** — one package that reimplements commit, review, deploy, and logging under one description.
- **Silent reimplementation** — copy-pasted steps from another skill with no name reference.
- **Folder nesting as composition** — burying a second skill's content under `workflows/` instead of a real sibling skill the model can select.
- **Vague dependency** — "use other skills as needed" with no names, when, or outputs.
- **Redundant twin** — a new skill whose description overlaps an existing one without a refusal boundary.

## Task seeds for authors

Register each item as a session task during new-skill Gather and improve Diagnose (`TaskCreate` / `TodoWrite`). Complete with evidence. Do not track as markdown checkboxes.

- Capability fits one sentence without an unrelated "and"
- Related skills scanned; inventory written
- Reusable steps map to named skills (or justify local procedure)
- Multi-capability work is split or is an orchestrator with sub-skills
- SKILL.md will name each sub-skill with when + produces + missing behavior

