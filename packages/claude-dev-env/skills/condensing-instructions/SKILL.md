---
name: condensing-instructions
description: >-
  Refine an instruction document for Claude 5 generation models: cut rules the
  model's judgment already covers, move detail behind progressive disclosure,
  and route each remaining piece to the system prompt, CLAUDE.md, a skill, or a
  reference. Use for system prompts, CLAUDE.md files, skills, tool
  descriptions, agent instructions, context engineering, prompt slimming, and
  token reduction.
---

# Condensing Instructions

Cut an instruction document to what a Claude 5 generation model needs, and move the rest to the surface that loads it on demand. Over 80% of Claude Code's system prompt came out for Claude Opus 5 and Claude Fable 5 with no measurable drop in performance, so treat a long instruction document as a place with room to cut.

## Clear the conflicts first

Read the system prompt, the CLAUDE.md, and the skills as one body of text and find the lines that pull against each other — "leave documentation as appropriate" sitting beside "DO NOT add comments". A conflict makes the model deliberate at length before it acts. Resolve each pair into one statement, or delete both when neither changes what the model does.

## Trade rules for judgment

Delete a rule written to block a worst case, such as file deletion. Claude 5 generation models read the surrounding context and decide well without it, and a rigid rule blocks the user who has a real reason to want the behavior it forbids.

State the outcome and the signal the model should read:

- Cut: "Default to writing no comments. Never write multi-paragraph docstrings or multi-line comment blocks — one short line max. Don't create planning, decision, or analysis documents unless the user asks for them."
- Keep: "Write code that reads like the surrounding code: match its comment density, naming, and idiom."

## Design the interface in place of examples

Examples constrain exploration. Carry usage in the tool's own shape: expressive names, expressive parameters, and types that signal intent. A status parameter enumerated as `pending`, `in_progress`, `completed` shows correct use with no example attached.

## Load detail at the point of use

Move detail out of always-on text and into a surface the model reaches for:

- A skill the model calls when the task calls for it. Code review and verification detail belongs here.
- A linked file the model opens on demand.
- A tool with deferred loading, where the model searches for the definition before it uses the tool.

Keep the always-on context lean and let the model pull the rest.

## Say each thing once

Put tool usage guidance in the tool description alone. Delete the copy that repeats it in the system prompt.

## Let memory carry session facts

Claude's automatic memory captures relevant context and carries it across sessions. Delete hand-written memory notes from CLAUDE.md when memory already holds them.

## Point at rich references

Include files as references with @mentions. Prefer a reference the model can read with no ambiguity, in this order:

1. Code from this or another codebase — the highest fidelity specification available.
2. A test suite that pins the behavior.
3. An HTML artifact or a mockup.
4. A rubric, which lets a verification agent score work against a quality standard.
5. Prose description or a screenshot.

## Route what remains

| Surface | What belongs there |
|---|---|
| System prompt | The product Claude works within and the role it plays. For a custom agent, spend real effort here. |
| CLAUDE.md | A short line on what the repository is, then the gotchas found inside the codebase. Drop anything the model can read off the file structure. Link to skills for the detail. |
| Skills | Opinions, knowledge, and practices particular to your team or product, written as a guide the model consults. Split a long skill into several files. Constrain only where it matters. |
| References | Specs, mockups, and codebases pulled in by @mention. |

## Deliver

Rewrite the document in place and report what moved to which surface. Offer `claude doctor` as a follow-up pass — it rightsizes skills and CLAUDE.md files against these same rules.
