# Polish Skill Workflow

Final optimization pass for a skill that is functionally complete.

## Prerequisites

- The skill passes its evaluation scenarios
- The user is satisfied with output quality
- This is the final step before the skill is considered done

---

## Step 1: Description Optimization

Optimize the skill's description for triggering accuracy using the skill-creator's trigger eval system.

### Generate trigger eval queries

Create 20 eval queries: 10 should-trigger and 10 should-not-trigger.

**Should-trigger queries (10):** Different phrasings of the same intent. Include:
- Formal and casual variations
- Cases where the user does not explicitly name the skill but clearly needs it
- Uncommon use cases
- Cases where this skill competes with another but should win

**Should-not-trigger queries (10):** Near-misses that share keywords but need something different. Include:
- Adjacent domains with overlapping terminology
- Ambiguous phrasing where naive keyword matching would falsely trigger
- Tasks that touch the skill's domain but in a context where another tool is better

All queries must be realistic -- detailed, specific, with file paths, personal context, casual speech. Not abstract one-liners.

### Review with user

Present the eval set using the skill-creator's HTML review template. See `${CLAUDE_SKILL_DIR}/references/delegation-map.md` for the exact process.

The user can edit queries, toggle should-trigger, and add/remove entries.

### Run optimization loop

See `${CLAUDE_SKILL_DIR}/references/delegation-map.md` for the exact command. The loop:
1. Splits eval set into 60% train / 40% held-out test
2. Evaluates current description (3 runs per query for reliability)
3. Proposes improvements based on failures
4. Re-evaluates on both train and test
5. Iterates up to 5 times
6. Selects best description by test score (avoids overfitting)

### Apply result

Update the skill's SKILL.md frontmatter with the optimized description. Show the user before/after with scores.

---

## Step 2: Final Validation

Run the skill-writer self-check rubric:

- [ ] Description is third person with trigger phrases
- [ ] SKILL.md body under 500 lines
- [ ] States what to do in positive terms (not prohibition-heavy)
- [ ] Degree of freedom matches task fragility
- [ ] Progressive disclosure used (heavy content in separate files)
- [ ] No time-sensitive claims unless clearly dated
- [ ] Examples are concrete, not abstract
- [ ] Frontmatter fields are valid per official docs
- [ ] One skill = one capability
- [ ] Consistent terminology throughout
- [ ] File references are one level deep from SKILL.md
- [ ] Files over 100 lines have a table of contents

---

## Step 3: Final Summary

Present the finished skill to the user:

1. **Benchmark summary:** Final pass rate vs baseline, with delta
2. **Gaps addressed:** Map each original gap to the skill content that addresses it
3. **Description optimization:** Before/after trigger accuracy scores
4. **Known limitations:** Anything the skill does not handle (scope boundaries)
5. **Maintenance notes:** What to watch for in future usage that might warrant re-iteration
