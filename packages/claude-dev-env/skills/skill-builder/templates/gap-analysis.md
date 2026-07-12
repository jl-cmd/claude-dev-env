# Gap Analysis: [Skill Name]

## Skill Type

[One of the 9 types from skill-types.md. Determines folder structure.]

## Task Description

[One capability sentence — the single job this skill owns]

## Degree of Freedom

[High | Medium | Low] — [Reasoning based on task fragility and variability]

## Composition Plan

See `references/skill-modularity.md`.

- **Capability sentence:** [one job, no unrelated "and"]
- **Related skills inventory:** [skill → keep separate | invoke as sub-skill | absorb + reason]
- **Sub-skills to invoke:** [name → when → produces → missing behavior]
- **Split or orchestrator:** [one leaf skill | several skills | thin orchestrator + peers]
- **Missing sub-skills to create:** [names to build first or as siblings]

## Description Triggers

See `references/description-field.md`. Not story prose.

- **Capability stem tokens:** [5–20 words]
- **Trigger phrases:** [comma-separated phrases, slash forms, file types]
- **Near-miss exclusions:** [tokens that must not select this skill]
- **Draft description string:**

```yaml
description: >-
  <stem>. Triggers: <phrases>.
```

## Gaps Identified

### Gap 1: [Descriptive Name]

- **What happened:** [Description of the failure or missing context when working without a skill]
- **What was needed:** [The specific context, instruction, or knowledge that would fix it]
- **Frequency:** [How often this comes up in real usage]
- **Example task:** [A concrete task that exposes this gap]

### Gap 2: [Descriptive Name]

- **What happened:** [Description]
- **What was needed:** [Context/instruction needed]
- **Frequency:** [Frequency]
- **Example task:** [Concrete example]

### Gap 3: [Descriptive Name]

- **What happened:** [Description]
- **What was needed:** [Context/instruction needed]
- **Frequency:** [Frequency]
- **Example task:** [Concrete example]

## Patterns

- [Recurring themes across gaps — e.g., "Claude consistently lacks knowledge about X"]
- [Common failure modes — e.g., "Without guidance, Claude chooses library A when library B is required"]
- [Context that was repeatedly provided manually]

## Initial Gotcha Candidates

- [Failure pattern distilled to one line — "Claude will try to use X when it should use Y"]
- [Another failure pattern — "Without explicit instruction, Claude skips the validation step"]
- [Edge case that could become a gotcha]
