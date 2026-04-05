---
name: anthropic-plan
description: Structured implementation planning through readonly codebase exploration before any code changes. Produces a plan file for approval. Use when the user says /anthropic-plan, "plan this first", "think before coding", "explore before implementing", "make a plan", or when approaching non-trivial tasks that benefit from upfront exploration and design. Also triggers on "what would the approach be", "scope this out", or "don't code yet, just plan".
---

# Claude Plan

Explore the codebase, design an approach, and write a plan file -- all without touching production code.

## Why

Jumping straight to code on non-trivial tasks leads to wasted effort when the approach conflicts with existing patterns, misses reusable code, or misunderstands the user's intent. This skill enforces "look before you leap": explore first, design second, write the plan third, get approval last. No code changes until the user says go.

## Constraints

Treat the codebase as readonly throughout this skill. The only file you may create or edit is the plan file.

**Allowed:** Read files, Grep, Glob, launch Explore agents, launch Plan agents, write/edit the plan file, AskUserQuestion for clarification.

**Not allowed:** Edit source files, Write new source files, run tests, install packages, run non-readonly Bash commands, or make any system changes.

This discipline exists because the user invoked this skill specifically to understand the approach before committing to it. Violating readonly would undermine the whole point.

## Plan File

Write to `~/.claude/plans/<slug>.md`.

Generate the slug from the task -- descriptive, kebab-case, 2-4 words. Examples: `add-user-auth.md`, `fix-payment-retry.md`, `refactor-config-loading.md`. Avoid the random-word convention used by built-in plan mode.

**Announce at start:** "Planning: `<slug>` -- exploring before writing code."

## Workflow

### Phase 1: Explore

Understand the problem space before proposing solutions. Launch Explore agents in parallel -- up to 3, but use the minimum needed. Quality over quantity.

What to look for:
- Files and modules the task will touch
- Existing patterns for similar functionality
- Utilities, helpers, constants, and shared code to reuse
- Test patterns already in place

Skip this phase only if the task is trivial and full context already exists in the conversation.

### Phase 2: Design

Launch Plan agent(s) to design the implementation -- up to 3 for complex or multi-area tasks, skip entirely for trivial tasks. Feed them comprehensive context from Phase 1; they cannot explore on their own, so everything they need must come from you.

### Phase 3: Review

Before committing to the plan:
- Read the critical files yourself to verify the agents got it right
- Check alignment with what the user actually asked for
- If requirements are ambiguous, use AskUserQuestion now -- not after writing the plan

### Phase 4: Write the Plan

Write incrementally as you learn things in Phases 1-3, then refine here. The plan file has these sections:

```markdown
## Context
Why this change is needed, what problem it solves, what the outcome looks like.

## Approach
The recommended implementation. One approach, not a menu of alternatives.
Concise but detailed enough to execute without re-exploring.

## Files
Critical file paths that will be created or modified.

## Reuse
Existing functions, utilities, constants, or patterns to leverage.
Include file:line references so the implementer can find them instantly.

## Steps
Ordered implementation steps. Each step is a discrete, testable unit of work.

## Verification
How to confirm end-to-end that the implementation works.
Specific commands, test files, or manual verification steps.

## Bash Permissions
Semantic descriptions of bash actions the implementation will need:
- "run tests"
- "install dependencies"
- "start dev server"
These are action descriptions, not specific commands.
```

### Phase 5: Present for Approval

Use AskUserQuestion to present the completed plan. Do not ask about approval in regular text -- always use AskUserQuestion so the user gets a clear, structured decision point.

Options:
- **Approve** -- proceed with implementation
- **Revise** -- user has feedback to incorporate
- **Cancel** -- abandon the plan

## Scaling

Not every task needs all five phases. Match effort to complexity:

- **Trivial** (rename, typo fix): Ask if a formal plan is even wanted. If yes, skip Phases 1-2, write a minimal plan.
- **Small** (single-file change, clear scope): One Explore agent, skip Design phase, concise plan.
- **Medium** (multi-file feature, some ambiguity): Full workflow, 1-2 agents per phase.
- **Large** (cross-cutting change, architectural): Full workflow, max agents, thorough Review phase.
