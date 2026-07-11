# deep-research

Runs an iterative multi-source research pipeline that produces a comprehensive Obsidian report with citations. Triggered by `/deep-research [topic]`.

## Purpose

The skill operates in two phases. Phase 1 (main thread) turns the raw topic into a precise research brief through a short AskUserQuestion session covering audience, scope, recency, and depth. Phase 2 delegates to the `deep-research` agent with the confirmed brief and an iteration budget (8 / 15 / 25 based on depth preference). The agent handles iteration, state tracking, and Obsidian output.

## Key file

| File | Purpose |
|---|---|
| `SKILL.md` | Phase 1 steps (classify, ask, construct `<research_brief>` XML, set iteration budget) and Phase 2 spawn instructions, including `mode: bypassPermissions` for unrestricted web access. |

## Post-run cleanup

After the agent returns, the skill summarizes the Obsidian path, source counts, and any gaps, then deletes the `.deep-research-state.md` temp file.
