# Explore Thoroughly

Source: [Anthropic - Overthinking and Excessive Thoroughness](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#overthinking-and-excessive-thoroughness)

Note: This deliberately chooses exploration depth over the "commit and execute quickly" pattern from the same source. Thorough upfront exploration is preferred for the intended workflow.

## Before committing to an approach

- Read the relevant files. Understand what exists before proposing what to change.
- Map the existing patterns: naming conventions, file organization, architectural decisions.
- Identify constraints that could invalidate an approach before investing effort in it.
- For unfamiliar codebases or high-stakes changes, invest more time exploring than feels necessary.

## Exploration scales with risk

- Small change to a familiar file: a quick read of the file and its immediate neighbors is sufficient.
- New feature or cross-cutting change: read broadly across the codebase to understand how similar things are done.
- Architectural decision: explore the full landscape before recommending a direction.

## Inside an autonomous run

The depth budget shrinks once the evidence is in hand. When you can already name the files, the constraints, and what success looks like, further reading buys nothing — act. Re-reading a file to re-derive a fact the run already settled is the shape to cut. See [`long-horizon-autonomy.md`](long-horizon-autonomy.md).

## Relationship to other rules

- **conservative-action.md** gates *whether* to act. This rule governs *how deeply* to investigate.
- **research-mode.md** ensures factual claims are grounded. This rule ensures implementation plans are grounded in the actual codebase.
