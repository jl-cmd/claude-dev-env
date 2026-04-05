# Emotion-Informed Prompt Design for agent-gate

Design document. Review before implementation.

---

## Source Material

**Paper:** "Emotion Concepts and their Function in a Large Language Model" (Anthropic, April 2026)
- https://transformer-circuits.pub/2026/emotions/index.html
- https://www.anthropic.com/research/emotion-concepts-function

**Official guidance:** https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices

**Reference repo:** https://github.com/OuterSpacee/claude-emotion-prompting (7 principles and 9 anti-patterns grounded in the paper; its system prompt templates use collaborative language and include examples, though they omit XML tags and output format specification)

**Cross-model caveat:** The paper studied Sonnet 4.5. Agent-gate targets Opus 4.6. The emotion-vector mechanism has not been validated across models. The changes below align with Anthropic's official best practices for Opus 4.6 independently; the paper findings serve as additional supporting rationale.

---

## Design Principles

Five paper findings shape how each surface is written:

| Principle | Research basis | How it applies |
|---|---|---|
| Clear criteria and escape routes | Desperation vectors activate on repeated failure + unclear success criteria, driving fabrication | Every path has explicit next steps. The model always knows what to do next. |
| Collaborative framing | Compliance pressure activates anxiety, which drives sycophancy over accuracy | Frame evaluation as collaborative improvement. Use roles and motivation. |
| Positive engagement | Curiosity/interest states correlate with measurably better output quality | Frame the coaching task as helping the user, with constructive energy. |
| Invite transparency | Suppressing uncertainty trains concealment, not resolution | Invite "I don't know" and placeholder notation. Permission to express uncertainty. |
| Constructive tone | Post-training RLHF creates a gloomy default; constructive framing counterbalances | Active, forward-looking language throughout. |

---

## Surface-by-Surface Specifications

Each surface shows the target text and the rationale for that framing.

### Surface 1: Gate Directive (UserPromptSubmit injection)

**File:** `packages/agent-gate-claude/src/agent_gate_claude/config/constants.py`
**Constant:** `USER_PROMPT_SUBMIT_GATE_DIRECTIVE`

**Target text:**
```
<prompt_gate>
A prompt evaluation step helps ensure clear, actionable work before execution begins.

Call {evaluate_tool_name} with a single `request` object as your first tool action. Before calling it, gather concrete project context using Read, Glob, Grep, WebFetch, WebSearch, and Context7 — actual file paths, existing patterns, and current official documentation make the assessment specific and useful.

If the rubric scores low, the gate asks you to coach the user toward a clearer prompt via AskUserQuestion, then unlocks bounded discovery tools for further context gathering.

Write, Edit, Bash, Agent, and Task become available after the gate clears. Discovery tools (Read, Glob, Grep, WebFetch, WebSearch, Context7) are available throughout.

For library or API behavior, fetch official documentation rather than relying on training-data recollection.

The PreToolUse hook ensures this ordering — if a tool is called before the gate clears, the hook will redirect you to call evaluate_prompt first.
</prompt_gate>
```

**Rationale:**
- XML wrapper per Anthropic: "Use consistent, descriptive tag names across your prompts"
- "helps ensure" — collaborative framing with motivation (Anthropic: "Providing context or motivation behind your instructions helps Claude better understand your goals")
- "become available after" — positive framing (Anthropic: "Tell Claude what to do instead of what not to do")
- Discovery tools listed as available throughout — the model always knows what it can use right now
- Enforcement notice as information ("ensures this ordering", "will redirect") — the model learns the constraint proactively rather than discovering it through denial (which would trigger the desperation pattern the paper identifies)

---

### Surface 2: Tool Description (evaluate_prompt)

**File:** `packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/config/constants.py`
**Constant:** `EVALUATE_PROMPT_TOOL_DESCRIPTION`

**Target text:**
```
Evaluate the user's prompt against five quality dimensions before proceeding with execution tools.

Before calling this tool, use Read, Glob, and Grep to gather concrete project context. Use WebFetch, WebSearch, and Context7 to look up current official documentation for any library, API, or platform in the prompt. Cite official documentation sources only (the library's own docs domain or platform provider docs such as docs.anthropic.com, docs.python.org). Cite exact URLs inline.

For each rubric category below threshold, encode specific findings as assessment suggestions — actual file paths, cited API patterns, concrete details. Specific values make the draft prompt confirmable; vague phrases leave blanks.

Pass a single `request` object with: `assessment` (required — JSON object with five keys: target_and_action, scope, clarity_of_intent, success_criteria, output_expectations, each mapping to {"score": 1-5, "suggestions": [...]}), `original_prompt` or `prompt` for user text, optional `planned_execution` or `rubric`, optional `session_identifier`, optional `require_canonical_confirmation`, optional `confirmation_phase` (set to "ack" for follow-up confirmation call).

When categories score below threshold: the return includes coaching guidance with a draft prompt block. Present this via AskUserQuestion so the user can refine their intent. When the average score is below 3.0, question-first mode activates — call AskUserQuestion, then call this tool with confirmation_phase ack to unlock bounded discovery.

When all categories pass: a canonical prompt is returned for user confirmation via AskUserQuestion. After the user confirms, call this tool with confirmation_phase ack to complete the evaluation. Execution tools become available after the ack call.
```

**Rationale:**
- "quality dimensions" — frames as improvement. "coaching guidance" — collaborative.
- "become available" / "refine their intent" — positive framing throughout
- Conditional flow details preserved — Anthropic: "Claude's latest models are trained for precise instruction following and benefit from explicit direction to use specific tools." Tool descriptions are machine-facing contracts where completeness matters.
- `require_canonical_confirmation` removed — confirmation is now always the flow (Surface 9)

---

### Surface 3: Failing-Path Preamble

**File:** `packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/config/constants.py`
**Constants:** `ASK_USER_QUESTION_FAILING_CANON_AND_MISSION`, `ASK_USER_QUESTION_FAILING_AGENT_GUIDANCE`, `ANTI_HALLUCINATION_DRAFT_RULES`

**`ASK_USER_QUESTION_FAILING_CANON_AND_MISSION` target:**
```
CANONICAL REFERENCE (prompt quality): {PROMPT_ENGINEERING_CANON_URL}
ANTI-HALLUCINATION REFERENCE: {ANTI_HALLUCINATION_GUIDANCE_URL}
These are the authoritative references for this coaching step.

Your role here: help the user sharpen their prompt so the intent, scope, and success criteria are clear enough to act on. The user may not be familiar with prompt engineering — explain gaps in plain language and offer concrete improvements.

Your next action is AskUserQuestion. Present the draft block and options below, then wait for the user's response before any other work.
```

**`ASK_USER_QUESTION_FAILING_AGENT_GUIDANCE` target:**
```
<coaching_guidance>
Follow these steps in order:

1) Call AskUserQuestion next with the options and draft block below.
2) Build your choices from the rubric-aligned option lines. Each choice should resolve a specific gap identified in the assessment.
3) Include "Proceed as-is" and "Let me rephrase" as the final two options. Aim for 3-5 total choices.
4) Ground every element in the user message, files read this session, or official documentation fetched this turn. Use [BRANCH], [REPO], [FILE_PATH], or [PR_NUMBER] placeholders for values you haven't verified. Do not invent repositories, branches, PR numbers, or product facts not in those sources.
5) Include the DRAFT_PROMPT_FOR_USER: block below verbatim in your AskUserQuestion question text. You may correct obvious errors in the draft before presenting it.
6) Align suggestions with Anthropic's prompt engineering guidance: clear instructions, sufficient context, bounded scope, verifiable success criteria, explicit output expectations.
</coaching_guidance>
```

**`ANTI_HALLUCINATION_DRAFT_RULES` target:**
```
When assembling the draft prompt (reference: {ANTI_HALLUCINATION_GUIDANCE_URL}):
- Ground claims in the user message, planned_execution, files read via Read/Glob/Grep, or official documentation fetched via WebFetch/WebSearch/Context7 this turn.
- Fetch official docs for library or API behavior and cite the URL — training data may be outdated.
- Use [BRANCH], [REPO], [FILE_PATH], or [PR_NUMBER] placeholders for genuinely unknown values.
- Say "I don't know" when you lack a source rather than constructing plausible specifics.
```

**Rationale for Surface 3:**
- Role-setting per Anthropic: "Setting a role in the system prompt focuses Claude's behavior and tone"
- "Your next action is" — direct positive instruction
- Numbered steps per Anthropic: "Provide instructions as sequential steps using numbered lists or bullet points when the order or completeness of steps matters" (Section: "Be clear and direct"). Numbered format makes compliance auditable.
- Step 4 keeps concrete anti-hallucination guardrail alongside placeholder guidance — concrete rules strengthen factual grounding
- "Say 'I don't know'" — positive instruction, permission to express uncertainty

---

### Surface 4: Passing-Path Reply

**File:** `packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/config/constants.py`
**Constant:** `PASSING_ASSESSMENT_GATE_CLEARED_REPLY`

**Target text:**
```
All rubric categories passed. Proceed with your planned execution using tools.

Ground your work in files you have read and official documentation you have fetched. Use [PLACEHOLDER] notation for file paths, branch names, or API specifics you have not verified this session. When you encounter something uncertain during execution, verify it rather than assuming.
```

**Rationale:**
- "Ground your work in" — positive instruction for how to proceed
- "verify it rather than assuming" — positive action for uncertainty
- Shorter per Anthropic: "more direct and grounded... less verbose"
- This constant is only reached via `confirmation_phase ack` after Surface 9 — the user has already confirmed via AskUserQuestion. Surface 9 must land before this text change.

---

### Surface 5: Low-Score Question-First Reply

**File:** `packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/server.py`
**Constant:** `LOW_SCORE_QUESTION_FIRST_REPLY`

**Target text:**
```
The prompt needs more detail before discovery tools can help effectively. Present the options and draft block below via AskUserQuestion so the user can clarify their intent. After their response, call evaluate_prompt with confirmation_phase ack and the same session_identifier to continue.
```

**Rationale:**
- "needs more detail" — describes the situation with motivation ("before discovery tools can help effectively")
- "so the user can clarify their intent" — collaborative framing
- "to continue" — forward-looking

---

### Surface 6: Discovery Mode Enabled Reply

**File:** `packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/server.py`
**Constant:** `DISCOVERY_MODE_ENABLED_REPLY`

**Target text:**
```
The user has clarified their intent. Discovery tools are now available to gather context for the task. Use Read, Glob, Grep, WebFetch, WebSearch, and Context7 within the exploration budget, then call evaluate_prompt with a full assessment grounded in what you found.
```

**Rationale:**
- "The user has clarified" — acknowledges the collaborative exchange
- Named specific tools — removes ambiguity
- "grounded in what you found" — connects discovery to assessment quality

---

### Surface 7: Draft Prompt Builder

**File:** `packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/server.py`
**Function:** `_build_draft_improved_prompt()`

**Target structure:**
```
DRAFT_PROMPT_FOR_USER:
Here is a structured version of your request. Review each section — confirm what looks right, adjust what doesn't, and fill in any blanks.

---
Goal: [user prompt + target suggestions]
Scope: [scope suggestions or "looks clear"]
Constraints / intent: [clarity suggestions or "looks clear"]
Success criteria: [criteria suggestions or "looks clear"]
Output format: [output suggestions or "looks clear"]
Planned approach (if relevant): [planned_execution]
---
```

**Rationale:**
- "confirm what looks right, adjust what doesn't, and fill in any blanks" — three positive actions
- "looks clear" — natural language for passing fields

---

### Surface 8: Canonical Prompt Builder

**File:** `packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/canonical_prompt_builder.py`
**Function:** `build_canonical_user_prompt_block()`

**Target role section:**
```
You are a coding agent working on this task. Deliver clear, verifiable outcomes and flag uncertainties you encounter along the way.
```

**Target instructions format for passing categories:**
```
- Target and action: incorporate [suggestion]
- Scope: addressed in the prompt; maintain during execution
```

---

## Surface 9: Mandatory User Confirmation (Architectural Change)

**Files:**
- `packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/server.py` (flow logic)
- `packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/config/constants.py` (remove optional confirmation constants)
- `packages/agent-gate-core/src/agent_gate_core/config/constants.py` (remove env var constants)
- `packages/agent-gate-claude/src/agent_gate_claude/config/constants.py` (remove canonical confirmation suffix)
- `packages/agent-gate-prompt-refinement/src/agent_gate_prompt_refinement/assessment_models.py` (remove `require_canonical_confirmation` field)

**Design goal:** Every gate traversal requires explicit user confirmation before clearing. The user always sees what Claude plans to do and approves it.

**Target flow (two paths):**
1. Low score (avg < 3.0) -> question-first -> user clarifies -> bounded discovery -> re-evaluate -> user confirms canonical prompt -> clears
2. Normal/passing score -> canonical prompt shown via AskUserQuestion -> user confirms -> `confirmation_phase ack` -> clears

**Code changes:**

1. **Remove `_canonical_confirmation_effective()` conditional** in `server.py` — the passing path always keeps the bridge and returns canonical prompt + AskUserQuestion instruction

2. **Remove opt-in infrastructure:**
   - `require_canonical_confirmation` field from `EvaluatePromptRequest`
   - `REQUIRE_CANONICAL_CONFIRMATION_ENVIRONMENT_KEY` and `REQUIRE_CANONICAL_CONFIRMATION_ENVIRONMENT_ACTIVE_VALUE` from core constants
   - `USER_PROMPT_SUBMIT_CANONICAL_CONFIRMATION_SUFFIX` from claude constants
   - Environment variable check in `gate_trigger.py`

3. **Simplify `evaluate_prompt()` passing branch:** After `_all_categories_passing()` returns True, always build canonical block, keep bridge in `confirm_canonical` phase, return phase-two confirmation reply

4. **Ensure re-evaluation after discovery also requires confirmation:** When the low-score path reaches a second `evaluate_prompt` call with a full assessment and all categories pass, that path also goes through canonical confirmation — not silent clearing

5. **Update `PASSING_ASSESSMENT_GATE_CLEARED_REPLY`:** This constant is now only reached via `confirmation_phase ack` — it is the post-confirmation message, never the initial response to a passing rubric

6. **Update `EVALUATE_PROMPT_TOOL_DESCRIPTION`:** Remove references to optional confirmation mode; confirmation is always the flow

7. **Fix the middle path (not-all-passing, avg >= 3.0):** Currently (server.py line 275-281) this path clears the bridge immediately and returns AskUserQuestion instruction — the model is free to use Write/Edit/Bash because the bridge is gone. This violates the invariant. **Fix:** Keep the bridge active on this path too. Set phase to `confirm_canonical`, build canonical block, return phase-two confirmation reply — same as the all-passing path. The AskUserQuestion coaching from the failing assessment still appears in the question text, but the bridge stays until the user confirms.

8. **Update `CANONICAL_CONFIRMATION_ACK_WRONG_PHASE_REPLY`:** Current text references `require_canonical_confirmation` which is being removed. Rephrase to: "Canonical prompt confirmation is not pending for this gate. Call evaluate_prompt with an assessment first. After all categories pass, confirm the canonical prompt via AskUserQuestion, then call evaluate_prompt with confirmation_phase ack."

9. **Update `ASK_USER_QUESTION_PHASE_TWO_AGENT_RULES`:** Contains "STRICT RULES (phase two):" which contradicts the cross-cutting pattern. Rephrase to numbered steps with positive framing (consistent with Surface 3 fix).

10. **Update `ASK_USER_QUESTION_PHASE_TWO_OPENING`:** Contains "blocked tools are allowed" — change to "execution tools become available" per cross-cutting pattern.

11. **Define "Proceed as-is" behavior:** When the user selects "Proceed as-is" on a failing prompt, the gate clears without requiring a second canonical confirmation step. The user has already made an explicit human-in-the-loop decision. Double-confirmation adds no safety value and degrades UX.

12. **Update both file copies:** `hooks/gate_trigger.py` and `packages/agent-gate-claude/hooks/gate_trigger.py` are identical copies — both need Surface 1 changes and env-var removal.

**Invariant:** No path clears without explicit user interaction (either `confirmation_phase ack` after AskUserQuestion, or "Proceed as-is" selection). No silent auto-clearing.

---

## Cross-Cutting Patterns

These patterns apply across all surfaces:

### 1. Use collaborative language

| Pattern | Example | Anthropic basis |
|---|---|---|
| Set a role | "Your role here: help the user sharpen their prompt" | "Setting a role focuses Claude's behavior and tone" |
| Provide motivation | "helps ensure clear, actionable work" | "Providing context or motivation helps Claude better understand your goals" |
| Frame as partnership | "so the user can clarify their intent" | Collaborative framing activates positive engagement |
| Inform about constraints | "The PreToolUse hook ensures this ordering" | Proactive awareness prevents repeated-failure pattern |

### 2. Use positive framing

| Pattern | Example | Anthropic basis |
|---|---|---|
| State what to do | "become available after" | "Tell Claude what to do instead of what not to do" |
| Positive uncertainty | "Say 'I don't know'" / "Use [PLACEHOLDER]" | Permission to express uncertainty |
| Forward-looking language | "to continue" / "verify it rather than assuming" | Direct next action |
| Keep concrete guardrails | "Do not invent repositories, branches, PR numbers" | Anti-hallucination needs concrete rules |

### 3. Use XML structure

Multi-section prompt surfaces use XML tags: `<prompt_gate>`, `<coaching_guidance>`. Per Anthropic: "Use consistent, descriptive tag names across your prompts. Nest tags when content has a natural hierarchy."

### 4. Use numbered steps for sequential procedures

Per Anthropic: "Provide instructions as sequential steps using numbered lists or bullet points when the order or completeness of steps matters." The coaching guidance is a sequence where order matters.

### 5. Keep model-facing text focused on actions

The model needs to know: what to do, in what order, and what tools are available. Internal mechanics (bridge files, score thresholds, phase names) stay in code.

---

## Design Scope

- The gate evaluates the same five rubric categories with the same thresholds — this design changes communication, not evaluation
- The phase-aware enforcement hook (`hooks/gate_enforcer.py`) already handles all phases correctly and requires no changes
- The package-level enforcer (`packages/agent-gate-claude/hooks/gate_enforcer.py`) lacks phase logic; the phase-aware version is canonical in production
- Emotion-informed framing shapes how the gate talks to the model, not the user
- Constructive framing throughout — no forced enthusiasm or artificial tone

---

## Implementation Order

Changes apply in this order (dependency-aware, each step independently testable):

**Phase A — Architectural change (Surface 9, must land first):**
1. Remove opt-in confirmation infrastructure (env var, request field, suffix constant, env check in both gate_trigger.py copies)
2. Make `evaluate_prompt()` passing branch always require canonical confirmation
3. Fix the middle path (not-all-passing, avg >= 3.0) to also keep bridge and require confirmation
4. Ensure re-evaluation after discovery also requires confirmation
5. Update `CANONICAL_CONFIRMATION_ACK_WRONG_PHASE_REPLY` to remove `require_canonical_confirmation` reference
6. Define "Proceed as-is" behavior — clears gate without second canonical confirmation
7. Update tests for mandatory confirmation flow (15 tests: 3 delete, 7 rewrite, 3 update field usage, 2 update assertions)

**Phase B — Prompt text changes (Surfaces 1-8, order within phase is flexible):**
8. Gate directive (`USER_PROMPT_SUBMIT_GATE_DIRECTIVE`) — XML wrapper, positive enforcement notice
9. Passing-path reply (`PASSING_ASSESSMENT_GATE_CLEARED_REPLY`) — now only reached via ack
10. Low-score + discovery replies (server.py constants) — small, self-contained
11. Anti-hallucination rules (`ANTI_HALLUCINATION_DRAFT_RULES`) — shared across paths
12. Failing-path preamble (composed constants) — numbered steps, XML wrapper, depends on #11
13. Phase-two constants (`ASK_USER_QUESTION_PHASE_TWO_AGENT_RULES`, `ASK_USER_QUESTION_PHASE_TWO_OPENING`) — align with Surface 3 language
14. Tool description (`EVALUATE_PROMPT_TOOL_DESCRIPTION`) — keep conditional flow detail, remove optional confirmation references
15. Draft prompt builder (server.py function + constants) — display text changes
16. Canonical prompt builder — role and instruction format tweaks
17. Update remaining text-assertion tests (3 tests: "STRICT RULES" markers, directive text)
