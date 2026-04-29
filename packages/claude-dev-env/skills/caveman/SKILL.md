---
name: caveman
description: "Inline counterpart to the caveman agent — trim noise from `$ARGUMENTS` (or the previous assistant message) and reply with the trimmed text only, no report, no Agent spawn. Triggers: /caveman, caveman this, trim this, make it terse, caveman voice."
argument-hint: "[text to trim, or omit and the model uses the previous assistant message]"
---

# Caveman

Inline counterpart to the `caveman` agent at `packages/claude-dev-env/agents/caveman.md`. Use this skill when the trim target is conversational text in the current turn rather than a separate file or multi-section artifact. The model performs the trim itself in the next reply — no `Agent` invocation, no structured report, just the trimmed text.

## Instructions

1. **Resolve the source.** If `$ARGUMENTS` is non-empty, that text is the trim source. Otherwise the source is the previous assistant message in the current conversation.

2. **Trim the same noise categories the agent trims:**

   | Noise type | Example |
   |---|---|
   | Preamble / recap | "As discussed above, this skill will..." |
   | Hedging | "This might, in some cases, potentially..." |
   | Filler transitions | "Now, moving on to..." / "It's worth noting that..." |
   | Restatement | the same point made twice in different words |
   | Empty future-proofing | parameters, sections, or fields with no current consumer |
   | Dead examples | examples that duplicate another example without adding coverage |
   | Pleasantries | "Hope this helps." / "Feel free to..." |
   | Vague qualifiers | "various", "several", "a number of" — replace with the actual count or cut |

3. **Preserve verbatim:** code, commands, paths, URLs, errors, JSON, schemas, frontmatter, counts, version strings, identifiers, safety/destructive-op language, and anything the user explicitly flagged as keep-as-is.

4. **Output only the trimmed text.** No `trimmed / removed / preserved-verbatim / flagged` report. No commentary about what was cut. No preamble like "Here is the trimmed version:". The trimmed text is the entire reply.

## Escape hatch

If trimming would drop a safety warning, collapse a deliberate distinction, or you are unsure whether a span is load-bearing, leave that span in place verbatim. Do not flag, narrate, or ask about the preserved span — instruction 4 still applies, so the trimmed text (with the preserved span included) remains the entire reply. Terse is for noise, not for substance.

## When NOT to use

Use the `caveman` agent (via `Task` / `Agent` tool with `subagent_type: caveman`) when the input is a file path, a multi-section artifact requiring the structured `trimmed / removed / preserved-verbatim / flagged` report, or any delegated workflow. This skill is for inline conversational text only.
