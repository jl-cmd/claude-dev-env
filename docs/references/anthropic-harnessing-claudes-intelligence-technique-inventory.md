# Overview

Generative systems like Claude are “grown” more than hand-assembled, so **agent harnesses encode time-stamped assumptions** about what the model cannot do alone—assumptions that go stale as capabilities improve. The post argues teams should **revisit harness design** on each capability step-change while balancing intelligence, latency, and cost. It organizes guidance into **three patterns**: prefer **tools and compositions the model already masters** (especially bash and a text editor, extended into skills, programmatic calling, and memory); **question what orchestration, context loading, and memory logic the harness can stop owning** as the model can filter outputs, progressively load skills, edit context, fork subagents, compact, and persist to files; and **set boundaries deliberately** via caching-aware packaging, declarative tools for security/UX/observability, and ongoing pruning of “dead weight” compensations.

---

# Pattern 1 — Use what Claude knows

### Technique: Build on bash and text-editor tool literacy

**Practice:** Ship agent experiences around **general tools Claude already uses well**—notably **bash** and a **text editor** for viewing, creating, and editing files—rather than inventing parallel abstractions when the model’s training trajectory already favors these primitives. Treat **Claude Code** as an existence proof: it is grounded in the same tools.

**Mechanism:** **Bash tool**, **text editor tool**, **SWE-bench Verified** as an external benchmark reference; **Claude Code** as product alignment.

**Payoff:** The article ties this to **keeping pace with a model that “gets better at using” familiar tools over time** and to strong **coding/agent** benchmark results with minimal specialized surface area (49% SWE-bench Verified for Claude 3.5 Sonnet with only bash + editor, described as then state of the art).

**Anchor:** Section **“1. Use what Claude knows”** — *“We suggest building applications using tools that Claude understands well.”*

---

### Technique: Compose higher-level agent features from the same primitives

**Practice:** When you need **Agent Skills**, **programmatic tool calling**, or **the memory tool**, design them as **layers on top of** bash and the text editor rather than as unrelated subsystems—so the harness reuses the model’s strongest operational vocabulary.

**Mechanism:** **Agent Skills** (agentskills.io link in article), **programmatic tool calling**, **memory tool**, all explicitly framed as built from **bash + text editor**.

**Payoff:** Implied **coherence and leverage**: the model’s improving skill on general tools lifts composed patterns together (the article’s caption states the composition fact directly).

**Anchor:** Verbatim caption — *“Programmatic tool calling, skills, and memory are compositions of our bash and text editor tools.”*

---

# Pattern 2 — Ask “what can I stop doing?”

### Technique: Stop forcing every tool result through the context window

**Practice:** Revisit the assumption that **each tool result must be tokenized back to Claude** before the next step. When the next hop only needs a **slice** of output or a **handoff between tools**, let the **model** decide what becomes tokens instead of the harness defaulting to “full result in, full result billed.”

**Mechanism:** **Context window**, **tool results as tokens**, harness-side orchestration defaults; contrast with model-side filtering/orchestration (paired with the next technique).

**Payoff:** **Latency and cost** when large payloads would otherwise flood context; **task quality** when irrelevant rows/columns drown signal (large-table example).

**Anchor:** **“Let Claude orchestrate its own actions”** — *“Processing tool results in tokens can be slow, costly, and unnecessary if it only needs to be passed to the next tool or if Claude only cares about a small slice of the output.”*

---

### Technique: Give Claude code execution to express multi-step tool logic

**Practice:** Provide a **code execution** path (article names **bash** or a **language-specific REPL** under the code execution tool) so Claude can **write code** that sequences tool calls and intermediate logic. Structure the harness so **only code execution’s output** returns as model-visible context, not every intermediate tool payload.

**Mechanism:** **Code execution tool**, **bash tool**, **language-specific REPL**, harness orchestration vs. in-code orchestration.

**Payoff:** **Token cost and context health** by avoiding full intermediate dumps; **task quality** on **BrowseComp** when Opus 4.6 could filter its own tool outputs (**45.3% → 61.6%** accuracy).

**Anchor:** **“Let Claude orchestrate its own actions”** — *“Since code is a general way for Claude to orchestrate actions, a strong coding model is also a strong general agent.”*

*Narrow reading:* The article presents **hard-coded filters** (migration guide) as a **tool-design** mitigation that **does not replace** moving orchestration judgment to the model; it is a complementary pattern, not the main recommendation.

---

### Technique: Replace monolithic preloaded instructions with skills and progressive disclosure

**Practice:** Avoid stuffing **system prompts** with **rarely used, task-specific** instructions that **scale poorly** across many tasks. Use **skills** whose **YAML frontmatter** gives a **short, always-on summary** while the **full skill body** is loaded only when needed via a **read file** path.

**Mechanism:** **System prompts**, **skills** (overview doc), **YAML frontmatter**, **read file tool**, **attention budget** (linked engineering article).

**Payoff:** **Context health** and **cost** by not pre-spending attention on unused instructions.

**Anchor:** **“Let Claude manage its own context”** — *“The full skill can be progressively disclosed by Claude calling a read file tool if a task calls for it.”*

---

### Technique: Prune stale context with context editing

**Practice:** Pair voluntary assembly of context (skills) with **selective removal** of **stale or irrelevant** material—examples given: **old tool results**, **thinking blocks**.

**Mechanism:** **Context editing** (platform doc).

**Payoff:** **Context health** (keeping the window focused as sessions lengthen).

**Anchor:** **“Let Claude manage its own context”** — *“context editing is the inverse, providing a way to selectively remove context that’s become stale or irrelevant.”*

---

### Technique: Fork work into subagents for fresh context

**Practice:** Let Claude **spawn subagents** when a subtask benefits from a **clean context window** rather than carrying parent-thread baggage.

**Mechanism:** **Subagents** (code.claude.com docs), **BrowseComp** measurement for Opus 4.6.

**Payoff:** **Task quality**: subagents improved BrowseComp by **+2.8%** vs. best single-agent runs (article’s Opus 4.6 note).

**Anchor:** **“Let Claude manage its own context”** — *“With Opus 4.6, the ability to spawn subagents improved results on BrowseComp by 2.8% over the best single-agent runs.”*

---

### Technique: Use compaction for long-horizon continuity

**Practice:** For **long-running** agents, enable **compaction** so Claude **summarizes prior context** to preserve continuity instead of relying solely on external retrieval stacks.

**Mechanism:** **Compaction** doc, **BrowseComp** comparisons across models and “compaction budget.”

**Payoff:** **Task quality** scales with **newer models** under the same compaction setup: **Sonnet 4.5** “stayed flat at **43%** regardless of the compaction budget,” while **Opus 4.5** reached **68%** and **Opus 4.6** **84%**.

**Anchor:** **“Let Claude persist its own context”** — *“Sonnet 4.5 stayed flat at 43% regardless of the compaction budget we gave it. Yet Opus 4.5 scaled to 68% and Opus 4.6 reached 84% with the same setup.”*

---

### Technique: Persist agent-chosen state with a memory folder

**Practice:** Give Claude **simple, direct persistence**—a **memory folder** where it **writes** context to files and **reads** it back—rather than assuming memory must always be a separate retrieval system around the model.

**Mechanism:** **Memory folder** / **memory tool** doc, **BrowseComp-Plus**, Pokémon long-horizon play example.

**Payoff:** **Task quality** on **BrowseComp-Plus**: **Sonnet 4.5** with memory folder **60.4% → 67.2%**; qualitative **better note-taking discipline** in the Pokémon vignette (older model: transcript-like duplicate files; **Opus 4.6**: fewer, directory-organized files including distilled learnings).

**Anchor:** **“Let Claude persist its own context”** — *“On BrowseComp-Plus, giving Sonnet 4.5 a memory folder lifted accuracy from 60.4% to 67.2%.”*

---

# Pattern 3 — Set boundaries carefully

### Technique: Package stateless turns to maximize prompt-cache hits

**Practice:** Because the **Messages API is stateless**, the harness must **re-supply** prior actions, tool definitions, and instructions each turn—so **intentionally order and mutate** that bundle to hit **prompt caching breakpoints**. Follow the article’s harness principles: **stable prefix first, dynamic tail last**; **append** new content via the **messages** channel rather than rewriting the cached prompt; **avoid mid-session model switches** (caches are **model-specific**—use a **subagent** if you need a cheaper model); **treat the tool list as part of the cached prefix** and avoid churn; use **tool search** so dynamic discovery **appends without invalidating** the prefix; for multi-turn agents, **advance breakpoints** toward the latest message (**auto-caching** referenced).

**Mechanism:** **Messages API**, **prompt caching breakpoints**, **tool search**, **subagents**, **auto-caching**, **pricing** link.

**Payoff:** **Cost** — cached tokens priced at **10% of base input tokens** (article cites pricing doc).

**Anchor:** Section **“Design context to maximize cache hits”** — *“Since cached tokens are 10% the cost of base input tokens, here are a few principles in the agent harness help maximize cache hits.”*

*Narrow reading:* The table row describing message updates appears garbled in the captured HTML (`Append a`  `in messages`); the **Description** column’s intent is **append via messages instead of editing the prompt** to preserve cache behavior.

---

### Technique: Promote actions to dedicated, typed tools at real boundaries

**Practice:** Where **bash** gives only a **uniform command string**, **lift** sensitive or product-meaningful actions into **dedicated tools** with **typed arguments** so the harness can **intercept, gate, render, or audit** per action. Use **reversibility** as a guide: **hard-to-reverse** steps (e.g., **external API calls**) are candidates for **user confirmation**; **write/edit** tools can enforce **staleness checks** so Claude does not overwrite concurrently changed files.

**Mechanism:** **Bash tool** vs. **dedicated tools**, **typed arguments**, harness hooks.

**Payoff:** **Safety**, **UX control**, and **observability** (structured arguments).

**Anchor:** **“Use declarative tools for UX, observability, or security boundaries”** — *“Promoting actions to dedicated tools gives the harness an action-specific hook with typed arguments it can intercept, gate, render, or audit.”*

---

### Technique: Surface human decisions through tool-shaped UI (e.g., modals)

**Practice:** When the agent must **pose a question**, offer **options**, or **block** until feedback, model that step as a **tool** the harness can render—article example: **modal** presentation.

**Mechanism:** Tool calls as **UI events**, **modal** rendering, agent loop **blocking** until user input.

**Payoff:** **User experience** clarity and controlled pacing.

**Anchor:** **“Use declarative tools for UX, observability, or security boundaries”** — *“they can be rendered as a modal to display a question clearly to the user.”*

---

### Technique: Log, trace, and replay via structured tool payloads

**Practice:** Prefer **typed tools** when you need **first-class telemetry**: the harness receives **structured arguments** suitable for **logging, tracing, and replay**.

**Mechanism:** **Structured arguments** on tool calls.

**Payoff:** **Observability** and operational **debuggability** of agent behavior.

**Anchor:** **“Use declarative tools for UX, observability, or security boundaries”** — *“When the action is a typed tool, the harness gets structured arguments it can log, trace, and replay.”*

---

### Technique: Re-evaluate when “general + guardrail” replaces dedicated tools

**Practice:** Treat the dedicated-tool decision as **ongoing**. The article cites **Claude Code auto-mode** (noted as **research mode** at publication): a **second Claude** reads the **bash command string** and **judges safety**, which **can reduce** how many bespoke tools you need—**only** where users **trust** that general direction; **high-stakes** actions may still warrant **dedicated** tools.

**Mechanism:** **Claude Code auto-mode** engineering post, **dual-model** command review over **bash**.

**Payoff:** **Simpler surface area** without abandoning **security boundaries** where stakes demand explicit tools.

**Anchor:** **“Use declarative tools for UX, observability, or security boundaries”** — *“The decision to promote actions to tools should be continually re-evaluated.”*

---

## Stacks and dependencies


| Higher-level pattern (article)                       | Building blocks named in the post                                                | One-line rationale                                                                          |
| ---------------------------------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------- |
| **Programmatic tool calling**                        | **Bash**, **text editor**                                                        | Composed from the same general tools Claude already masters.                                |
| **Agent Skills**                                     | **Bash**, **text editor** (plus **read file** for disclosure)                    | Skills are called out as compositions of those primitives; disclosure uses read file.       |
| **Memory tool / memory folder**                      | **Bash**, **text editor**                                                        | Explicitly listed alongside other compositions of bash + editor.                            |
| **Model-side orchestration / output filtering**      | **Code execution** (**bash** or **REPL**), tool calls executed in an environment | Code expresses calls and logic; only execution output must return as tokens.                |
| **Long-horizon continuity**                          | **Compaction**, optionally **memory folder**                                     | Compaction summarizes past context; memory folder files provide durable externalized state. |
| **Fresh-context subtasks**                           | **Subagents**                                                                    | Forking isolates work without polluting the parent window.                                  |
| **Cheaper model in-session**                         | **Subagents** (instead of switching main model)                                  | Model switches break caches; subagent avoids breaking the primary cached session.           |
| **Safety without proliferating tools** (conditional) | **Bash** + **auto-mode second Claude reviewer**                                  | Can bound bash risk and **limit** dedicated-tool need where trust profile fits.             |


---

## Evidence-led examples


| Example (article)                               | What was compared / varied                                                              | Outcome stated in the post                                                                                                                                                     | Anchor                                                                                            |
| ----------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------- |
| **SWE-bench Verified**                          | **Claude 3.5 Sonnet** with **only bash + text editor** vs. prior SOTA framing           | **49%**, described as **state of the art** at the time                                                                                                                         | **“1. Use what Claude knows”** (SWE-bench Sonnet engineering link in sentence).                   |
| **BrowseComp** (agentic web browsing benchmark) | **Opus 4.6** could **filter its own tool outputs** vs. not                              | Accuracy **45.3% → 61.6%**                                                                                                                                                     | **“Let Claude orchestrate its own actions”** — benchmark named **BrowseComp** with those figures. |
| **BrowseComp** + **subagents**                  | **Opus 4.6** spawning subagents vs. **best single-agent** runs                          | **+2.8%**                                                                                                                                                                      | **“Let Claude manage its own context”** — explicit percentage.                                    |
| **BrowseComp** + **compaction**                 | **Compaction budget** vs. model generation (**Sonnet 4.5**, **Opus 4.5**, **Opus 4.6**) | **Sonnet 4.5** flat **43%**; **Opus 4.5** **68%**; **Opus 4.6** **84%** “with the same setup”                                                                                  | **“Let Claude persist its own context”**.                                                         |
| **BrowseComp-Plus** + **memory folder**         | **Sonnet 4.5** with vs. without memory folder                                           | **60.4% → 67.2%**                                                                                                                                                              | **“Let Claude persist its own context”**.                                                         |
| **Pokémon long-horizon play**                   | **Sonnet 3.5** vs. **Opus 4.6** memory-folder usage at **~14,000 steps**                | **Sonnet 3.5**: **31 files**, duplicate caterpillar notes, still early-game; **Opus 4.6**: **10 files**, directory structure, **three gym badges**, distilled **learnings.md** | **“Let Claude persist its own context”** — subsection with YAML snippet examples.                 |
| **Long-horizon harness resets**                 | **Sonnet 4.5** “context anxiety” workaround vs. **Opus 4.5** behavior                   | Premature wrap behavior **gone** on Opus 4.5; **context resets became unnecessary dead weight**                                                                                | **“Looking forward”** — narrative about harness resets added then obsoleted.                      |
| **Prompt caching**                              | Cached vs. uncached input pricing                                                       | Cached tokens **10%** the cost of **base input tokens**                                                                                                                        | **“Design context to maximize cache hits”** — cites pricing documentation.                        |


---

# Cross-cutting themes

- **Harness assumptions expire** as the model’s emergent capabilities grow; even blog guidance should be **revisited frequently**. *Anchor:* Opening paragraphs — *“agent harnesses encode assumptions … but those assumptions grow stale as Claude gets more capable.”*
- **Prefer primitives the model is already learning** (bash, editor) and **compose upward** rather than fragmenting the tool surface. *Anchor:* Caption — *“Programmatic tool calling, skills, and memory are compositions of our bash and text editor tools.”*
- **Shift orchestration and context decisions toward the model** (code-mediated tool chains, skills, editing, subagents, compaction, memory files) to protect **latency, tokens, and signal**. *Anchor:* **“Let Claude orchestrate its own actions”** — orchestration moves from harness to model.
- **A strong coding model generalizes** to non-coding agent tasks when code is the orchestration layer. *Anchor:* **“Let Claude orchestrate its own actions”** — *“a strong coding model is also a strong general agent.”*
- **Boundaries remain necessary** for UX, cost, and security—but should be **designed**, not accidental (caching layout, typed tools, confirmations). *Anchor:* **“Set boundaries carefully”** — *“Agent harnesses provide structure around Claude to enforce UX, cost, or security.”*
- **Remove compensations that the model outgrows**; leftover structure can **bottleneck** performance. *Anchor:* **“Looking forward”** — *“Removing this dead weight is important because it can bottleneck Claude’s performance.”*
- **Continually ask “what can I stop doing?”** as the through-line between simplification and pruning. *Anchor:* Introductory three-pattern list — *“ask what you can stop doing.”*

---

# Skill integration hooks

1. **Include** a **harness hygiene** checklist: **re-test** “what Claude can’t do alone” on **each model generation** or product release, mirroring the article’s **stale assumptions** warning.
2. **When drafting agent harness prompts**, **specify** default **tool-return policy**: require explicit justification before the harness **tokenizes full tool outputs**; steer authors toward **code execution** patterns where intermediates should stay **out of context**.
3. **Teach** the **bash + text editor** foundation and require skill/tool authors to state **which primitive composition** their feature assumes (skills, programmatic calling, memory).
4. **Document** **progressive disclosure** for skills: **YAML frontmatter** always on; **full body** via **read file** only when relevant—paired with a warning against **monolithic system prompts** for rare tasks.
5. **Add** a **context stack** subsection covering **context editing**, **subagents**, **compaction**, and **memory folder**, each with **when-to-use** cues tied to **long-horizon** and **multi-step browse/search** scenarios.
6. **Include** **prompt-caching authoring rules**: **static-first / dynamic-last**, **append messages vs. rewrite**, **no mid-session model swap** (prefer **subagent** for cheaper models), **stable tool lists** plus **tool search** for extension, **breakpoint / auto-caching** guidance for multi-turn agents, and the **10% vs. base input** cost anchor from **pricing** docs.
7. **Instruct** authors to **map actions to dedicated tools** when the harness needs **typed hooks** for **gating, UI, or telemetry**, with examples: **user confirmation** for **hard-to-reverse** calls, **staleness checks** on writes, **modal** flows.
8. **Add** a **standing review item**: **re-evaluate** dedicated tools vs. **general bash + policy** (e.g., **auto-mode–style** secondary review) for tasks where users accept broader autonomy.
9. **Cite** the article’s **benchmark vignettes** (BrowseComp percentages, BrowseComp-Plus memory lift, compaction scaling across Sonnet/Opus) as **quantitative motivation** blocks—not as universal guarantees—when teaching harness simplification.
10. **Point** implementers to **Anthropic’s consolidated `claude-api` skill** on GitHub for **hands-on coverage** of the patterns the post enumerates (*“To use all tools and patterns discussed here, check out our claude-api skill”*).
11. **Reference** linked **platform docs** **only** where the article explicitly uses them as the mechanism: **bash**, **text editor**, **code execution**, **skills overview**, **context editing**, **subagents**, **compaction**, **memory tool**, **prompt caching**, **Messages API**, **context windows**, **system prompts**, **migration guide** (hard-coded filters), **harness design for long-running apps**, and **Claude Code auto-mode**—so skill readers can jump from **concept → official spec**.
12. **Frame scope** in the skill: this article **emphasizes** harness evolution, tool composition, context economics, caching, and declarative boundaries; it does **not** attempt a full **security threat model** or **product-specific compliance** catalog—those stay **out-of-scope** unless paired with other sources.

---

**Source:** [Harnessing Claude’s intelligence — three patterns for building apps](https://claude.com/blog/harnessing-claudes-intelligence) (Claude blog, April 2, 2026).