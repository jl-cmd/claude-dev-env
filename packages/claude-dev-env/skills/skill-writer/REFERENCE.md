# Skill Writer Reference

## Table of Contents

1. [Complete Frontmatter Fields](#complete-frontmatter-fields)
2. [Progressive Disclosure Architecture](#progressive-disclosure-architecture)
3. [Content Templates by Degree of Freedom](#content-templates)
4. [Validation Checklist](#validation-checklist)

---

## Complete Frontmatter Fields

Source: [Claude Code Skills](https://platform.claude.com/docs/en/claude-code/skills)

### Required Fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `name` | string | Lowercase, hyphens, numbers. Max 64 chars. No `anthropic` or `claude`. | Must match directory name. Prefer gerund form. |
| `description` | string | Max 1024 chars. Third person. No XML tags. | What it does + when to use it + trigger phrases. |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `allowed-tools` | string | (all tools) | Tools permitted without asking. E.g., `Read, Grep, Bash(python *)` |
| `context` | string | (inline) | Set to `fork` to run in isolated subagent (no conversation history) |
| `agent` | string | (default) | Subagent type when `context: fork` is set |
| `model` | string | (inherits) | Model override when skill is active |
| `effort` | string | (inherits) | `low`, `medium`, `high`, or `max` (Opus only) |
| `user-invocable` | boolean | `true` | Set `false` to hide from `/` menu (background knowledge only) |
| `disable-model-invocation` | boolean | `false` | Set `true` for manual-only via `/name` |
| `paths` | string/list | (all files) | Glob patterns limiting activation. E.g., `"*.py"` or `["*.ts", "*.tsx"]` |
| `argument-hint` | string | (none) | Autocomplete hint. E.g., `[filename] [format]` |
| `shell` | string | `bash` | Shell for `!`command`` blocks. `bash` or `powershell` |
| `hooks` | object | (none) | Hooks scoped to this skill's lifecycle |

### String Substitutions (available in SKILL.md body)

| Variable | Description |
|----------|-------------|
| `$ARGUMENTS` | All arguments passed when invoking |
| `$ARGUMENTS[N]` | Specific argument by 0-based index |
| `$N` | Shorthand for `$ARGUMENTS[N]` (e.g., `$0`, `$1`) |
| `${CLAUDE_SESSION_ID}` | Current session ID |
| `${CLAUDE_SKILL_DIR}` | Directory containing SKILL.md |
| `` !`command` `` | Dynamic context injection - shell command runs before Claude sees content |

### Permission Syntax

```
Skill(name)        # Allow exact skill
Skill(name *)      # Allow skill with any arguments
```

---

## Progressive Disclosure Architecture

Source: [Agent Skills Overview](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)

Skills load in three levels to minimize context usage:

| Level | What Loads | Token Cost | When |
|-------|-----------|------------|------|
| **1. Metadata** | `name` and `description` from frontmatter | ~100 tokens | Always (system prompt) |
| **2. Instructions** | SKILL.md body | <5k tokens | When triggered by matching request |
| **3. Resources** | Additional files, scripts, schemas | Unlimited | When referenced from instructions |

### Key implications:
- You can install many skills with minimal context cost (~100 tokens each)
- SKILL.md body should stay under 500 lines
- Scripts execute via bash - their code never enters context, only output does
- Reference files load only when Claude reads them

---

## Content Templates

### High Freedom (Advisory)

Best for guidance where multiple approaches are valid.

```markdown
---
name: analyzing-data
description: "Analyzes datasets and generates statistical summaries. Use when working with CSV or Excel data requiring descriptive statistics, correlations, or visualizations."
---

# Analyzing Data

## Overview

Performs statistical analysis on tabular datasets.

**Announce at start:** "I'm using the analyzing-data skill."

## Instructions

1. Load and inspect the data structure
2. Generate descriptive statistics
3. Identify correlations and patterns
4. Produce visualizations if requested

## Examples

**Input:** "Analyze sales_2024.csv for trends"
**Output:** Summary statistics, monthly trend chart, top performers

## Best Practices

- Always show data shape and types before analysis
- Handle missing values explicitly
- Use appropriate chart types for the data
```

### Medium Freedom (Structured Workflow)

Best for preferred patterns with some variation allowed.

```markdown
---
name: reviewing-plans
description: "Validates implementation plans against code standards, TDD compliance, and right-sized engineering. Use after writing plans and before executing them. Triggers: 'review plan', 'validate plan', 'check plan'."
---

# Reviewing Plans

## Overview

**Core principle:** Bad plans produce bad code. Review before you execute.

**Announce at start:** "I'm using the reviewing-plans skill to validate this plan."

**Context:** Use after write-plan and before plan-executor. Quality gate between planning and implementation.

## The Process

### Step 1: Identify Plan Files
Locate plan files in `.planning/phases/` or `docs/plans/`.

### Step 2: Review Dimensions
Check structure, TDD compliance, code quality, right-sized engineering, task granularity.

### Step 3: Report Verdict
READY or NEEDS REVISION with specific issues.

## Output Format

| Dimension | Status |
|-----------|--------|
| Structure | PASS/FAIL |
| TDD | PASS/FAIL |
| Code quality | PASS/FAIL |

## Red Flags - STOP

- Any placeholder text ("implement later")
- Missing TDD steps for production code
- Magic values in code blocks

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "The plan is high-level" | Plans without complete code produce inconsistent implementations |
| "TDD makes it too long" | TDD in plan prevents skipping TDD during execution |
```

### Low Freedom (Critical/Exact)

Best for fragile operations where consistency is critical.

```markdown
---
name: filling-pdf-forms
description: "Fills PDF forms using pdf-lib JavaScript library with exact field mapping. Use when populating PDF forms programmatically. Triggers: 'fill PDF form', 'populate form', 'form filling'."
allowed-tools: Bash(node *), Read
---

# Filling PDF Forms

## MANDATORY PROTOCOL

Before filling ANY form:
1. [ ] Read `${CLAUDE_SKILL_DIR}/FORMS.md` for field mapping reference
2. [ ] Extract field names: `node ${CLAUDE_SKILL_DIR}/scripts/extract_fields.js input.pdf`
3. [ ] Match extracted fields against the mapping

## Workflow

### Step 1: Extract Fields
```bash
node ${CLAUDE_SKILL_DIR}/scripts/extract_fields.js "$0"
```

### Step 2: Generate Fill Script
Use the field mapping from FORMS.md. Every field must be explicitly set.

### Step 3: Execute and Validate
```bash
node fill_script.js && node ${CLAUDE_SKILL_DIR}/scripts/validate_fill.js output.pdf
```

### Feedback Loop
If validation fails -> read error output -> fix field mapping -> re-execute -> re-validate.

## Critical Rules

**NEVER guess field names.** Always extract first.
**WHY:** Wrong field names silently produce empty forms.
```

---

## Validation Checklist

Source: [Best Practices Checklist](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)

### Core Quality
- [ ] Description is specific, includes key terms, and is in **third person**
- [ ] Description includes both what the Skill does and when to use it
- [ ] SKILL.md body is **under 500 lines**
- [ ] Additional details are in separate files (if needed)
- [ ] No time-sensitive information (or clearly marked as legacy)
- [ ] Consistent terminology throughout
- [ ] Examples are concrete, not abstract
- [ ] File references are **one level deep** from SKILL.md
- [ ] Files >100 lines have a **table of contents**
- [ ] Workflows have clear steps
- [ ] All file paths use **forward slashes**

### Code and Scripts
- [ ] Scripts solve problems rather than punt to Claude
- [ ] Error handling is explicit and helpful
- [ ] No "voodoo constants" (all values justified)
- [ ] Required packages listed and verified as available
- [ ] MCP tools use **fully qualified names** (`ServerName:tool_name`)
- [ ] Validation/verification steps for critical operations
- [ ] Feedback loops included for quality-critical tasks

### Testing
- [ ] At least 3 evaluation scenarios created
- [ ] Tested with representative real tasks
- [ ] If multi-model: tested with Haiku, Sonnet, and Opus
