# New Skill Workflow

Full evaluation-driven lifecycle for building a new skill from scratch.

## Prerequisites

- The user has a task or domain they want to capture as a skill
- No existing skill for this capability (or intentionally starting fresh)

### Ground-up package layout (required before multi-file implementation)

When the outcome includes **ARCHITECTURE.md**, **REFERENCE / EXAMPLES / WORKFLOWS**, and **`evals/*.json`** under a workspace (Anthropic-style progressive disclosure plus checkpointed rollout):

1. Read `prompt-generator/templates/skill-from-ground-up.md` from the installed `~/.claude/skills/` tree (provided by [@jl-cmd/prompt-generator](https://github.com/jl-cmd/prompt-generator)).
2. Run `/prompt-generator` using that template (substitute tokens per its table) **before** Phase 3 expands the repo; align the XML scope block with this workflow’s workspace and evidence rules.
3. Keep Phase 1–2 artifacts honest: eval prompts and expectations stay grounded in **real** user scenarios; the template reinforces eval rows that reference pasted or explicitly approved evidence only.

Skip this block only when the user explicitly wants a **single-file** SKILL.md with no staged package plan.

Refinements to an **existing** skill package use `prompt-generator/templates/skill-refinement-package.md` instead (see `improve-skill.md`).

---

## Phase 1: Identify Gaps

**Goal:** Document what fails or requires repeated context when working without a skill.

### Process

1. Have a guided conversation to uncover gaps. Explore these areas:
   - "What task were you doing when you realized you needed a skill?"
   - "What context did you repeatedly provide to Claude?"
   - "Where did Claude fail or produce subpar results without guidance?"
   - "What domain knowledge was missing?"
   - "What specific format or structure did you need?"
   - "Were there tools or scripts that needed to be used in a particular way?"
   - "What rules or constraints did Claude violate?"

2. As patterns emerge, probe for eval-worthy scenarios:
   - "Can you give me a concrete example of a task where this failed?"
   - "What would success look like for that specific task?"
   - "Are there edge cases where the right approach changes?"

3. Generate `gap-analysis.md` from the conversation using the template at `${CLAUDE_SKILL_DIR}/templates/gap-analysis.md`. Fill in all sections from what was discussed.

4. Review the gap analysis with the user. Confirm completeness before moving to Phase 2.

**Output:** `[skill-name]-workspace/gap-analysis.md`

---

## Phase 2: Build Evals

**Goal:** Create 3+ evaluation scenarios that test the identified gaps. Establish a baseline.

### Process

1. Transform each gap into at least one eval scenario. Each scenario needs:
   - A realistic user prompt (detailed and specific, like a real request)
   - A description of what success looks like
   - Objectively verifiable expectations (assertions)

2. Draft evals using the schema at `${CLAUDE_SKILL_DIR}/templates/eval-scenario.json`. Ensure:
   - Minimum 3 scenarios (official requirement)
   - Every identified gap has at least one scenario testing it
   - Expectations are objectively verifiable, not subjective
   - Prompts sound like things a real user would say

3. Review eval scenarios with the user. Adjust until both sides are satisfied.

4. Save to `[skill-name]-workspace/evals/evals.json`.

5. **Establish baseline.** For each eval, spawn a subagent WITHOUT any skill:

   ```
   Execute this task with NO skill loaded:
   - Task: [eval prompt]
   - Input files: [eval files if any, or "none"]
   - Save all output files to: [workspace]/iteration-0/eval-[name]/without_skill/outputs/
   - Save a complete transcript of your work to: [workspace]/iteration-0/eval-[name]/without_skill/transcript.md
   ```

   Spawn all baseline runs in parallel. Capture timing data when each completes.

6. Grade baseline results using the skill-creator grading agent. See `${CLAUDE_SKILL_DIR}/references/delegation-map.md` for exact grading invocation.

**Output:** `[skill-name]-workspace/evals/evals.json` and baseline results in `iteration-0/`

---

## Phase 3: Write Minimal Skill

**Goal:** Create just enough skill content to address the documented gaps and pass evaluations.

### Process

1. Invoke `/skill-writer` with this context:

   ```
   Create a skill based on this gap analysis and eval scenarios.

   Gap analysis: [reference or paste gap-analysis.md]
   Eval scenarios: [reference or paste evals.json expected_output and expectations]
   Baseline failures: [summarize what Claude got wrong in iteration-0]

   Constraint: Write the minimum instructions needed to address these specific gaps.
   Every line must serve a documented gap. Do not over-document.
   ```

2. `/skill-writer` will run its workflow: classify type, set degree of freedom, ask clarifying questions, produce the SKILL.md artifact.

3. Review the draft with the user:
   - "Does this address all the gaps we identified?"
   - "Is anything here unnecessary or over-engineered?"
   - "Would this pass our eval scenarios?"

4. Save the skill to its target directory.

**Output:** The skill's SKILL.md (and optional reference files)

---

## Phase 4: Test (Feedback Loop)

**Goal:** Run the skill on eval scenarios, compare against baseline, identify remaining gaps.

### Process

1. **Spawn all runs in parallel.** For each eval scenario, launch a with-skill subagent:

   ```
   Execute this task:
   - Read the skill at [path-to-skill]/SKILL.md and follow its instructions
   - Task: [eval prompt from evals.json]
   - Input files: [eval files if any, or "none"]
   - Save all output files to: [workspace]/iteration-N/eval-[name]/with_skill/outputs/
   - Save a complete transcript of your work to: [workspace]/iteration-N/eval-[name]/with_skill/transcript.md
   ```

   For iteration-1, the without-skill baseline already exists from Phase 2.

2. **While runs are in progress**, review and refine assertions if needed based on what was learned from the baseline.

3. **When runs complete**, immediately capture timing data (`total_tokens`, `duration_ms`) to `timing.json` in each run directory. This data is only available in the task completion notification.

4. **Grade each run** using the skill-creator grading agent. See `${CLAUDE_SKILL_DIR}/references/delegation-map.md` for the grading process.

5. **Aggregate into benchmark** using skill-creator's aggregation script. See delegation-map.md for the exact command.

6. **Launch the eval viewer** using skill-creator's generate_review.py. See delegation-map.md for the exact command. For iteration 2+, include `--previous-workspace` to show diffs.

7. Tell the user to review in the viewer:
   - "Outputs" tab: click through each test case, leave feedback
   - "Benchmark" tab: quantitative comparison (pass rates, timing, tokens)

8. Wait for the user to complete their review.

**Output:** `grading.json`, `benchmark.json`, `feedback.json` in the iteration directory

---

## Phase 5: Iterate

**Goal:** Refine the skill based on observed Claude B behavior and user feedback.

### Process

1. Read `feedback.json` from the viewer. Empty feedback means the user was satisfied with that test case.

2. Read transcripts from Phase 4 runs. Watch for the signals the official docs highlight:
   - **Unexpected exploration paths** -- Claude B read files in an order you did not anticipate
   - **Missed connections** -- Claude B did not follow references to important files
   - **Overreliance on certain sections** -- content that should be promoted to SKILL.md
   - **Ignored content** -- files Claude B never accessed (may be unnecessary or poorly signaled)
   - **Repeated work across test cases** -- all subagents wrote similar helper scripts (bundle them into the skill)

3. Synthesize observations into actionable improvements. For each piece of feedback, identify the specific skill change that would fix it.

4. Apply improvements. For significant changes, re-invoke `/skill-writer` with:

   ```
   Refine this existing skill based on testing observations.

   Current SKILL.md: [reference or paste]
   User feedback: [from feedback.json -- only non-empty entries]
   Behavioral observations: [from transcript analysis]

   Specific issues to address:
   1. [Issue]
   2. [Issue]

   Constraint: Only change what the feedback demands. Do not reorganize working content.
   ```

5. Key principles for this phase (from the official docs):
   - **Generalize from feedback** -- the skill will be used across many different prompts, not just these test cases
   - **Keep the prompt lean** -- remove instructions that are not pulling their weight
   - **Explain the why** -- theory of mind beats rigid MUSTs
   - **Bundle repeated work** -- if subagents all wrote similar scripts, add them to the skill

6. Return to Phase 4 with the refined skill. Continue iterating until:
   - User feedback is all empty (satisfied with every test case)
   - Pass rates meet acceptable thresholds
   - No meaningful progress between iterations

---

## Phase 6: Polish

**Goal:** Optimize the skill description for triggering accuracy and run final validation.

### Process

1. **Description optimization.** Follow the process in `${CLAUDE_SKILL_DIR}/workflows/polish-skill.md`.

2. **Final validation.** Run the skill-writer self-check rubric against the finished skill:
   - [ ] Description is third person with trigger phrases
   - [ ] Under 500 lines
   - [ ] States what to do in positive terms (not prohibition-heavy)
   - [ ] Degree of freedom matches task fragility
   - [ ] Progressive disclosure used (heavy content in separate files)
   - [ ] Examples are concrete, not abstract
   - [ ] Frontmatter fields are valid
   - [ ] One skill = one capability

3. **Final checklist** from the official Anthropic docs:
   - [ ] At least 3 evaluation scenarios created and passing
   - [ ] Tested with real usage scenarios
   - [ ] Skill solves documented gaps (not imagined requirements)
   - [ ] Iterative refinement based on observed behavior (not assumptions)

4. Present the finished skill to the user with:
   - Final benchmark comparison (latest iteration vs baseline)
   - Summary of gaps addressed
   - Any remaining limitations or known edge cases
