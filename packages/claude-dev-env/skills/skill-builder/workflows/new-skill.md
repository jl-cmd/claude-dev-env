# New Skill Workflow

Best-practice-driven lifecycle for building a skill from scratch.

## Prerequisites

- The user has a task or domain they want to capture as a skill
- No existing skill for this capability (or intentionally starting fresh)

---

## Step 1: Classify

**Goal:** Determine the skill type. Type dictates folder structure.

1. Read `${CLAUDE_SKILL_DIR}/references/skill-types.md`.

2. Ask the user about the skill’s purpose:

   > "What will this skill help Claude do?"

   Match the answer against the 9 types. If ambiguous, present the top 2-3 matches and ask the user to choose.

3. Record the classification: type number, type name, recommended folders.

**Output:** Type classification with folder plan.

---

## Step 2: Scaffold

**Goal:** Create the folder structure. Every skill starts with the same skeleton plus type-specific additions.

1. Create the skill directory if it doesn’t exist.

2. Create the minimum structure:

   ```
   skill-name/
   ├── SKILL.md          # Hub — every skill has this
   ```

3. Add type-specific directories based on Step 1 classification (see `${CLAUDE_SKILL_DIR}/references/skill-types.md` for the folder recommendations per type).

4. Verify the scaffold matches the type recommendation.

> "As your Skill grows, you can bundle additional content that Claude loads only when needed."

**Output:** Directory tree with SKILL.md stub.

---

## Step 3: Gather

**Goal:** Collect domain knowledge, failure patterns, and gotchas from the user.

> "Build a Gotchas Section — these sections should be built up from common failure points that Claude runs into when using your skill."

### Interview questions

Ask the user:

1. "What task were you doing when you realized you needed a skill?"
2. "What context did you repeatedly provide to Claude?"
3. "Where did Claude fail or produce subpar results without guidance?"
4. "What does Claude consistently get wrong about this domain?"
5. "What specific format or structure do you need in the output?"
6. "Are there rules or constraints Claude must never violate?"
7. "What tools, scripts, or libraries does Claude need to use?"
8. "Does this skill need to run differently for different models (Haiku vs Opus)?"

### Generate gap analysis

Use the template at `${CLAUDE_SKILL_DIR}/templates/gap-analysis.md`. Fill in:

- Skill type and degree of freedom
- Task description
- Gaps identified (what failed, what was needed)
- Recurring patterns across gaps
- Initial gotcha candidates

### Assess degree of freedom

> "Match the level of specificity to the task’s fragility and variability."

| Degree | When | Example |
|---|---|---|
| High | Multiple valid approaches, context-dependent | Code review guidelines |
| Medium | Preferred pattern exists, some variation ok | Report generation with template |
| Low | Fragile operations, consistency critical | Database migration with exact script |

Record the assessment with reasoning.

**Output:** Completed gap analysis, initial gotchas list, degree-of-freedom assessment.

---

## Step 4: Write

**Goal:** Produce the skill package — SKILL.md and companion files.

Delegate to `/skill-writer` using the structured handoff from `${CLAUDE_SKILL_DIR}/references/delegation-map.md`.

The handoff must include: skill type, folder structure, gap analysis, initial gotchas, degree of freedom, constraints.

After skill-writer produces the draft:

1. Verify it follows the hub layout (principle → gotchas → when-applies → process → file index → folder map).
2. Verify SKILL.md body is under 500 lines.
3. Verify all references are one level deep.
4. Verify files over 100 lines have a TOC.

Fix structural issues before proceeding.

**Output:** Complete skill package at the target directory.

---

## Step 5: Self-Audit

**Goal:** Verify every best practice is satisfied before delivery.

1. Read `${CLAUDE_SKILL_DIR}/references/self-audit-checklist.md`.
2. Copy the checklist into your response.
3. Check every item against the built skill. For each: PASS, FAIL with file:line evidence, or N/A with reason.
4. Every FAIL must be fixed before proceeding. Apply fixes, then re-check that item.
5. When all items are PASS or N/A, proceed to Step 6.

For an independent check, spawn a subagent to run the audit (see delegation-map.md).

**Output:** Completed checklist with all items PASS or N/A.

---

## Step 6: Deliver

**Goal:** Hand off the finished skill with full documentation.

Present to the user:

1. **File map** — every file created, with its purpose.
2. **Skill type** — classification and why it fits.
3. **Degree of freedom** — assessment and reasoning.
4. **Gotchas seeded** — initial gotchas captured.
5. **Audit summary** — "All 38 items: N passed, M N/A."
6. **Maintenance notes** — what to watch for in future usage that might warrant iteration.
7. **Suggested first test** — a concrete task to try with Claude B.
