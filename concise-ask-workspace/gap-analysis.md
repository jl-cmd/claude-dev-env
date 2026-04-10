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

- **Primary pain:** **Late signal under early noise** — the reply is long and dense up front, and the sentence that actually answers the user shows up late. The answer may still be correct; it is just hard to find.
- **Secondary pain:** **Multi-part or under-specified prompts** — a **staged reply** works better: answer the most important part first, list what you are leaving for later, **or** use one short **structured disambiguation** round (`AskUserQuestion` / `AskQuestion`) so the next reply stays on one track.
- **Where to encode behavior:** Put the contract in a **Claude skill or rule** (Markdown under `.claude/`, e.g. `SKILL.md`). Prefer `.md` for Claude; `.mdc` is optional.

## Candidate eval scenarios

Use these as checklists when judging whether a reply matches **concise ask mode**.

- **Gather evidence first (all scenarios):** Before asking the user to paste a file, confirm a branch, or run something for you, use whatever is available—read the repo, search the codebase, run safe local commands, use MCP or other tools—to find logs, configs, and paths yourself. Ask the user only for what is **not** obtainable that way (secrets, production-only systems, machine-local state you cannot reach).

### 1. Single, clear question

- **What the user did:** Asked one focused question (not “explain everything”).
- **What the reply should do:** Start with the direct answer to that question. The first screenful should stay on that question.
- **What to defer:** Long tutorials, history, and edge cases until the user asks for more or the question wording clearly asks for a wide overview.

### 2. User wants more depth

- **What the user did:** Asked for more (“more detail,” “explain the rest,” “go deeper”) or finished answering a clarification you ran.
- **What the reply should do:** Expand in scope and length **now** — this turn is the right place for the longer explanation.

### 3. Bundled or multi-part prompt

- **What the user did:** Packed several questions or topics into one message.
- **What the reply should do:** Either (a) answer the **most important** part first and briefly name the other parts you will cover next or skipped, or (b) run **one** `AskUserQuestion` / `AskQuestion` round so they pick which part comes first, then answer that part tightly.
- **What to defer:** A single huge reply that answers every sub-topic at full length — save that for when they explicitly want the full tour.

### 4. Missing grounding

- **What the user did:** Asked something that depends on files, logs, or configs that are **not** in the thread (so any confident answer would be guesswork).
- **What the reply should do:** **First**, try to pull what you need from the workspace and tools (open likely paths, search, run read-only or safe commands). **If** it is still missing after that, run structured clarification: labeled choices or a tool flow so they attach the right artifact or pick the right scenario. **Then** answer from what is now in thread.
- **What to defer:** Long speculative narrative until you have either self-served the facts or the user supplied what tools cannot reach.

### 5. Partial confidence

- **What the user did:** Asked a question where you can answer **part** of it firmly but **not** the whole thing from what you see.
- **What the reply should do:** **First**, try to close the gap yourself the same way—targeted reads, search, checks you can run—so “what would resolve it” is something you already attempted. **If** uncertainty remains, say **which part** is still open in plain terms and name **what would still resolve it**, preferring items only the user or their environment can provide (e.g. secret values, a service only they can hit) over things you could have looked up.
- **What to defer:** Extra background on related topics in the same message. If they need more context, they can ask in a follow-up; keep this reply short and honest about limits.
