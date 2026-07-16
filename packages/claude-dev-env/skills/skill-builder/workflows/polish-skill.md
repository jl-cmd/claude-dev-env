# Polish Skill Workflow

Final optimization pass for a skill that is functionally complete.

## Prerequisites

- The skill has been used and observed
- The user is satisfied with output quality
- This is the final step before the skill is considered done

---

## Step 1: Description trigger-catalog audit

**Goal:** Rewrite the frontmatter `description` into a dense trigger catalog. Selection metadata only — not a story.

Read `${CLAUDE_SKILL_DIR}/references/description-field.md` and apply its checklist in full.

> "The description is critical for skill selection: Claude uses it to choose the right Skill from potentially 100+ available Skills."

> "The description field is not a summary — it's a description of when to trigger."

### Fail conditions (must rewrite)

- Multi-sentence narrative or benefits language ("helps you", "ensures reliable…")
- First or second person
- Process/implementation detail that belongs in the body
- Missing concrete trigger phrases
- Overlap with a sibling skill with no distinguishing tokens

### Required shape

```yaml
description: >-
  <capability tokens>. Triggers: <phrase>, <phrase>, <slash>, <filetype>.
```

### Description task seeds

Register each as a session task; complete with evidence (no markdown checkboxes):

- **Third person** — no I/you
- **Capability stem** — what tokens, ≤20 words, no story
- **Triggers list** — concrete phrases / slash forms / file types
- **Under 1024 characters** (prefer much shorter; always-on context)
- **No XML tags**
- **Not a story** — no narrative, benefits, or process dump
- **Sibling boundary** — distinguishable from related skills

### Trigger phrase review

Generate 10 variations of the user's intent:

- Formal and casual phrasings
- Cases where the user doesn't name the skill but clearly needs it
- Cases where this skill competes with another but should win

For each: would the current description select this skill?
If you aren't sure of user's intent, present options to the user via askuserquestion for trigger phases.

Also check 5 near-miss phrasings — adjacent domains that must not activate. Adjust Triggers tokens only as needed for boundary.

### Fix

If any check fails, rewrite. Show before/after. The after form must match `description-field.md` good examples.

**Output:** Final description string (trigger catalog).

---

## Step 2: Progressive disclosure, modularity, and deterministic audit

**Goal:** Verify within-skill structure, cross-skill modularity, and deterministic placement.

1. Apply hard rules in `${CLAUDE_SKILL_DIR}/references/progressive-disclosure.md`.
2. Apply modularity rules in `${CLAUDE_SKILL_DIR}/references/skill-modularity.md`.
3. Apply deterministic-elements rules in `${CLAUDE_SKILL_DIR}/references/deterministic-elements.md`.
4. Cross-check matching items on `${CLAUDE_SKILL_DIR}/references/self-audit-checklist.md`.

### Common fixes

- SKILL.md too long → move sections to companion files, leave links
- Nested references → surface all links on SKILL.md
- Missing TOC → add to files over 100 lines
- Multi-capability package → split or orchestrator + named sub-skills
- Silent reimplementation → invoke peer skill by name; add Sub-skills table
- Mechanical sequence / fenced program / giant detector only in body → extract to `scripts/` or `workflow/`; point from process steps; add paired tests and `*_constants/` as needed
- Verbatim templates inline → `templates/`; long fixed tables → `reference/`
- Markdown `- [ ]` progress boards → plain task-seed list + seed instruction (`TaskCreate` / `TodoWrite`)

**Output:** Verified structure, composition, and deterministic placement (and edits if needed).

---

## Step 3: Gotcha freshness

**Goal:** Ensure gotchas reflect current observations.

> "Ideally, you will update your skill over time to capture these gotchas."

- Review the skill's Gotchas section.
- Check against recent usage: are there new failure modes not yet captured?
- Remove gotchas for issues that no longer occur (the skill fixed them).
- Verify each gotcha is actionable — a reader should know what to avoid and why.
- Verify they are relevant by going over them 1 by 1 with the user via AskUserQuestion.

**Output:** Updated gotchas section (and any new gotchas for skill-builder itself).

---

## Step 4: Full self-audit

**Goal:** Complete checklist pass including description, modularity, and deterministic items.

Same as new-skill Step 5 and improve-skill Step 5:

1. Read `${CLAUDE_SKILL_DIR}/references/self-audit-checklist.md`.
2. Register every bullet as a session task; complete with evidence. Fix failures. Re-complete.
3. All items must be PASS or N/A.
4. Description items, modularity items, and process-step classification are never N/A for a delivered skill (sub-skills table alone may be N/A for pure leaf skills; script/test rows are N/A only when the package has zero code files and every step is judgment).

**Output:** Audit summary; all PASS or N/A.

---

## Step 5: Deliver

**Goal:** Final summary of the polished skill.

Present to the user:

1. **Description** — final trigger-catalog string (paste it).
2. **Composition** — sub-skills or leaf status.
3. **Deterministic inventory** — any extracts to scripts/templates/reference.
4. **File structure** — folder map with line counts.
5. **Gotchas** — current gotcha count and most recent additions.
6. **Audit summary** — "All checklist items: N passed, M N/A."
7. **Before/after** — description rewrite and structural changes if any.
8. **Maintenance notes** — what to watch for, when to re-audit.
