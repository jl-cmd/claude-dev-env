---
name: skill-writer
description: Guide users through creating Agent Skills for Codex. Use when the user wants to create, write, author, or design a new Skill, or needs help with SKILL.md files, frontmatter, or skill structure.
---

# Writing Skills

## Overview

Create well-structured Agent Skills for Codex that follow superpowers patterns and validation requirements.

**Core principle:** Skills encode expertise. A good skill prevents the same mistake from happening twice.

**Announce at start:** "I'm using the skill-writer skill to create a new skill."

**Context:** Skills complement agents. Skills are invoked inline; agents run as subprocesses. Use skills for workflows that need conversation context.

## The Process

### Step 1: Understand the Need

Ask clarifying questions (one at a time):

1. What specific capability should this Skill provide?
2. When should Codex use this Skill?
3. Is this critical (must follow exactly) or advisory (adapt to context)?
4. Does this fit in an existing workflow pipeline?

**Keep it focused:** One Skill = one capability
- Good: "PDF form filling", "plan review", "TDD enforcement"
- Too broad: "Document processing", "code quality"

### Step 2: Choose Format

**CRITICAL DECISION:** Advisory vs Superpowers format.

| Format | When to Use | Key Signals |
|--------|-------------|-------------|
| **Superpowers** | Rules that MUST be followed | Production failures if violated, anti-patterns to block, non-negotiable workflows |
| **Advisory** | Helpful guidance | Best practices, tips, adaptable to context |

**If in doubt:** If you're tempted to say "should" instead of "MUST", it's advisory.

### Step 3: Choose Location

**Personal Skills** (`~/.Codex/skills/`):
- Individual workflows
- Experimental skills

**Project Skills** (`.Codex/skills/`):
- Team conventions
- Project-specific expertise
- Committed to git

### Step 4: Write Frontmatter

```yaml
---
name: skill-name
description: [What it does] + [When to use it] + [Trigger phrases]
---
```

**Name rules:**
- Lowercase, hyphens only, max 64 chars
- Must match directory name

**Description formula:** `[What] + [When] + [Triggers]`

```yaml
# Good
description: Review implementation plans against AGENTS.md standards. Use after writing-plans and before executing-plans to validate TDD compliance and right-sized engineering.

# Bad
description: Helps with plans
```

### Step 5: Write Content

#### Superpowers Format Structure

```markdown
# Skill Name

## Overview

Brief description.

**Core principle:** [One sentence that captures the essential insight]

**Announce at start:** "I'm using the [skill] skill to [purpose]."

**Context:** [Where this fits in the workflow pipeline]

## The Process

### Step 1: [First Action]
[Narrative instructions, not verbose checklists]

### Step 2: [Second Action]
[Continue with clear steps]

## Output Format

[What the skill produces - be specific]

## After Completion

[What happens next - reference sub-skills if applicable]

**If [condition]:**
- [Action]
- **REQUIRED SUB-SKILL:** Use [skill-name]

## Red Flags - STOP

[List signals that mean something is wrong]

- [Red flag 1]
- [Red flag 2]

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "[Common shortcut]" | [Why it fails] |
| "[Another excuse]" | [Why it fails] |

## Remember

- [Key point 1]
- [Key point 2]
- [Key point 3]
```

#### Advisory Format Structure

```markdown
# Skill Name

## Overview

Brief description of what this Skill does.

**Announce at start:** "I'm using the [skill] skill."

## Instructions

Step-by-step guidance:
1. First step
2. Second step
3. Handle edge cases

## Examples

Concrete usage examples.

## Best practices

- Key conventions
- Common pitfalls
```

#### Ironclad Format (Critical Rules)

For skills where violations cause production failures:

```markdown
<EXTREMELY_IMPORTANT>
# Skill Name

**This skill is MANDATORY for [context].**

IF you are [doing task], YOU DO NOT HAVE A CHOICE. YOU MUST FOLLOW THIS SKILL.

## MANDATORY FIRST RESPONSE PROTOCOL

Before doing ANYTHING:

1. [ ] [First verification]
2. [ ] [Second verification]
3. [ ] [Third verification]

**Responding WITHOUT completing this checklist = automatic failure.**

## Critical Rules - NO EXCEPTIONS

### Rule 1: [Rule Name]

**NEVER [forbidden action].**

- [ ] FORBIDDEN: [specific example]
- [x] REQUIRED: [correct approach]

**WHY:** [Production consequence]

## Common Rationalizations That Mean You're About To Fail

- **"[Excuse 1]"** -> WRONG. [Reality]
- **"[Excuse 2]"** -> WRONG. [Reality]

</EXTREMELY_IMPORTANT>

---

## Implementation Guide

[Supporting material outside the critical wrapper]
```

### Step 6: Validate

**Structure:**
- [ ] SKILL.md in correct location
- [ ] Directory name matches `name` field
- [ ] Valid YAML frontmatter

**Content (Superpowers format):**
- [ ] Has Overview with Core principle
- [ ] Has "Announce at start"
- [ ] Has Context (pipeline placement)
- [ ] Steps are narrative, not verbose checklists
- [ ] Has Red Flags section
- [ ] Has Rationalization Prevention table
- [ ] Has Remember section
- [ ] References sub-skills where appropriate

**Content (Ironclad format):**
- [ ] `<EXTREMELY_IMPORTANT>` wrapper
- [ ] Absolute language ("MUST", "NEVER", "NO EXCEPTIONS")
- [ ] Checkbox protocol
- [ ] WHY explanations with consequences
- [ ] Rationalizations are specific, not generic

### Step 7: Test

1. Restart Codex to load the skill
2. Ask questions that should trigger it
3. Verify activation and behavior

## Red Flags - STOP

- Skill is too broad ("handles documents")
- No clear trigger phrases in description
- Steps say "consider" or "might" in Ironclad format
- No workflow context (where does this fit?)
- Rationalizations are generic ("I'll do it later")
- Missing WHY explanations for rules

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "This skill is simple, doesn't need structure" | Simple skills become complex. Structure prevents drift. |
| "I'll add the rationalization section later" | Later never comes. Add it now. |
| "Nobody will try to shortcut this" | Developers always shortcut. Block it proactively. |
| "The description is good enough" | Vague descriptions mean skill never activates. |
| "Advisory format is fine for critical rules" | Critical rules need Ironclad format or they get ignored. |

## Remember

- **Core principle first** - captures the essential insight
- **Announce at start** - makes skill usage visible
- **Context placement** - skills fit in pipelines
- **Red flags** - catch problems early
- **Rationalizations** - block shortcuts proactively
- **Sub-skill references** - connect to related workflows
- One skill = one capability
- Specific triggers in description
- Test activation before shipping
