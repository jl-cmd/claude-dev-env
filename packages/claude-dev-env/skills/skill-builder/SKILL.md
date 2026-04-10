---
name: skill-builder
description: >-
  Orchestrates the complete skill-building lifecycle using evaluation-driven
  development. Routes through gap analysis, eval creation, skill writing (via
  skill-writer), subagent testing (via skill-creator infrastructure), and
  iterative refinement. Use when creating new skills, improving existing skills,
  or optimizing skill descriptions. Triggers: 'build a skill', 'new skill
  workflow', 'improve this skill', 'optimize skill description', 'skill
  development lifecycle'.
---

@${CLAUDE_SKILL_DIR}/references/eval-driven-flow.md

# Skill Builder

**Core principle:** Evaluation-driven development. Build evals BEFORE writing extensive documentation. This ensures skills solve real problems rather than documenting imagined ones.

Source: [Anthropic Skill Best Practices - Evaluation and Iteration](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#evaluation-and-iteration)

## When this skill applies

Trigger for requests to **build**, **improve**, or **polish** a skill through the full evaluation-driven lifecycle. This skill orchestrates the process -- it delegates writing to `/skill-writer` and evaluation infrastructure to the `skill-creator` plugin.

For quick skill syntax questions or one-off SKILL.md edits, use `/skill-writer` directly instead.

## Routing

Assess the user's intent from conversation context and existing artifacts. Route directly:

**Creating a new skill?**
Read `${CLAUDE_SKILL_DIR}/workflows/new-skill.md` and follow it.

**Improving an existing skill?**
Read `${CLAUDE_SKILL_DIR}/workflows/improve-skill.md` and follow it.

**Final polish only (description optimization, trigger eval)?**
Read `${CLAUDE_SKILL_DIR}/workflows/polish-skill.md` and follow it.

**Ambiguous?** Ask: "Are you creating a new skill, improving an existing one, or doing a final polish pass?"

## The Claude A / Claude B Pattern

You and the user are **Claude A** -- the expert who designs and refines the skill. Subagents running the built skill on eval tasks are **Claude B** -- the agent using the skill to perform real work.

> "Work with one instance of Claude ('Claude A') to create a Skill that is used by other instances ('Claude B'). Claude A helps you design and refine instructions, while Claude B tests them in real tasks."

The feedback loop: observe Claude B's behavior, bring insights back, refine the skill, test again.

## Phase Overview

| Phase | Purpose | Delegated To |
|-------|---------|-------------|
| 1. Identify gaps | Document what fails without the skill | This skill (guided conversation) |
| 2. Build evals | Create 3+ scenarios testing the gaps | This skill (templates + user input) |
| 3. Write skill | Minimal instructions addressing gaps | `/skill-writer` |
| 4. Test | Subagent runs with/without skill, grade, benchmark | `skill-creator` eval infrastructure |
| 5. Iterate | Review results, refine, re-test | This skill + `/skill-writer` + Phase 4 |
| 6. Polish | Description optimization, trigger eval, final check | `skill-creator` description optimizer |

## Principles (apply across all phases)

1. **Evals before documentation.** Never write extensive skill content without evaluation scenarios to validate it.

2. **Minimal instructions first.** Write just enough to pass evaluations. Resist the urge to over-document.

3. **Generalize from feedback.** The skill will be used across many prompts. Do not overfit to test cases.

4. **Explain the why.** Theory of mind beats rigid rules. Help the model understand reasoning, not just constraints.

5. **Observe, do not assume.** Iterate based on what Claude B actually does, not what you think it should do.

## Delegation Details

See `${CLAUDE_SKILL_DIR}/references/delegation-map.md` for exact invocation patterns and integration points between this orchestrator, `/skill-writer`, and `skill-creator`.

## File Index

| File | Purpose |
|------|---------|
| `workflows/new-skill.md` | Full lifecycle for new skills (6 phases) |
| `workflows/improve-skill.md` | Observation-first flow for existing skills |
| `workflows/polish-skill.md` | Description optimization and final validation |
| `references/eval-driven-flow.md` | Official Anthropic methodology with citations |
| `references/delegation-map.md` | Integration map for skill-writer and skill-creator |
| `templates/gap-analysis.md` | Template for Phase 1 gap documentation |
| `templates/eval-scenario.json` | Eval template matching skill-creator schema |
