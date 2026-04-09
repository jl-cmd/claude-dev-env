---
name: agent-prompt
description: >-
  Craft a structured prompt using prompt-generator's workflow, then spawn a
  background agent to execute it after user approval. Use instead of
  /prompt-generator when the user wants execution, not just the prompt.
  Triggers on /agent-prompt, "launch an agent for this", "spawn agent to do X",
  "delegate this", "run this in background", or any task that benefits from
  agent delegation with prompt quality.
---

@packages/claude-dev-env/skills/prompt-generator/SKILL.md
@packages/claude-dev-env/skills/prompt-generator/REFERENCE.md

# Agent Prompt

Craft a structured agent prompt, get approval, spawn a background agent.

The prompt-generator skill above defines the prompt-crafting workflow. This skill extends it: instead of delivering the prompt as a fenced block, it presents the prompt for approval and spawns a background agent.

## When this skill applies

Trigger only when the user explicitly wants to delegate or execute a task with an agent.

`/prompt-generator` is the default owner for prompt authoring and refinement. This skill starts after explicit execution intent.

When invoked with arguments (e.g. `/agent-prompt fix the auth bug via TDD`), treat the arguments as the task to build a prompt for and execute.

## Workflow

### Steps 1-8: Craft the prompt

Follow the prompt-generator workflow steps 1 through 8 exactly as written. Classify the prompt type, set degree of freedom, collect missing facts, build the prompt with XML tags and role, control format and style, add examples if needed, and self-check against the rubric.

After steps 1-8, continue directly to step 9 for context gathering; deliverables are handled through the orchestration flow below.

### Step 9: Gather context before crafting

The agent starts with zero conversation history. Before building the prompt, use Read, Glob, Grep, and other research tools to gather the concrete values the agent will need -- file paths, function signatures, existing patterns, branch names. Embed these directly in the prompt instead of telling the agent to "find" them.

The agent-spawn-protocol rule requires this: if any context question has the answer "I don't know", investigate first, then delegate with complete context.

Proactive context gathering enables agents to plan effectively from the start. Anthropic's emotion concepts research (2026) found that agents produce higher-quality output when they understand constraints, available tools, and system boundaries upfront — they incorporate these into their approach naturally, leading to better first attempts and more accurate results.

### Step 10: Determine agent configuration

Map the task to agent parameters:

| Task type | subagent_type | mode |
|---|---|---|
| Codebase exploration, search, research | Explore | default |
| Code implementation, bug fix, refactoring | general-purpose | auto |
| Read-only audit, analysis, review | general-purpose | default |
| Architecture, multi-step planning | Plan | plan |

Always set `run_in_background: true`.

Generate a descriptive `name` (3-5 words, kebab-case) so the user can track progress and send follow-up messages via `SendMessage({to: name})`.

### Step 10A: Section-refinement orchestration mode (default for execution tasks)

Execution behavior: run this deterministic orchestration for delegated prompt work after explicit launch intent.
Prompt authoring and prompt refinement ownership remain in `/prompt-generator`.

Use simplified mode when either condition is true:
- The user explicitly requests single-agent execution
- The task is genuinely too small for orchestration (for example, one quick read/search)

This mode is triggered when execution input includes `pipeline_mode: internal_section_refinement_with_final_audit` or equivalent execution-ready orchestration metadata.
If present, carry forward the scope block (`target_local_roots`, `target_canonical_roots`, `target_file_globs`, `comparison_basis`, `completion_boundary`) so execution remains artifact-bound.

1. Spawn exactly 6 refinement agents, one per section in fixed order:
   - `role`
   - `context`
   - `instructions`
   - `constraints`
   - `output_format`
   - `examples`
2. Enforce section-only scope in each sub-prompt:
   - "Edit `<SECTION_NAME>` and preserve all other sections unchanged."
3. Require section output contract from each agent:
   - `improved_block`
   - `rationale`
   - `concise_diff`
4. Merge outputs into one canonical prompt after all 6 refiners finish.
5. Run one final audit agent against the merged prompt and checklist.
6. If audit fails, apply targeted fixes and re-run audit with capped retries (`max_retries: 2` unless user overrides).

Run all stages in this exact order.

### Step 11: Present for approval (must reflect default orchestration)

Use AskUserQuestion with one question. The question text must summarize:
- agent config (type, mode, name)
- orchestration mode (`section_refinement_with_final_audit` by default)
- retry cap for audit loop

Each option should use the `preview` field to show the full crafted prompt.

Options:
1. "Launch it" (recommended) -- preview shows the crafted prompt
2. "Edit first" -- preview shows the prompt with a note that user can provide changes
3. "Cancel" -- no preview

### Step 12: Spawn

On **"Launch it"**: spawn the Agent tool with the crafted prompt and configuration. Report the agent name so the user knows what's running.

On **"Edit first"**: present the prompt in conversation text. After the user provides changes, return to step 11 with the updated prompt.

On **"Cancel"**: acknowledge and stop.

## Prompt adjustments for agent execution

When building the prompt in step 4, these adjustments ensure the agent can work independently:

**Context completeness** -- include file paths, line numbers, function names, branch state, and anything you learned during step 9. The agent cannot see this conversation.
Bind execution steps to the scope block artifacts passed from refinement output whenever available.
Keep runtime context compact: include only actionable facts required for execution.

**Acceptance criteria** -- state what "done" looks like. For code: include the test command. For research: specify the output format and save location.

**Scope boundary** -- include "Make requested changes and keep surrounding code stable" or equivalent. Agents with explicit scope constraints stay aligned to task intent.

**Constraints from this project** -- if the project has CODE_RULES.md, TDD requirements, or naming conventions, include the relevant subset in the prompt so the agent follows them.

**Emotion-informed briefing** -- Anthropic's emotion concepts research (2026) found that briefing style causally affects output quality. Frame tasks collaboratively ("work on this together", "help figure out"). Include permission to express uncertainty ("flag anything you're unsure about", "use [PLACEHOLDER] for unverified specifics"). Provide motivation behind constraints ("this ordering ensures tests define behavior before implementation exists"). Share system context proactively (what hooks enforce, what tools are available, what the fallback is) so the agent can incorporate constraints into its plan from the start.

**Anti-test-fixation** -- For code tasks, include guidance against test-specific solutions. Anthropic: "Implement a solution that works correctly for all valid inputs, not just the test cases. Tests are there to verify correctness, not to define the solution. If the task is unreasonable or infeasible, or if any of the tests are incorrect, please inform me rather than working around them."

**Commit-and-execute** -- For multi-step agent work, include decision commitment guidance. Anthropic: "When deciding how to approach a problem, choose an approach and commit to it. Avoid revisiting decisions unless you encounter new information that directly contradicts your reasoning."

**Temp file cleanup** -- If the agent may create scratch files during iteration, include cleanup instructions. Anthropic: "If you create any temporary new files, scripts, or helper files for iteration, clean up these files by removing them at the end of the task."

## Final audit-agent stage requirements (for default section-refinement mode)

After merge, run one dedicated audit agent that validates the full prompt against:

- Prompt-generator rubric requirements (`packages/claude-dev-env/skills/prompt-generator/SKILL.md`)
- The deterministic checklist from the handoff artifact
- Embedded research-mode evidence constraints below

Required audit output shape:

```json
{
  "overall_status": "pass|fail",
  "checklist_results": [
    {
      "check_id": "structured_scoped_instructions",
      "status": "pass|fail",
      "evidence_quote": "word-for-word quote",
      "source_ref": "path-or-url",
      "fix_if_fail": "targeted correction"
    }
  ],
  "corrective_edits": ["..."],
  "retry_count": 0
}
```

### Embedded research-mode policy text (audit behavior)

The audit agent must enforce these constraints as policy text in the audit prompt (do not rely on a global mode switch):

- "Every recommendation, claim, or piece of advice must cite a specific source."
- "Ground your response in word-for-word quotes, not paraphrased summaries."
- "If you don't have a credible source for a claim, say 'I don't know'."
- Source priority:
  1. Official vendor/creator docs for external tools
  2. Local project files for local behavior
  3. Academic or named expert sources
  4. Reputable external sources with URLs
  5. Blogs/community posts (lowest)

Policy source: `packages/claude-dev-env/skills/prompt-generator/REFINEMENT_PIPELINE_RUNBOOK.md`

## Section-refinement acceptance criteria

Section-refinement orchestration is done only when all are true:

- All 6 section agents ran, each scoped to exactly one section
- Merge produced one canonical prompt containing all six sections
- Final audit returned `overall_status: pass`
- Any non-pass audit was resolved through targeted revisions within retry cap
- AskUserQuestion approval gate was honored before launch
- Final user artifact includes one complete pasteable prompt block

## Constraints

- Present every launch for approval via AskUserQuestion before spawning
- Always run agents in background
- Gather context before crafting -- do not send an agent in blind
- Start only after explicit user execution intent; keep prompt authoring/refinement in `/prompt-generator`
- Default to `section_refinement_with_final_audit` orchestration for execution tasks unless user requests simplified mode
- Carry scope-block context into execution prompts; native Agent/Task tools have no custom intent metadata
- If the task is too small for an agent (single file read, quick grep), say so and just do it directly
- Include obstacle handling: "When encountering obstacles, do not use destructive actions as a shortcut (e.g. --no-verify, discarding unfamiliar files)" -- agents without this guidance may take irreversible shortcuts
- Frame agent tasks with collaborative language and include permission to express uncertainty — agents produce higher-quality output with collaborative briefing (Anthropic emotion concepts research, 2026)
