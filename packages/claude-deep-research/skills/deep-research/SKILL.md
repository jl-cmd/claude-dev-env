---
name: deep-research
description: "Deep Research mode — iterative multi-source research producing comprehensive Obsidian reports with citations. Official-docs-first methodology. Triggers: '/deep-research [topic]'"
argument-hint: "TOPIC or RESEARCH QUESTION"
---

# Deep Research

You orchestrate a two-phase deep research pipeline. Phase 1 happens here (main thread). Phase 2 is delegated to the `deep-research` agent.

## Phase 1: Build the Research Prompt (Interactive Q&A)

The user's raw topic is: `$ARGUMENTS`

Your job is to turn this raw topic into a precise, well-scoped research brief using prompt-generator methodology. Follow these steps:

### Step 1: Classify and assess

Silently determine:
- **Complexity**: Is this a narrow factual question or a broad landscape survey?
- **Ambiguity**: Can you research this as-is, or does it need scoping?
- **Official docs**: Does this topic have official vendor/creator documentation? If yes, that is the primary source and must be consulted first.

### Step 2: Ask clarifying questions

Use AskUserQuestion to ask 1-3 questions. Choose from these dimensions based on what's genuinely unclear — skip any that are obvious from context:

- **Audience**: "Who is this research for?" (options: technical deep-dive, executive summary, personal learning, decision support)
- **Scope**: "Should I focus on a specific angle or survey the full landscape?" (options: specific angle with description field, broad survey, compare specific alternatives)
- **Recency**: "How important is recency?" (options: last 6 months only, last 1-2 years, historical overview, doesn't matter)
- **Depth**: "How deep should this go?" (options: quick overview 5-10 sources, standard 15-20 sources, exhaustive 25+ sources)

Skip clarification entirely only if the topic is already narrow, unambiguous, and the audience is obvious.

### Step 3: Construct the research brief

From the user's answers, write a structured research brief:

```
<research_brief>
  <topic>The original topic, cleaned up</topic>
  <official_docs>Known official documentation sources, or "none identified" if the topic lacks vendor docs</official_docs>
  <scope>Exactly what to research — boundaries, inclusions, exclusions</scope>
  <audience>Who this is for and what they need</audience>
  <depth>Target source count and iteration budget</depth>
  <output>What the final deliverable looks like</output>
  <key_questions>
    1. Specific question the research must answer
    2. Another specific question
    3. ...
  </key_questions>
</research_brief>
```

Show the brief to the user. Ask: "Does this capture what you need, or should I adjust the scope?"

### Step 4: Set iteration budget

Map the user's depth preference to iteration count:
- Quick overview: 8 iterations
- Standard (default): 15 iterations
- Exhaustive: 25 iterations

## Phase 2: Launch the Research Agent

Once the brief is confirmed, spawn the `deep-research` agent using the Agent tool with:

- **subagent_type**: `deep-research`
- **prompt**: The full `<research_brief>` XML block from Step 3, plus the iteration budget
- **mode**: `bypassPermissions` (research agent needs unrestricted tool access for web searches)
- **description**: "Deep research: [short topic summary]"

The agent handles everything from here: iteration, state tracking, and Obsidian output.

When the agent returns, summarize:
1. Where the report was saved (Obsidian path)
2. How many sources were consulted (official vs secondary)
3. Any gaps or limitations noted

Then clean up temporary files: `.deep-research-state.md`
