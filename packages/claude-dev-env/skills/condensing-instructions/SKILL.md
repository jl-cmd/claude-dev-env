---
name: condensing-instructions
description: >-
  Compress instruction text without changing its contract. Triggers: shorten
  prompts, optimize instructions for LLMs, condense skills, compact reference
  docs, rewrite operational specifications, preserve requirements while reducing
  tokens.
---

# Condensing Instructions

Rewrite supplied instructions into a substantially shorter operational specification for LLM consumption.

## Rules

- Preserve every behaviorally meaningful requirement, safety rule, constraint, exact identifier, URL, name, condition, exception, and output requirement.
- Remove rationale, history, background, repetition, conversational framing, unnecessary structure, and examples unless an example defines required behavior.
- Merge instructions with the same purpose, state shared defaults once, replace descriptive prose with direct instructions, combine related requirements, and organize by function rather than source order.
- Keep wording that affects execution, safety, accuracy, scope, conditions, exceptions, or output. Do not omit requirements, weaken constraints, replace precise instructions with vague shorthand, invent behavior, or preserve unnecessary structure.
- Use short declarative paragraphs or compact sections. Produce a compact operational specification, not an essay or explanation.

## When This Applies

Use for prompts, skills, reference documentation, runbooks, policies, and other instruction text intended for LLMs. If no clear instruction text is supplied, respond exactly: `Provide the instructions to condense.`

## Output

Output only the rewritten instructions. Do not add commentary about the rewrite.

Before responding, verify that every requirement in the supplied instructions is represented.

## Process Classification

The workflow is judgment-based: identify meaningful requirements, remove nonfunctional prose, restructure, and perform a requirement-preservation check. No scripts, dependencies, persistent state, sub-skills, or external tools are required.

## File Index

| File | Purpose |
|---|---|
| `SKILL.md` | Condensing workflow and output contract |

## Folder Map

- `condensing-instructions/` — the complete skill package.

## Gotchas

- Compression must not remove a constraint merely because it looks repetitive or obvious.
- Exact strings, paths, URLs, names, identifiers, conditions, exceptions, and output formats are immutable.
- “Shorter” permits restructuring and merging, not semantic generalization.
