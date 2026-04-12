# Improve Skill Workflow

Observation-first flow for iterating on an existing skill.

## Prerequisites

- An existing skill that needs improvement
- The skill has been used at least once (or the user has observed specific issues)

---

## Phase 1: Observe

**Goal:** Document the existing skill's current behavior by running it on real tasks.

> "Use the Skill in real workflows: Give Claude B (with the Skill loaded) actual tasks, not test scenarios"

### Process

1. Identify the skill to improve. Read its current SKILL.md and any reference files.

2. Ask the user what prompted the improvement:
   - "What specific issue did you observe?"
   - "Can you give me a concrete task where the skill underperformed?"
   - "Is this a triggering issue (skill does not activate), a quality issue (skill activates but produces poor results), or a scope issue (skill does the wrong thing)?"

3. Run the existing skill on 2-3 real tasks. For each, spawn a subagent:

   ```
   Execute this task using the skill at [path-to-existing-skill]:
   - Read the skill at [path]/SKILL.md and follow its instructions
   - Task: [realistic task from user]
   - Save outputs to: [skill-name]-workspace/observation/task-[N]/outputs/
   - Save transcript to: [skill-name]-workspace/observation/task-[N]/transcript.md
   ```

4. Analyze the transcripts. Document observations:
   - Where did the skill work well?
   - Where did it fail or produce subpar results?
   - Did Claude B follow the skill's instructions as written?
   - Did Claude B ignore any sections or files?
   - Did Claude B explore in unexpected directions?

5. Generate a gap analysis (same template as new-skill Phase 1) focused on the delta between current behavior and desired behavior.

**Output:** `[skill-name]-workspace/gap-analysis.md` with observation-based gaps

---

## Phase 2-6: Follow the New Skill Workflow

From here, follow the same phases as `${CLAUDE_SKILL_DIR}/workflows/new-skill.md`, starting at Phase 2 (Build Evals).

### Collaborative package orchestration (Phases 2–6)

Whenever Phases 2–6 will touch **multiple files**, **progressive disclosure layout**, or use **checkpointed file-by-file rollout**, treat this as **required** before expanding or rewriting the tree:

1. Read `prompt-generator/templates/skill-refinement-package.md` from the claude-dev-env `skills/` tree (repository path: `skills/prompt-generator/templates/skill-refinement-package.md` in [jl-cmd/prompt-generator](https://github.com/jl-cmd/prompt-generator)).
2. Run `/prompt-generator` with that template’s token table filled: set `[[BASELINE_SKILL_ROOT]]` to the existing skill directory, `[[WORKSPACE_ROOT]]` to your iteration workspace (in-place or snapshot per user preference), and `[[DESIGN_INPUT_GLOB]]` to this workflow’s observation-based `gap-analysis.md` when it exists.

Use `skill-from-ground-up.md` **only** for **greenfield** packages where no baseline skill directory exists yet; use `skill-refinement-package.md` for every refinement anchored to an existing skill.

Key differences from the new-skill flow:

- **Phase 2 (Build Evals):** Evals should test the specific issues observed in Phase 1, not hypothetical gaps.

- **Phase 3 (Write Skill):** Instead of writing from scratch, invoke `/skill-writer` with:

  ```
  Refine this existing skill based on observation findings.

  Current SKILL.md: [reference or paste current skill]
  Gap analysis: [reference observation-based gaps]
  Eval scenarios: [reference evals]

  Constraint: Preserve what works. Only change what the observations demand.
  ```

- **Phase 4 (Test):** The baseline is the CURRENT skill (snapshot it before editing). Compare old-skill vs new-skill, not with-skill vs without-skill.

  Before making any changes, snapshot the existing skill:
  ```bash
  cp -r [skill-path] [workspace]/skill-snapshot/
  ```

  Then for baseline runs, point subagents at the snapshot:
  ```
  Execute this task using the ORIGINAL skill at [workspace]/skill-snapshot/:
  - Read the skill and follow its instructions
  - Task: [eval prompt]
  - Save outputs to: [workspace]/iteration-N/eval-[name]/old_skill/outputs/
  - Save transcript to: [workspace]/iteration-N/eval-[name]/old_skill/transcript.md
  ```

- **Phase 5 (Iterate):** Same process. The improvement loop compares new version against the snapshot.

- **Phase 6 (Polish):** Same process. Run description optimization if triggering was an issue.
