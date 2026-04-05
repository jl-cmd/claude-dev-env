---
name: rule-creator
description: "Creates or hardens Codex rules in .Codex/rules/*.md. Analyzes behavioral patterns and converts them into persistent, enforceable rule files. Triggers: 'create rule', 'add rule', 'harden rule', 'enforce rule', 'new rule'."
---

# Rule Creator

## Overview

Creates well-structured `.Codex/rules/*.md` files that Codex loads into every session.

**Core principle:** Rules encode "always true" behaviors. A rule eliminates repeated manual prompting by making the instruction persistent and automatic.

**Announce at start:** "I'm using the rule-creator skill to [create/harden] a rule."

**Context:** Rules are loaded at session start. They complement AGENTS.md (high-level project instructions) and skills (on-demand workflows). Use rules for behavioral constraints that must always be active.

## The Process

### Step 1: Understand the Need

Before writing, clarify:

1. **What behavior** should this rule enforce or prevent?
2. **Why** is it needed? (What goes wrong without it? What do you manually correct?)
3. **Scope** — all projects (`~/.Codex/rules/`) or project-specific (`.Codex/rules/`)?
4. **Path-scoped?** — does it only apply to certain file types?

### Step 2: Check for Overlap

Search existing rules before creating a new one:

1. Read `~/.Codex/rules/*.md` and `.Codex/rules/*.md`
2. Read AGENTS.md for related instructions
3. If overlap exists: **harden the existing rule** instead of creating a duplicate

### Step 3: Write the Rule

Follow these principles from Anthropic's prompting best practices and Codex docs:

**Structure:**
- Optional YAML frontmatter (only if path-scoped or needs `alwaysApply`)
- Markdown with headers and bullets
- Target under 50 lines per rule file (rules are loaded every session — token cost matters)

**Writing principles (source: [Anthropic Prompting Best Practices](https://platform.Codex.com/docs/en/build-with-Codex/prompt-engineering/Codex-prompting-best-practices)):**

1. **Tell what TO do, not what NOT to do.** Positive instructions outperform negative ones.
   - Instead of: "Do not guess CSS selectors"
   - Write: "Read the actual HTML source before writing any CSS selector"

2. **Add context/motivation (WHY).** Codex generalizes from explanations.
   - Instead of: "NEVER use ellipses"
   - Write: "Never use ellipses because the text-to-speech engine cannot pronounce them"

3. **Be specific enough to verify.** Vague rules get ignored.
   - Instead of: "Write clean code"
   - Write: "Use 2-space indentation, no trailing whitespace"

4. **Use XML tags for critical constraints.** Wrap non-negotiable rules in semantic tags.
   ```
   <investigate_before_answering>
   Read referenced files before making claims about their contents.
   </investigate_before_answering>
   ```

5. **Dial back aggressive language for the current model.** The model overtriggers on "CRITICAL", "MUST", "ALWAYS" — use normal prompting unless enforcement truly requires it.

**Frontmatter reference:**
```yaml
# Path-scoped rule (loads only when matching files are opened):
---
paths:
  - "src/api/**/*.ts"
---

# Always-apply rule (loads every session, no conditions):
# Simply omit frontmatter entirely — rules without frontmatter load unconditionally.

# AVOID using alwaysApply: false — it makes the rule load-on-demand only,
# which means it may never activate unless Codex happens to read matching files.
```

### Step 4: Choose Filename

- Lowercase, hyphens only: `investigate-first.md`, `parallel-tools.md`
- Descriptive of the behavior: name after what the rule DOES, not the problem it prevents
- Match naming convention of existing rules in the target directory

### Step 5: Validate

Before writing the file:

- [ ] Under 50 lines (concise enough to load every session without waste)
- [ ] Positive instructions (tells what TO do)
- [ ] Includes WHY context where non-obvious
- [ ] Specific enough to verify compliance
- [ ] No overlap with existing rules or AGENTS.md
- [ ] No frontmatter if it should always load (omit = unconditional)
- [ ] Path-scoped frontmatter only if genuinely file-type-specific

### Step 6: Write and Confirm

1. Write the rule to the target directory
2. Show the user the final content for review
3. Note: rules take effect on the NEXT session (Codex caches at startup)

## Hardening Existing Rules

When a rule exists but isn't being followed:

1. **Check frontmatter** — `alwaysApply: false` prevents auto-loading. Remove it.
2. **Check for conflicts** — contradictory rules in other files cause arbitrary behavior
3. **Add WHY context** — unexplained rules get lower adherence
4. **Reframe as positive** — convert "NEVER do X" to "Always do Y instead"
5. **Add XML wrapper** — for critical rules, semantic tags improve parsing:
   ```xml
   <rule_name>
   Instruction here.
   </rule_name>
   ```
6. **Reduce aggressive language** — the current model overtriggers on "CRITICAL/MUST/ALWAYS". Use direct, normal language unless the rule truly requires absolute enforcement.

## Red Flags — STOP

- Rule duplicates something already in AGENTS.md or another rule
- Rule is over 50 lines (split it or move details to a referenced doc)
- Rule uses only negative instructions ("NEVER", "DON'T") without positive alternatives
- Rule has `alwaysApply: false` for something that should always be active
- Rule is too vague to verify ("write good code")

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "This is already in AGENTS.md" | If it's not being followed, it needs a dedicated rule with WHY context |
| "The rule is short enough, no WHY needed" | WHY context improves adherence even for short rules — Codex generalizes from explanations |
| "I'll use CRITICAL/MUST to make it stronger" | the current model overtriggers on aggressive language. Direct, calm instructions work better. |
| "alwaysApply: false is fine, Codex will find it" | On-demand loading means the rule may never activate. Omit frontmatter for always-on rules. |

## Remember

- Omit frontmatter = always loads (this is what you want for most rules)
- `alwaysApply: false` = on-demand only (use sparingly)
- `paths:` frontmatter = loads when matching files are opened
- Positive instructions > negative instructions
- WHY context > bare commands
- Under 50 lines per rule file
- One behavior per rule file
- Rules take effect next session
