# Polish Skill Workflow

Final optimization pass for a skill that is functionally complete.

## Prerequisites

- The skill has been used and observed
- The user is satisfied with output quality
- This is the final step before the skill is considered done

---

## Step 1: Description Audit

**Goal:** Verify the description field is optimized for model discovery.

> "The description is critical for skill selection: Claude uses it to choose the right Skill from potentially 100+ available Skills."

> "The description field is not a summary — it's a description of when to trigger."

Check each requirement:

- [ ] **Third person.** "Processes Excel files" not "I can help you process Excel files."
- [ ] **Includes what AND when.** Both the capability and trigger contexts.
- [ ] **Specific trigger phrases.** Different phrasings of the same intent should all match.
- [ ] **Under 1024 characters.** Hard limit.
- [ ] **No XML tags.**
- [ ] **Distinguishable from similar skills.** If two skills overlap, the descriptions must make the boundary clear.

### Trigger phrase review

Generate 10 variations of the user's intent:
- Formal and casual phrasings
- Cases where the user doesn't explicitly name the skill but clearly needs it
- Cases where this skill competes with another but should win

For each, answer: would the current description cause Claude to select this skill?

Also check 5 near-miss phrasings — adjacent domains where this skill should NOT trigger. Verify the description doesn't cause false activation.

### Fix issues

If the description fails any check, revise it. Show before/after with the specific change and why it improves discovery.

**Output:** Verified description (and revised version if changes were made).

---

## Step 2: Progressive Disclosure Audit

**Goal:** Verify the file structure follows all progressive disclosure rules.

Apply the hard rules and hub pattern in `${CLAUDE_SKILL_DIR}/references/progressive-disclosure.md`. Cross-check progressive-disclosure items on `${CLAUDE_SKILL_DIR}/references/self-audit-checklist.md`.

### Fix structural issues

If any check fails, restructure. Common fixes:
- SKILL.md too long → move sections to companion files, leave links.
- Nested references → surface all links to SKILL.md.
- Missing TOC → add to files over 100 lines.

**Output:** Verified file structure (and restructured files if changes were made).

---

## Step 3: Gotcha Freshness

**Goal:** Ensure gotchas reflect current observations.

> "Ideally, you will update your skill over time to capture these gotchas."

- Review the skill's Gotchas section.
- Check against recent usage: are there new failure modes not yet captured?
- Remove gotchas for issues that no longer occur (the skill fixed them).
- Verify each gotcha is actionable — a reader should know what to avoid and why.

**Output:** Updated gotchas section (and any new gotchas for skill-builder itself).

---

## Step 4: Full Self-Audit

**Goal:** Complete 33-point checklist pass.

Same as new-skill Step 5 and improve-skill Step 5:

1. Read `${CLAUDE_SKILL_DIR}/references/self-audit-checklist.md`.
2. Check every item. Fix failures. Re-check.
3. All items must be PASS or N/A.

**Output:** Completed checklist.

---

## Step 5: Deliver

**Goal:** Final summary of the polished skill.

Present to the user:

1. **Description** — final version, confirmed trigger phrases.
2. **File structure** — folder map with line counts.
3. **Gotchas** — current gotcha count and most recent additions.
4. **Audit summary** — "All 33 items: N passed, M N/A."
5. **Before/after** — description changes if any, structural changes if any.
6. **Maintenance notes** — what to watch for, when to re-audit.
