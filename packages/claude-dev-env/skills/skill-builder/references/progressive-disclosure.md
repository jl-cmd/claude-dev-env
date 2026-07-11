# Progressive Disclosure

Source A: [Anthropic — Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
Source B: [Lessons from Building Claude Code](thariq-x-post-skills.json)

## Core concept

> Source A: "SKILL.md serves as an overview that points Claude to detailed materials as needed, like a table of contents in an onboarding guide."

> Source A: "At startup, only the metadata (name and description) from all Skills is pre-loaded. Claude reads SKILL.md only when the Skill becomes relevant, and reads additional files only as needed."

> Source B: "You should think of the entire file system as a form of context engineering and progressive disclosure."

## Standard folder conventions

Every skill is a folder. These are the standard subdirectories, each with a specific role:

| Directory | Purpose | When to use |
|---|---|---|
| `SKILL.md` | Hub — overview, gotchas, process, file index | Always |
| `reference/` | Deep-dive reference material loaded on demand | Domain knowledge, API surfaces, schemas |
| `scripts/` | Executable scripts (executed, not read into context) | Deterministic operations, validators, helpers |
| `workflows/` | Multi-step sub-workflows for different scenarios | Complex branching processes |
| `templates/` | Output templates or file scaffolds to copy and fill | Structured output formats |
| `assets/` | Static data files, images, config templates | Reference data, configuration |
| `examples/` | Copy-pasteable examples and usage patterns | Library/API reference skills |

> Source A: "As your Skill grows, you can bundle additional content that Claude loads only when needed."

> Source B: "The simplest form of progressive disclosure is to point to other markdown files for Claude to use."

## The hub pattern

SKILL.md is an index, not a textbook. It tells Claude what exists and when to read it.

Observed in model skills (bugteam, pr-converge), the proven layout:

1. Core principle (one sentence)
2. Gotchas (highest-signal content)
3. When this skill applies (trigger + refusal)
4. The Process (checklist)
5. Skill type routing (if applicable)
6. Principles / constraints
7. File index (what every file does)
8. Folder map (end of file)

> Source B: "Tell Claude what files are in your skill, and it will read them at appropriate times."

## Three progressive disclosure patterns

### Pattern 1: High-level guide with references

> Source A: "Claude loads FORMS.md, REFERENCE.md, or EXAMPLES.md only when needed."

```markdown
## Quick start
[essential content inline]

## Advanced features
**Form filling**: See [FORMS.md](FORMS.md)
**API reference**: See [REFERENCE.md](REFERENCE.md)
**Examples**: See [EXAMPLES.md](EXAMPLES.md)
```

### Pattern 2: Domain-specific organization

> Source A: "When a user asks about sales metrics, Claude only needs to read sales-related schemas, not finance or marketing data."

```markdown
**Finance**: Revenue, ARR → See [reference/finance.md](reference/finance.md)
**Sales**: Pipeline, accounts → See [reference/sales.md](reference/sales.md)
**Product**: API usage, features → See [reference/product.md](reference/product.md)
```

### Pattern 3: Conditional details

> Source A: "Show basic content, link to advanced content."

```markdown
For simple edits, modify the XML directly.

**For tracked changes**: See [REDLINING.md](REDLINING.md)
**For OOXML details**: See [OOXML.md](OOXML.md)
```

## Hard rules

### 500-line cap on SKILL.md body

> Source A: "Keep SKILL.md body under 500 lines for optimal performance. If your content exceeds this, split it into separate files."

### One level deep

> Source A: "Keep references one level deep from SKILL.md. All reference files should link directly from SKILL.md."

> Source A: "Claude may partially read files when they're referenced from other referenced files. When encountering nested references, Claude might use commands like `head -100` to preview content rather than reading entire files, resulting in incomplete information."

**Bad:** `SKILL.md → advanced.md → details.md`
**Good:** `SKILL.md → advanced.md`, `SKILL.md → details.md`

### TOC for files over 100 lines

> Source A: "For reference files longer than 100 lines, include a table of contents at the top. This ensures Claude can see the full scope of available information even when previewing with partial reads."

### Forward slashes only

> Source A: "Always use forward slashes in file paths, even on Windows. Unix-style paths work across all platforms."

## File naming conventions

> Source A: "Name files descriptively: Use names that indicate content: `form_validation_rules.md`, not `doc2.md`."

> Source A: "Organize for discovery: Structure directories by domain or feature. Good: `reference/finance.md`, `reference/sales.md`. Bad: `docs/file1.md`, `docs/file2.md`."

## Scripts: execute vs read

> Source A: "Make clear in your instructions whether Claude should execute the script or read it as reference."

- **Execute:** "Run `analyze_form.py` to extract fields"
- **Read as reference:** "See `analyze_form.py` for the extraction algorithm"

> Source A: "For most utility scripts, execution is preferred because it's more reliable and efficient."
