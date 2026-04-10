# Prompt generator -- reference

## Canonical resources

When authoring or refining prompts, ground decisions in these sources. If guidance conflicts, defer to the higher tier.

### Tier 1: Anthropic (primary authority for Claude)

- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview -- overview, links to all sub-guides
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices -- the single living reference for Claude's latest models.
- https://transformer-circuits.pub/2026/emotions/index.html -- emotion concepts research (April 2026). Key takeaways: clear criteria and escape routes, collaborative framing, positive task framing, inviting transparency. Full catalog: `packages/claude-dev-env/docs/emotion-informed-prompt-design.md`.
- https://www.anthropic.com/research/emotion-concepts-function -- blog summary of the above paper.
- https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking -- adaptive thinking reference; replaces manual budget_tokens with effort-based control.
- https://claude.com/blog/harnessing-claudes-intelligence -- harness evolution: primitives Claude already knows, what to stop doing in the harness, deliberate boundaries (context economics, caching, typed tools). Local inventory: `docs/references/anthropic-harnessing-claudes-intelligence-technique-inventory.md`.
- https://github.com/anthropics/skills/tree/main/skills/claude-api -- Anthropic `claude-api` Agent Skill for hands-on API/tool patterns from that post (Hook 10). Platform entry: https://platform.claude.com/docs/en/agents-and-tools/agent-skills/claude-api-skill

### Tier 2: Major labs (strong secondary, often transfers across models)

- https://platform.openai.com/docs/guides/prompt-engineering -- six strategies: write clear instructions, provide reference text, split complex tasks, give models time to think, use external tools, test systematically.
- https://deepmind.google/research/ -- learning resources and chain-of-thought research.
- https://www.microsoft.com/en-us/research/blog/ -- publications and applied research.

### Tier 3: Courses, communities, individuals (supplementary)

**Courses:**

- https://www.deeplearning.ai/short-courses/ -- Andrew Ng's courses. "ChatGPT Prompt Engineering for Developers" (with OpenAI) is the foundational one.
- https://course.fast.ai/ -- Jeremy Howard's top-down teaching style.
- https://www.elementsofai.com/ -- University of Helsinki introductory course.
- https://ocw.mit.edu/search/?t=Artificial%20Intelligence -- MIT OpenCourseWare AI curriculum.

**Communities and individuals:**

- https://discuss.huggingface.co/ -- open-source model community.
- https://www.latent.space/ -- AI engineering perspective (Latent Space Podcast & Newsletter).
- https://simonwillison.net/ -- practical LLM experiments. His "LLM" tag is especially valuable.

### Conflict resolution rule

If sources disagree, apply tier order: Anthropic first, then OpenAI/Google/Microsoft, then community. Tier 1 wins when conflicting with lower tiers.

### Outcome preview gate and digest (`prompt-generator`)

See SKILL.md §§107-115 (Phases 4-5) and `TARGET_OUTPUT.md` for the full contract. **Clipboard safety:** `extract_fenced_xml_content` concatenates every ` ```xml ` block—follow §7 sample formatting so clipboard copy stays the lone artifact body.

### Outcome preview gate and digest (`prompt-generator`)

Human checkpoint before the paste-ready artifact ships: the orchestrator runs an **Outcome preview** turn (`### Outcome preview` bullets built from the **preview summary**, defined in SKILL.md Terminology) plus **AskUserQuestion** (**Ship** recommended first, two contextual alternates, **Refine with free text**), then emits `Audit`, a single ` ```xml ` fence, and **`## Outcome digest`** after the fence. Rationale matches collaborative checkpoints in `templates/skill-from-ground-up.md` and the refinement pattern in `templates/skill-refinement-package.md`. `ARCHITECTURE.md` lists all files in this skill package.

**Clipboard safety:** `prompt_workflow_gate_core.extract_fenced_xml_content` concatenates every ` ```xml ` block in the message—follow the sample formatting rules in SKILL.md section 7 so clipboard copy stays the lone artifact body. Full contract: `TARGET_OUTPUT.md`.

## Harness design patterns (Anthropic blog, April 2026)

Primary URL: https://claude.com/blog/harnessing-claudes-intelligence. Structured inventory: `docs/references/anthropic-harnessing-claudes-intelligence-technique-inventory.md`.

### Mechanism doc map (Hook 11)

Jump from concept to the platform specs the post names:

- [Bash tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/bash-tool) / [Text editor tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool)
- [Code execution tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/code-execution-tool) / [Programmatic tool calling](https://platform.claude.com/docs/en/agents-and-tools/tool-use/programmatic-tool-calling)
- [Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Agent Skills overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)
- [Context windows](https://platform.claude.com/docs/en/build-with-claude/context-windows) / [Context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing) / [Compaction](https://platform.claude.com/docs/en/build-with-claude/compaction)
- [Subagents](https://code.claude.com/docs/en/sub-agents)
- [System prompts](https://platform.claude.com/docs/en/release-notes/system-prompts) / [Working with the Messages API](https://platform.claude.com/docs/en/build-with-claude/working-with-messages) / [Prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching)
- [Model migration guide — hard-coded filters](https://platform.claude.com/docs/en/about-claude/models/migration-guide#additional-recommended-changes)
- [Harness design for long-running applications](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [Claude Code auto-mode](https://www.anthropic.com/engineering/claude-code-auto-mode)
- [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

### Context stack (Hook 5)

- **Context editing:** Remove stale tool results and thinking blocks selectively ([Context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing)).
- **Subagents:** Fork fresh windows for isolated subtasks; post cites **+2.8%** BrowseComp vs best single-agent for Opus 4.6 ([Subagents](https://code.claude.com/docs/en/sub-agents)).
- **Compaction:** Summarize prior context for long horizons ([Compaction](https://platform.claude.com/docs/en/build-with-claude/compaction)); effectiveness varies by model generation (see Hook 9 table).
- **Memory folder:** Persist agent-chosen state via the memory tool / files ([Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)).

### Prompt caching (Hook 6)

The Messages API is stateless. Maximize [prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching): **stable prefix first, dynamic tail last**; **append** via messages; **avoid mid-session model switches** (use a subagent for cheaper models); **treat tool list as cached prefix**; use **tool search** to append without invalidation; **advance breakpoints** toward the latest message. Cached tokens cost **10% of base input**.

### Typed tools vs bash strings (Hook 7)

Promote actions to **dedicated tools** with typed arguments when the harness must intercept, gate, render (e.g., **modals**), or audit—**hard-to-reverse** steps (e.g., external API calls) for user confirmation; **write/edit** paths with **staleness checks** so concurrent edits are not blindly overwritten ([Harnessing Claude's intelligence](https://claude.com/blog/harnessing-claudes-intelligence)).

### Standing review: dedicated tools vs general bash + policy (Hook 8)

Re-evaluate promotions as models improve—e.g., Claude Code **auto-mode** (secondary reviewer over bash strings) can **reduce** bespoke tools **only** where users accept that trust profile; **high-stakes** actions still warrant dedicated tools ([Claude Code auto-mode](https://www.anthropic.com/engineering/claude-code-auto-mode)).

### Benchmark vignettes — motivation only, not guarantees (Hook 9)

| Vignette | Outcome stated in the post |
|----------|----------------------------|
| SWE-bench Verified | Claude 3.5 Sonnet **49%** with bash + editor only (then SOTA framing) |
| BrowseComp + output filtering | Opus 4.6 **45.3% → 61.6%** |
| BrowseComp + subagents | Opus 4.6 **+2.8%** vs best single-agent |
| BrowseComp + compaction | Sonnet 4.5 **43%** flat; Opus 4.5 **68%**; Opus 4.6 **84%** (same setup) |
| BrowseComp-Plus + memory folder | Sonnet 4.5 **60.4% → 67.2%** |
| Prompt caching | Cached tokens **10%** the cost of base input tokens |

## NotebookLM Audio Overview customization (example)

Adapt `[FOCUS AREA]` per notebook. Pair with Deep Dive + Longer in the product UI when that matches the user's plan.

```text
Target audience: [Expert-level listener profile -- skip beginner padding.]

Focus: [FOCUS AREA -- single notebook-specific paragraph.]

Style: [Technical depth, anti-patterns, implications for builders.]

Prioritize: [Technical depth and specific findings over marketing tone or generic summaries.]
```

## Agent checklist pattern

For long tasks, optional checklist the model can mirror:

```text
Copy this checklist and mark items as you go:

Progress:
- [ ] ...
- [ ] ...
```

## Agentic state management

For `agent-harness` prompts that span multiple context windows, include state persistence and multi-window patterns. Based on Anthropic's guidance:

### Context awareness

Claude 4.6 tracks its remaining context window. Include harness capabilities so Claude can plan accordingly:

```text
<context_management>
Your context window will be automatically compacted as it approaches its limit, allowing you to continue working indefinitely from where you left off. Do not stop tasks early due to token budget concerns. As you approach the limit, save current progress and state before the context window refreshes. Always be as persistent and autonomous as possible and complete tasks fully.
</context_management>
```

### Multi-window workflow

Anthropic recommends differentiating the first context window from subsequent ones:

**First window:** Set up the framework -- write tests, create setup scripts, establish the todo-list.

**Subsequent windows:** Iterate on the todo-list, using state files to resume.

Key patterns from Anthropic:
- Have the model write tests in a **structured format** (e.g. `tests.json` with `{id, name, status}`) before starting work. Remind: "It is unacceptable to remove or edit tests because this could lead to missing or buggy functionality."
- Encourage **setup scripts** (e.g. `init.sh`) to start servers, run test suites, and linters. This prevents repeated work across windows.
- When starting fresh, be **prescriptive about resumption**: "Review progress.txt, tests.json, and the git logs."
- Provide **verification tools** (Playwright, computer use) for autonomous UI testing.

### State tracking

```text
<state_management>
Track progress in structured + freeform files:
- tests.json: structured test status {id, name, status}
- progress.txt: freeform session notes and next steps
- Use git commits as checkpoints for rollback

When approaching context limits, save current state before the window refreshes.
Do not stop tasks early due to token budget concerns.
</state_management>
```

### Encouraging complete context usage

```text
This is a very long task, so it may be beneficial to plan out your work clearly. It's encouraged to spend your entire output context working on the task - just make sure you don't run out of context with significant uncommitted work. Continue working systematically until you have completed this task.
```

## Research prompt pattern

For `research` prompt types, include structured investigation with hypothesis tracking:

```text
<research_approach>
Search for this information in a structured way. As you gather data, develop several competing hypotheses. Track your confidence levels in your progress notes to improve calibration. Regularly self-critique your approach and plan. Update a hypothesis tree or research notes file to persist information and provide transparency. Break down this complex research task systematically.
</research_approach>
```

## Evaluation loop

For prompt drafts that must hold up over time:

1. Run the draft on 2-3 representative user utterances.
2. Note failure modes (skipped steps, wrong format, over-refusal).
3. Tighten **constraints** or add **examples** for the failure class only.

Anthropic's **self-correction chaining** pattern extends this: generate a draft, have Claude review it against criteria, then have Claude refine based on the review. Each step can be a separate API call for inspection and branching.

## Anti-test-fixation pattern

```text
Write general-purpose solutions using the standard tools available. Implement logic that works correctly for all valid inputs, not just the test cases. Tests verify correctness -- they do not define the solution. If a test seems incorrect or the task is unreasonable, flag it rather than working around it.
```

## Commit-and-execute pattern

```text
When deciding how to approach a problem, choose an approach and commit to it. Avoid revisiting decisions unless you encounter new information that directly contradicts your reasoning. If you are weighing two approaches, pick one and see it through. You can always course-correct later if the chosen approach fails.
```

## Debug JSON schema (prompt-generator pipeline)

Use **only** when the user explicitly requests debug output (for example `show debug`, `full audit table`, `raw internal object`). Default assistant turns complete the normal handoff first: one `xml` fence + **`## Outcome digest`** (see also `TARGET_OUTPUT.md`); this JSON object is an optional appendix **after** that handoff.

Shape (field names stable for internal audit helpers and Stop-hook leak detection):

```json
{
  "pipeline_mode": "internal_section_refinement_with_final_audit",
  "scope_block": {
    "target_local_roots": ["..."],
    "target_canonical_roots": ["..."],
    "target_file_globs": ["..."],
    "comparison_basis": "...",
    "completion_boundary": "..."
  },
  "required_sections": ["role", "background", "instructions", "constraints", "output_format", "illustrations"],
  "base_prompt_xml": "<role>...</role><background>...</background><instructions>...</instructions><constraints>...</constraints><illustrations>...</illustrations><output_format>...</output_format>",
  "section_scope_rule": "Each refiner edits exactly one section and returns sibling sections unchanged.",
  "section_output_contract": {
    "required_fields": ["improved_block", "rationale", "concise_diff"]
  },
  "merge_output_contract": {
    "required_fields": ["canonical_prompt_xml"]
  },
  "audit_output_contract": {
    "required_fields": [
      "overall_status",
      "checklist_results",
      "evidence_quotes",
      "source_refs",
      "corrective_edits",
      "retry_count"
    ]
  },
  "checklist_results": {
    "<row_name>": {
      "status": "pass|fail",
      "evidence_quote": "exact quote used for verification",
      "source_ref": "URL or local path",
      "fix_if_fail": "concrete edit text (empty only if pass)"
    }
  }
}
```

`checklist_results` keys must include all **15** compliance row ids from `SKILL.md` §11 (for example `reversible_action_and_safety_check_guidance`, `scope_terms_explicit_and_anchored`).
