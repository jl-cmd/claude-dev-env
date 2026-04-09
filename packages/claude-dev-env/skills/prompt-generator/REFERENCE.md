# Prompt generator -- reference

## Canonical resources

When authoring or refining prompts, ground decisions in these sources. If guidance conflicts, defer to the higher tier.

### Tier 1: Anthropic (primary authority for Claude)

- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview -- overview, links to all sub-guides
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices -- the single living reference for Claude's latest models. Covers general principles, XML tags, prefill deprecation, tool use, thinking, agentic systems, overeagerness, evidence-grounding and citing sources before strong claims.
- https://transformer-circuits.pub/2026/emotions/index.html -- emotion concepts research (April 2026): 171 internal activation patterns that causally influence behavior. Key prompt-engineering takeaways: clear criteria and escape routes improve output quality, collaborative framing activates engagement, positive task framing correlates with better results, inviting transparency produces more reliable output. Cross-model caveat: studied on Sonnet 4.5; patterns align with best practices independently.
- https://www.anthropic.com/research/emotion-concepts-function -- blog summary of the above paper.
- https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking -- adaptive thinking reference; replaces manual budget_tokens with effort-based control.

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

If sources disagree on a technique, apply in order: Anthropic documentation first (it describes the actual model behavior), then OpenAI/Google/Microsoft (large-scale research with cross-model relevance), then community sources (patterns and intuition, not authoritative on model internals). When Tier 3 contradicts Tier 1, Tier 1 wins without exception.

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

Key elements:
- Define clear **success criteria** for the research question
- Encourage **source verification** across multiple sources
- Track **competing hypotheses** with confidence levels
- **Self-critique** approach and plan regularly

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

Use **only** when the user explicitly requests debug output (for example `show debug`, `full audit table`, `raw internal object`). Default assistant turns stay **audit line + one `xml` fence**; this object is an optional appendix after that pair.

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
  "required_sections": ["role", "context", "instructions", "constraints", "output_format", "examples"],
  "base_prompt_xml": "<role>...</role><context>...</context><instructions>...</instructions><constraints>...</constraints><examples>...</examples><output_format>...</output_format>",
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

`checklist_results` keys must include all **14** compliance row ids from `SKILL.md` §11 (for example `reversible_action_and_safety_check_guidance`, `scope_terms_explicit_and_anchored`).
