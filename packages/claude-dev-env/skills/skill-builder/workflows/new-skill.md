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

**Goal:** Collect domain knowledge, failure patterns, gotchas, and a composition plan.

> "Build a Gotchas Section — these sections should be built up from common failure points that Claude runs into when using your skill."

Read `${CLAUDE_SKILL_DIR}/references/skill-modularity.md`, `${CLAUDE_SKILL_DIR}/references/description-field.md`, and `${CLAUDE_SKILL_DIR}/references/deterministic-elements.md` before the interview. Modularity, description triggers, and deterministic inventory are gates: do not proceed to Write until the composition plan, trigger catalog draft, and deterministic-elements inventory are filled.

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
9. "In one sentence, what is the single capability this skill owns?"
10. "Which existing skills already cover a step of this work? Which steps should this skill invoke by name?"
11. "Is this one skill, several skills, or a thin orchestrator that calls sub-skills?"
12. "What exact phrases, slash commands, or file types should select this skill?"
13. "Which steps of this work are fixed procedures (same inputs → same outputs, machine-checkable) versus open judgment?"

### Related-skills inventory

Scan installed skills and the package skill tree for names that touch the same domain. List each with: keep separate / invoke as sub-skill / absorb (with reason if absorb).

### Generate gap analysis

Use the template at `${CLAUDE_SKILL_DIR}/templates/gap-analysis.md`. Fill in:

- Skill type and degree of freedom
- Task description (one capability sentence)
- Gaps identified (what failed, what was needed)
- Recurring patterns across gaps
- Initial gotcha candidates
- **Composition plan** — capability sentence, related skills, sub-skills to invoke, split or orchestrator decision, missing sub-skills to create
- **Description triggers** — capability stem tokens + trigger phrase list (not story prose)
- **Deterministic elements inventory** — each process step classified; home path; paired test for code

### Assess degree of freedom

> "Match the level of specificity to the task’s fragility and variability."

| Degree | When | Example |
|---|---|---|
| High | Multiple valid approaches, context-dependent | Code review guidelines |
| Medium | Preferred pattern exists, some variation ok | Report generation with template |
| Low | Fragile operations, consistency critical | Database migration with exact script |

Record the assessment with reasoning.

### Modularity gate

Register each task seed from `skill-modularity.md` on the session task list (`TaskCreate` / `TodoWrite`). Complete with evidence. If the capability sentence needs an unrelated "and", stop and split scope with the user before Step 4.

### Description gate

Draft the frontmatter description using the template in `description-field.md`. Register each description task seed and complete with evidence. Story prose fails the gate.

### Deterministic-elements gate

Register each task seed under **Required task seeds** in `deterministic-elements.md`. Complete with evidence. Every deterministic step must have a planned `scripts/`, `workflow/`, `templates/`, `reference/`, or task-seed path. Prose-only mechanical sequences and markdown checkbox boards fail the gate.

**Output:** Completed gap analysis (composition plan + description triggers + deterministic inventory), initial gotchas, degree-of-freedom assessment, modularity gate done, draft description.

---

## Step 4: Write

**Goal:** Produce the skill package — SKILL.md and companion files.

Delegate to `/skill-writer` using the structured handoff from `${CLAUDE_SKILL_DIR}/references/delegation-map.md`.

The handoff must include: skill type, folder structure, gap analysis (composition plan + description triggers + deterministic inventory), initial gotchas, degree of freedom, constraints, sub-skills to name in SKILL.md, exact description string to put in frontmatter, script/test paths for every deterministic step.

After skill-writer produces the draft:

1. Verify it follows the hub layout (principle → gotchas → when-applies → process → file index → folder map).
2. Verify SKILL.md body is under 500 lines.
3. Verify all references are one level deep.
4. Verify files over 100 lines have a TOC.
5. Verify modularity: single capability, sub-skills table when composing, no silent reimplementation of inventoried skills.
6. Verify description is a trigger catalog per `description-field.md` (not story prose).
7. Verify deterministic inventory: every deterministic step has a real code/artifact/task-seed path; no prose-only mechanical sequences; no markdown checkbox boards for required work; scripts follow CODE_RULES and have paired tests.

Fix structural, modularity, description, and deterministic-element issues before proceeding.

**Output:** Complete skill package at the target directory.

---

## Step 5: Self-Audit

**Goal:** Verify every best practice is satisfied before delivery.

1. Read `${CLAUDE_SKILL_DIR}/references/self-audit-checklist.md`.
2. Register **every** bullet as a session task (`TaskCreate` / `TodoWrite`).
3. Complete each task against the built skill: PASS, FAIL with file:line evidence, or N/A with reason.
4. Every FAIL must be fixed before proceeding. Apply fixes, then re-open/complete that task.
5. When all tasks are PASS or N/A, proceed to Step 6.

For an independent check, spawn a subagent to run the audit (see delegation-map.md).

**Output:** Audit summary (PASS / N/A / FAIL-fixed counts). All items PASS or N/A.

---

## Step 6: Deliver

**Goal:** Hand off the finished skill with full documentation. Prompt user if they want a PR up with the skill.

Present to the user:

1. **File map** — every file created, with its purpose.
2. **Skill type** — classification and why it fits.
3. **Degree of freedom** — assessment and reasoning.
4. **Composition plan** — capability sentence, sub-skills invoked, any skills split out.
5. **Description** — final frontmatter trigger catalog (paste the string).
6. **Deterministic inventory** — steps classified; script/template/reference paths; tests for code.
7. **Gotchas seeded** — initial gotchas captured.
8. **Audit summary** — "All checklist items: N passed, M N/A."
9. **Maintenance notes** — what to watch for in future usage that might warrant iteration.
10. **Suggested first test** — a concrete task to try with Claude B.
