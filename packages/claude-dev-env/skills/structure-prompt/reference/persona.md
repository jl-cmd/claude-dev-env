# Persona transformation

Lead the optimized prompt with what the agent does, not who the agent is.

## Detection patterns

The persona block matches any of:
- "You are a/an `<role>`"
- "You are an expert in/at `<topic>`"
- "You are a helpful assistant"
- "Act as `<role>`"
- "Pretend to be `<role>`"
- "Imagine you are `<role>`"
- "As a/an `<role>`, …"
- "Role: `<role>`"

## Transformation

Replace the persona line with a single mission sentence stating the task in imperative form.

| Persona input | Mission output |
|---|---|
| "You are a senior security engineer. Review this PR." | "Audit this PR for security issues." |
| "Act as a code reviewer and find bugs in this code." | "Find bugs in this code." |
| "You are an expert at SQL. Write a query that…" | "Write a SQL query that…" |

## Creative-writing carve-out

The persona line stays intact when the prompt explicitly references one of these output qualities: `style`, `tone`, `voice`, `fiction`, `creative writing`, `narrative`. In that case the persona shapes the output's character and the mission line follows it.

## Disposition reporting

The persona pass MUST emit a gap note via the paste-mode or file-path-mode gap-report mechanism that [`output-contract.md`](output-contract.md) defines, recording one of two dispositions:

- `> Gap: Persona transformed — original "<persona line>" replaced with mission "<mission line>".`
- `> Gap: Persona preserved (creative-writing carve-out matched: "<matched keyword>").`

When none of the six carve-out keywords appears in the input, the persona line is always transformed. The detection is deterministic: a case-insensitive match against the six listed keywords only. No subjective "near-miss" or "intent" judgment applies. See the [no silent action](output-contract.md#disposition-invariants) invariant.
