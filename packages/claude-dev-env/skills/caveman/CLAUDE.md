# caveman

Trims noise from conversational text in the current turn. Triggered by `/caveman`, `caveman this`, `trim this`, `make it terse`, or `caveman voice`.

## Purpose

The inline counterpart to the `caveman` agent. When the user wants preamble, hedging, filler transitions, restatements, empty future-proofing, dead examples, or pleasantries stripped from the last assistant message or from text passed as an argument, this skill performs the trim directly in the main session — no `Agent` spawn. The entire reply is the trimmed text; no report, no commentary about what was cut.

Use the `caveman` agent (`subagent_type: caveman`) when the input is a file path, a multi-section artifact that needs a structured report, or a delegated workflow.

## Key file

| File | Purpose |
|---|---|
| `SKILL.md` | Instructions: resolve the source (argument or prior message), noise categories to cut, what to preserve verbatim, and the escape hatch for load-bearing spans. |
