# Gap Analysis: Concise Ask Mode (focused replies)

## Task Description

A **simple question** calls for a **leading answer**: open with the lines that match the user’s stated ask, at depth proportional to that ask, then offer a clear path to more detail when the user signals they want it. Many sessions drift into **breadth-first** openings—tutorials, adjacent topics, full context—so the matching answer lands late inside a long block and costs extra scanning to extract. **Relevance first** means anchor the opening to the user’s words, scale depth to the ask, and stage breadth behind an explicit invitation or a clearly broad prompt.

## Gaps Identified

### Gap 1: Opening drifts ahead of the ask

- **What happened:** The reply opens with wide context: edge cases, neighboring topics, background—before the line that maps directly to the user’s wording. The body feels thorough; the **first clear match to the question** arrives deep in the stack or only after several paragraphs.
- **What was needed:** **Lead with the line that answers the user’s ask.** Add breadth after the user asks for it, after clarification resolves intent, or when the prompt itself clearly demands a wide scope. When intent splinters, **disambiguate with minimal friction** (Claude `AskUserQuestion`, Cursor `AskQuestion`) so one round picks the interpretation; follow with one tight reply to that choice.
- **Frequency:** Shows up across question types whenever default assistant style favors comprehensive openings and focused reply shape has yet to load from rules or skills.
- **Example task:** You ask one concrete thing about **Galaxy Store theme submission automation** (a single step or failure mode); the reply opens with a full pipeline tour, portal background, and tooling catalog before the line about your step.

### Gap 2: Thin grounding, confident tone

- **What happened:** The model answers with high confidence while logs, paths, configs, or thread-visible artifacts sit outside the thread, so the story rests on inference.
- **What was needed:** When key artifacts are missing, **run structured clarification** (`AskUserQuestion` / `AskQuestion`) so the user selects what to attach or which scenario applies. Write the clarification for fast answers; use as many words as clarity requires.
- **Frequency:** Whenever the correct answer depends on specifics outside the current context.
- **Example task:** “Why is DATABASE_URL empty in CI?” while workflow YAML and log excerpts remain outside the thread—offer labeled choices for which artifact to paste next, then answer from that material.

## Patterns

- **Primary pain:** **Late signal under early noise**—length and density land before the line that matches the ask; the eventual claim can still be accurate.
- **Secondary pain:** Multi-part prompts or thin context reward a **staged reply**: answer the highest-impact part first, name deferred parts, **or** run a **short structured disambiguation** (`AskUserQuestion` / `AskQuestion`) so the next turn stays scoped.
- **Where to encode behavior:** Capture the contract as a **Claude skill or rule in Markdown** under `.claude/` (for example `SKILL.md`). Deliver `.md` artifacts for Claude; treat `.mdc` as optional.

## Candidate Eval Scenarios

- **Single, clear question** → Open with the direct answer to that question; keep the first block scoped to that ask; add tutorial depth only after the user requests it or the ask clearly spans tutorial-scale scope.
- **User wants more depth** → Expand after explicit signals (“more,” “details,” “explain the rest”) or after clarification answers land.
- **Bundled or multi-part prompt** → Answer the highest-priority part first while naming deferred parts, **or** run `AskUserQuestion` / `AskQuestion` to pick which part leads; default path stays staged or clarified; reserve wall-of-text, all-topic replies for explicit user requests.
- **Missing grounding** → Run structured clarification (tool flow or labeled choices) first; draft the long narrative only after artifacts or choices are in thread.
- **Partial confidence** → State the uncertain slice and the artifact or check that would confirm it; park adjacent background for a follow-up turn or an explicit depth request.
