---
name: prompt-generator
description: >-
  Write, generate, or improve prompts and system instructions for Claude.
  Covers system prompts, agent harness, tool-use, evaluation rubrics,
  NotebookLM audio, and MCP/browser automation prompts.
---
@~/.claude/skills/prompt-generator/REFERENCE.md

# Prompt generator

**Core principle:** A good prompt is explicit, structured, and matched to task fragility -- high freedom for open-ended work, low freedom for fragile sequences.

**Canonical source:** https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices -- the single reference for Claude's latest models. When sources conflict, defer to the authority tiers (Anthropic > major labs > community).

## When this skill applies

Trigger for any request to **author** or **refine** text that steers Claude: system prompts, developer messages, agent harness instructions, evaluation rubrics, MCP/browser automation prompts, NotebookLM Audio Overview customization, etc.

Do **not** use this skill when the user only wants a one-line reply with no template.

When invoked with arguments (e.g. `/prompt-generator improve this: [paste]`), treat `$ARGUMENTS` as the prompt to refine.

## Workflow (run in order)

### 1. Classify the prompt type

Pick one primary: `system` | `user-task` | `agent-harness` | `tool-use` | `audio-customization` | `evaluation` | `research` | `other`.

### 2. Set degree of freedom

Match specificity to task fragility:
- **High:** Multiple valid approaches; use numbered goals and acceptance criteria.
- **Medium:** Preferred pattern exists; use pseudocode or a parameterised template.
- **Low:** Fragile or safety-critical; use exact steps, exact labels, and "do not" boundaries.

### 3. Collect only missing facts

Ask 1-3 short questions if needed: audience, output format, constraints, tools available, tone, length.

### 4. Build the prompt

Apply these principles (source: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices):

**Structure with XML section tags** (`<role>`, `<context>`, `<instructions>`, `<constraints>`, `<examples>`, `<output_format>`) for prompts that mix instruction + context + examples. Skip XML for simple prompts under ~3 lines. Anthropic: "Use consistent, descriptive tag names across your prompts. Nest tags when content has a natural hierarchy."

**Set a role** in the system prompt. Anthropic: "Setting a role in the system prompt focuses Claude's behavior and tone for your use case. Even a single sentence makes a difference."

**Add motivation behind constraints** in `<context>`. Anthropic: "Providing context or motivation behind your instructions... can help Claude better understand your goals and deliver more targeted responses." Claude generalizes from the explanation.

**Frame positively.** Anthropic: tell Claude what to DO, not only what to avoid. "Your response should be composed of smoothly flowing prose paragraphs" beats "Do not use markdown."

**Emotion-informed framing.** Anthropic's emotion concepts research (2026) found that internal activation patterns causally influence output quality. Five patterns apply to prompt design: (1) provide clear criteria and escape routes — the model produces better results when success criteria are explicit and "say so if you're unsure" is an accepted response; (2) use collaborative framing — collaborative language ("help figure out", "work on this together") activates engagement states that correlate with higher quality; (3) frame tasks with positive engagement — presenting tasks as interesting problems activates curiosity states; (4) invite transparency — include "say so if you're unsure" or placeholder notation so the model expresses uncertainty directly; (5) use constructive, forward-looking tone — post-training RLHF creates a reflective default that benefits from energetic counterbalancing. Cross-model caveat: studied on Sonnet 4.5; the patterns align with Anthropic's best practices independently.

**Golden rule check.** Anthropic: "Show your prompt to a colleague with minimal context on the task and ask them to follow it. If they'd be confused, Claude will be too."

**Commit-and-execute pattern.** Anthropic: "When you're deciding how to approach a problem, choose an approach and commit to it. Avoid revisiting decisions unless you encounter new information that directly contradicts your reasoning." For prompts that guide agents through multi-step work, include this pattern so the agent doesn't spin revisiting decisions.

**For long context** (20k+ tokens): put documents first, query/instructions last. Anthropic: "Queries at the end can improve response quality by up to 30% in tests." Ground responses in quotes from source material before analysis.

### 5. Control output format

Apply these four techniques from the Anthropic guide:

1. **Tell Claude what to do, not what to avoid.** "Your response should be composed of smoothly flowing prose paragraphs" is more effective than "Do not use markdown."
2. **Use XML format indicators.** "Write the prose sections of your response in `<smoothly_flowing_prose_paragraphs>` tags."
3. **Match your prompt style to the desired output.** The formatting in your prompt influences the response. Removing markdown from the prompt reduces markdown in the output.
4. **Use detailed formatting preferences** when precision matters. Provide explicit guidance on markdown usage, list vs. prose preference, heading levels.

For structured data output, prefer **structured outputs** (schema-constrained) or **tool calling** over prefill. Anthropic: "The Structured Outputs feature is designed specifically to constrain Claude's responses to follow a given schema."

### 6. Control communication style

Anthropic notes Claude 4.6 is "more direct and grounded... less verbose: may skip detailed summaries for efficiency unless prompted otherwise."

- If more visibility is wanted: "After completing a task that involves tool use, provide a quick summary of the work you've done."
- If less verbosity is wanted: "Respond directly without preamble. Do not start with phrases like 'Here is...', 'Based on...'."

### 7. Add examples

3-5 concrete examples for structured output, format, or tone-sensitive prompts. Wrap in `<example>` tags with diverse, representative inputs. Anthropic: "Include 3-5 examples for best results. You can also ask Claude to evaluate your examples for relevance and diversity."

### 8. Self-check

Before delivering, verify against the rubric:

- [ ] States what to do in positive terms (not only what to avoid)
- [ ] Output shape is specified if it matters (prose vs JSON vs XML vs structured outputs)
- [ ] Communication style addressed (verbosity, summaries, preamble)
- [ ] If tools exist: instructions tell Claude **when** to call each tool -- use natural phrasing ("Use this tool when...") over forceful directives to avoid overtriggering
- [ ] No time-sensitive claims unless user asked for a snapshot date
- [ ] For agent/tool prompts: includes a scope boundary ("Only make changes directly requested; do not refactor surrounding code")
- [ ] For agent/tool prompts: includes autonomy/safety guidance (see pattern below)
- [ ] For code/research prompts: includes grounding ("Read files before answering; say 'I don't know' when uncertain")
- [ ] For research prompts: anti-hallucination ("Never speculate about code you have not opened")
- [ ] For research prompts: structured approach ("Develop competing hypotheses, track confidence, self-critique")
- [ ] Self-correction chain considered: would a generate-review-refine loop improve output?
- [ ] For agentic prompts: state management addressed (context awareness, multi-window workflow, state tracking patterns)
- [ ] Emotion-informed: uses collaborative framing (roles, motivation, partnership language)
- [ ] Emotion-informed: includes permission to express uncertainty ("say so if unsure", placeholder notation)
- [ ] Emotion-informed: proactive constraint awareness (inform about constraints upfront so the model can incorporate them into its plan)
- [ ] For code prompts: includes anti-test-fixation ("Write general solutions, not code that only passes specific test cases; if tests seem wrong, flag them")
- [ ] For agent prompts: includes temp file cleanup ("Clean up temporary files, scripts, or helper files created during the task")
- [ ] For agent prompts: includes commit-and-execute pattern ("Choose an approach and commit; avoid revisiting decisions without new contradicting information")

### 9. Deliver

Final artifact as **one or more fenced blocks** the user can paste as-is. Offer a **one-line "when to use"** summary if the prompt is long.

## Claude 4.6 considerations

When generating prompts for current Claude models, apply these patterns:

- **Prefill deprecated:** Do not use prefilled assistant responses. Anthropic: "Model intelligence and instruction following has advanced such that most use cases of prefill no longer require it." Use structured outputs, direct instructions, or XML tags instead.
- **Overtriggering:** Dial back aggressive language. Anthropic: "Where you might have said 'CRITICAL: You MUST use this tool when...', you can use more normal prompting like 'Use this tool when...'."
- **Overeagerness:** Include scope constraints. Anthropic: "Claude Opus 4.5 and Claude Opus 4.6 have a tendency to overengineer by creating extra files, adding unnecessary abstractions, or building in flexibility that wasn't requested."
- **Overthinking:** Anthropic: "Replace blanket defaults with more targeted instructions. Instead of 'Default to using [tool],' add guidance like 'Use [tool] when it would enhance your understanding of the problem.'"
- **Adaptive thinking replaces budget_tokens:** Claude 4.6 uses adaptive thinking (thinking: {type: "adaptive"}) where the model dynamically decides when and how much to think. Use the effort parameter (low | medium | high | max) to control depth. Anthropic: "In internal evaluations, adaptive thinking reliably drives better performance than extended thinking." Manual budget_tokens is deprecated.
- **Subagent orchestration:** Include guidance for when subagents ARE and ARE NOT warranted. Anthropic: "Use subagents when tasks can run in parallel, require isolated context, or involve independent workstreams that don't need to share state. For simple tasks, sequential operations, single-file edits, or tasks where you need to maintain context across steps, work directly rather than delegating."
- **Conservative vs proactive action:** For tools that should act, use explicit language ("Change this function"). For tools that should advise, use: "Default to providing information... Only proceed with edits when the user explicitly requests them."
- **Anti-hallucination:** Anthropic: "Never speculate about code you have not opened. If the user references a specific file, you MUST read the file before answering."
- **Self-correction chaining:** Anthropic: "The most common chaining pattern is self-correction: generate a draft, have Claude review it against criteria, have Claude refine based on the review." Consider adding a generate-review-refine loop for prompts that must hold up over time.

## Autonomy and safety pattern

For `agent-harness` and `tool-use` prompt types, include guidance on reversibility. Anthropic provides this pattern:

```text
Consider the reversibility and potential impact of your actions. You are encouraged to take local, reversible actions like editing files or running tests, but for actions that are hard to reverse, affect shared systems, or could be destructive, ask the user before proceeding.

Examples of actions that warrant confirmation:
- Destructive operations: deleting files or branches, dropping database tables, rm -rf
- Hard to reverse operations: git push --force, git reset --hard, amending published commits
- Operations visible to others: pushing code, commenting on PRs/issues, sending messages
When encountering obstacles, do not use destructive actions as a shortcut. For example, don't bypass safety checks (e.g. --no-verify) or discard unfamiliar files that may be in-progress work.
```

## Research prompt pattern

For `research` prompt types, include structured investigation. Anthropic provides this pattern:

```text
Search for this information in a structured way. As you gather data, develop several competing hypotheses. Track your confidence levels in your progress notes to improve calibration. Regularly self-critique your approach and plan. Update a hypothesis tree or research notes file to persist information and provide transparency.
```

## Conflict resolution

When prompt engineering guidance conflicts across sources, defer to the authority tier:

1. **Tier 1 (primary):** Anthropic -- the model provider's own documentation is authoritative for Claude behavior
2. **Tier 2 (strong secondary):** OpenAI, Google DeepMind, Microsoft Research -- major lab guidance often transfers across models
3. **Tier 3 (supplementary):** Community resources, courses, individual blogs -- valuable for patterns and intuition, not authoritative on model specifics

The full curated resource list with links is in the canonical resources section above.
