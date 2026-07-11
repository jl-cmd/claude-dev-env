# Improve Skill Workflow

Observation-first flow for iterating on an existing skill.

## Prerequisites

- An existing skill that needs improvement
- The skill has been used at least once (or the user has observed specific issues)

---

## Step 1: Observe

**Goal:** Document what’s wrong with the current skill by watching it in action or gathering user reports.

> "Use the Skill in real workflows: Give Claude B (with the Skill loaded) actual tasks, not test scenarios."

### Option A: User has observed issues

Ask:
- "What specific issue did you observe?"
- "Can you give me a concrete task where the skill underperformed?"
- "Is this a triggering issue (skill doesn’t activate), a quality issue (skill activates but produces poor results), or a scope issue (skill does the wrong thing)?"

### Option B: No observations yet — spawn a test

Spawn a subagent with the existing skill on a real task (see delegation-map.md for the spawn pattern). Read the transcript when complete.

### Transcript analysis

> "Watch for unexpected exploration paths, missed connections, overreliance on certain sections, and ignored content."

Document:
- Where did the skill work well?
- Where did it fail or produce subpar results?
- Did Claude B follow the skill’s instructions as written?
- Did Claude B ignore any sections or files?
- Did Claude B explore in unexpected directions?
- What would a gotcha have prevented?

**Output:** Observation notes with specific failure examples.

---

## Step 2: Diagnose

**Goal:** Classify each failure so you know which best practice to apply.

Failure classification:

| Symptom | Diagnosis | Apply |
|---|---|---|
| Skill never activates when it should | Description missing trigger phrases or too vague | Principles: Description field |
| Skill activates when it shouldn’t | Description too broad, no refusal cases | Principles: Constraints and refusal cases |
| Claude reads wrong files first | Structure not intuitive, hub doesn’t guide well | Progressive disclosure |
| Claude ignores a companion file | File not signaled in SKILL.md or poorly linked | File index, hub pattern |
| Claude over-explains basics | Skill states what Claude already knows | Principles: Concision |
| Claude follows instructions too rigidly | Skill railroads instead of guiding | Principles: Degree of freedom |
| Claude makes same mistake repeatedly | Missing gotcha | Principles: Gotchas |
| Claude errors on script execution | Script doesn’t handle errors, missing deps | Principles: Scripts |
| Output format is wrong | Missing template or examples | Principles: Templates and examples |

**Output:** Diagnosis per failure — which best practice was violated.

---

## Step 3: Apply Patterns

**Goal:** Fix each diagnosed failure by applying the specific best practice that addresses it.

> "Only change what the feedback demands. Do not reorganize working content."

For each diagnosis from Step 2:

1. Read the relevant section in `${CLAUDE_SKILL_DIR}/references/progressive-disclosure.md` or the SKILL.md principles.
2. Make the minimum change that addresses the failure.
3. Verify the fix doesn’t break anything that was working.

Delegate larger rewrites to `/skill-writer` using the refine-skill handoff from delegation-map.md.

**Output:** Modified skill files with targeted fixes.

---

## Step 4: Capture Gotchas

**Goal:** Every observation is a gotcha candidate. Accumulate them.

> "Ideally, you will update your skill over time to capture these gotchas."

For each failure observed in Step 1:

1. Distill it to a one-line gotcha: what went wrong and the signal that should have prevented it.
2. Add it to the skill’s Gotchas section.
3. If the failure mode is about skill-builder itself (not the skill being improved), add it to skill-builder’s own Gotchas section.

**Output:** Updated gotchas in the skill’s SKILL.md (and potentially skill-builder’s SKILL.md).

---

## Step 5: Self-Audit

**Goal:** Re-verify the modified skill against all best practices.

Same process as new-skill Step 5:

1. Read `${CLAUDE_SKILL_DIR}/references/self-audit-checklist.md`.
2. Check every item. Fix failures. Re-check.
3. Pay special attention to items that overlap with the diagnosis from Step 2 — those were the failures; confirm they’re now fixed.

**Output:** Completed checklist, all PASS or N/A.

---

## Step 6: Deliver

**Goal:** Hand off the improved skill with delta summary.

Present to the user:

1. **What was observed** — summary of failures from Step 1.
2. **What was diagnosed** — which best practices were violated.
3. **What changed** — delta summary (files modified, lines added/removed).
4. **New gotchas added** — list of gotchas captured.
5. **Audit summary** — post-fix audit results.
6. **Suggested re-test** — a concrete task to verify the fix with Claude B.
