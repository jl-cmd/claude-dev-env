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

Follow **Reading a transcript for observations** in `${CLAUDE_SKILL_DIR}/references/delegation-map.md`. Note what worked, what failed, and which gotcha would have prevented each failure.

**Output:** Observation notes with specific failure examples.

---

## Step 2: Diagnose

**Goal:** Classify each failure so you know which best practice to apply.

Failure classification:

| Symptom | Diagnosis | Apply |
|---|---|---|
| Skill never activates when it should | Description missing trigger phrases, story prose, or too vague | `description-field.md` trigger catalog |
| Skill activates when it shouldn’t | Description too broad / story; no refusal boundary | Description triggers + Constraints / when-this-applies |
| Description is multi-sentence narrative | Description used as summary/story | Rewrite per `description-field.md` |
| Skill owns unrelated jobs | Monolith / multi-capability | `skill-modularity.md` — split or orchestrator + sub-skills |
| Skill reimplements another skill’s steps | Silent reimplementation | Compose by name; sub-skills table |
| Claude reads wrong files first | Structure not intuitive, hub doesn’t guide well | Progressive disclosure |
| Claude ignores a companion file | File not signaled in SKILL.md or poorly linked | File index, hub pattern |
| Claude over-explains basics | Skill states what Claude already knows | Principles: Concision |
| Claude follows instructions too rigidly | Skill railroads instead of guiding | Principles: Degree of freedom |
| Claude makes same mistake repeatedly | Missing gotcha | Principles: Gotchas |
| Claude errors on script execution | Script doesn’t handle errors, missing deps | Principles: Scripts + `deterministic-elements.md` CODE_RULES bar |
| Output format is wrong | Missing template or examples | Principles: Templates and examples |
| Mechanical sequence only in markdown | Deterministic work left as prose | `deterministic-elements.md` — extract to scripts/workflow |
| Detection/validation is a giant one-liner in body | Executable logic not in `scripts/` | `deterministic-elements.md` |
| Fenced Python/JS in SKILL.md is the real implementation | Code not shipped as a file | Extract to `scripts/` or `workflow/` + paired test |
| Script has magic literals / no tests | CODE_RULES bar missed | `deterministic-elements.md` + CODE_RULES |
| Skill uses `- [ ]` for agent progress | Work list not on task tool | Task-seed catalog + seed instruction (`deterministic-elements.md`) |
| "Copy checklist into response" protocol | Markdown as tracker | Switch to TaskCreate / TodoWrite seeding |

When scope, activation, or deterministic placement is in play, re-read `${CLAUDE_SKILL_DIR}/references/skill-modularity.md`, `${CLAUDE_SKILL_DIR}/references/description-field.md`, and `${CLAUDE_SKILL_DIR}/references/deterministic-elements.md`.

**Output:** Diagnosis per failure — which best practice was violated.

---

## Step 3: Apply Patterns

**Goal:** Fix each diagnosed failure by applying the specific best practice that addresses it.

> "Only change what the feedback demands. Do not reorganize working content."

For each diagnosis from Step 2:

1. Read the matching reference (`description-field.md`, `skill-modularity.md`, `deterministic-elements.md`, `progressive-disclosure.md`, or SKILL.md principles).
2. Make the minimum change that addresses the failure.
3. For description failures: rewrite frontmatter into a trigger catalog (capability stem + Triggers list); strip story prose.
4. For modularity failures: add sub-skills table, split packages, or thin the orchestrator; do not paste peer skill procedures.
5. For deterministic failures: extract mechanical work to `scripts/` / `workflow/` / `templates/` / `reference/`; body only points and handles exit codes; apply CODE_RULES + paired tests to new code.
6. For checkbox/tracker failures: replace markdown `- [ ]` boards with a plain task-seed list and a seed instruction (`TaskCreate` / `TodoWrite`).
7. Verify the fix doesn’t break anything that was working.

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
2. Register every bullet as a session task; complete with evidence. Fix failures. Re-complete those tasks.
3. Pay special attention to items that overlap with the diagnosis from Step 2 — those were the failures; confirm they’re now fixed.

**Output:** Audit summary; all PASS or N/A.

---

## Step 6: Deliver

**Goal:** Hand off the improved skill with delta summary.

Present to the user:

1. **What was observed** — summary of failures from Step 1.
2. **What was diagnosed** — which best practices were violated.
3. **What changed** — delta summary (files modified, lines added/removed).
4. **Description** — final frontmatter if rewritten (paste the trigger catalog).
5. **Composition** — sub-skills or splits if modularity changed.
6. **Deterministic extracts** — scripts/workflows/templates added or moved out of prose.
7. **New gotchas added** — list of gotchas captured.
8. **Audit summary** — post-fix audit results.
9. **Suggested re-test** — a concrete task to verify the fix with Claude B.
