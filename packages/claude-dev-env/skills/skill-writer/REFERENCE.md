# Skill writer -- reference

## Canonical resources

When authoring or refining skills, ground decisions in these sources. If guidance conflicts, defer to the higher tier.

### Tier 1: Anthropic (primary authority for Claude)

- https://platform.claude.com/docs/en/claude-code/skills -- official skill structure, frontmatter fields, progressive disclosure, string substitutions, directory layout.
- https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices -- the single living reference for Claude's latest models. Covers XML tags, tool use, thinking, agentic systems, overeagerness, anti-hallucination.
- https://transformer-circuits.pub/2026/emotions/index.html -- emotion concepts research (April 2026): 171 internal activation patterns that causally influence behavior. Key skill-writing takeaways: clear criteria and escape routes improve output quality, collaborative framing activates engagement, positive task framing correlates with better results.
- https://platform.claude.com/docs/en/build-with-claude/adaptive-thinking -- adaptive thinking reference; replaces manual budget_tokens with effort-based control.

### Tier 2: Major labs (strong secondary, often transfers across models)

- https://platform.openai.com/docs/guides/prompt-engineering -- six strategies: clear instructions, reference text, split complex tasks, give models time to think, use external tools, test systematically.
- https://deepmind.google/research/ -- chain-of-thought and structured reasoning research.

### Tier 3: Community and individuals (supplementary)

- https://simonwillison.net/ -- practical LLM experiments, skill patterns, and automation insights.
- https://www.deeplearning.ai/short-courses/ -- foundational prompt engineering courses.
- https://www.latent.space/ -- AI engineering perspective.

### Conflict resolution rule

If sources disagree on a technique, apply in order: Anthropic documentation first (it describes the actual model behavior), then OpenAI/Google/Microsoft (large-scale research with cross-model relevance), then community sources (patterns and intuition, not authoritative on model internals). When Tier 3 contradicts Tier 1, Tier 1 wins without exception.

---

## Complete frontmatter fields

Source: [Claude Code Skills](https://platform.claude.com/docs/en/claude-code/skills)

### Required fields

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| `name` | string | Lowercase, hyphens, numbers. Max 64 chars. No `anthropic` or `claude`. | Must match directory name. Prefer gerund form. |
| `description` | string | Max 1024 chars. Third person. No XML tags. | What it does + when to use it + trigger phrases. |

### Optional fields

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
| `shell` | string | `bash` | Shell for `` !`command` `` blocks. `bash` or `powershell` |
| `hooks` | object | (none) | Hooks scoped to this skill's lifecycle |

### String substitutions (available in SKILL.md body)

| Variable | Description |
|----------|-------------|
| `$ARGUMENTS` | All arguments passed when invoking |
| `$ARGUMENTS[N]` | Specific argument by 0-based index |
| `$N` | Shorthand for `$ARGUMENTS[N]` (e.g., `$0`, `$1`) |
| `${CLAUDE_SESSION_ID}` | Current session ID |
| `${CLAUDE_SKILL_DIR}` | Directory containing SKILL.md |
| `` !`command` `` | Dynamic context injection -- shell command runs before Claude sees content |

### Permission syntax

```
Skill(name)        # Allow exact skill
Skill(name *)      # Allow skill with any arguments
```

---

## Progressive disclosure architecture

Source: [Claude Code Skills](https://platform.claude.com/docs/en/claude-code/skills)

Skills load in three levels to minimize context usage:

| Level | What loads | Token cost | When |
|-------|-----------|------------|------|
| **1. Metadata** | `name` and `description` from frontmatter | ~100 tokens | Always (system prompt) |
| **2. Instructions** | SKILL.md body | <5k tokens | When triggered by matching request |
| **3. Resources** | Additional files, scripts, schemas | Unlimited | When referenced from instructions |

### Implications for skill authors

- Many skills can coexist with minimal context cost (~100 tokens each at Level 1)
- SKILL.md body should stay under 500 lines to fit the <5k token budget
- Scripts execute via bash -- their code never enters context, only output does
- Reference files load only when Claude reads them via `@` reference or explicit Read
- Heavy lookup tables, field mappings, and long examples belong in REFERENCE.md or separate files

---

## Content templates by degree of freedom

### High freedom (advisory)

For guidance where multiple approaches are valid. States goals and acceptance criteria without prescribing exact steps.

```markdown
---
name: analyzing-data
description: >-
  Analyzes datasets and generates statistical summaries. Use when working
  with CSV or Excel data requiring descriptive statistics, correlations,
  or visualizations. Triggers: 'analyze data', 'statistical summary'.
---

# Analyzing data

**Core principle:** Let the data structure guide the analysis approach.

## When this skill applies

Trigger when the user has tabular data and wants statistical insight,
trend identification, or visualization.

## Goals

1. Inspect the data structure and report shape, types, missing values
2. Generate descriptive statistics appropriate to the data types
3. Identify correlations and patterns worth highlighting
4. Produce visualizations if requested

## Output format

Summary with key findings first, then supporting tables and charts.
Explain statistical choices so the user can evaluate appropriateness.

## Examples

**Input:** "Analyze sales_2024.csv for trends"
**Output:** Monthly trend summary, top performers, seasonal patterns,
with charts for the clearest visual signals.
```

### Medium freedom (structured workflow)

For preferred patterns with room for adaptation. States a recommended sequence but allows deviation when justified.

```markdown
---
name: reviewing-plans
description: >-
  Validates implementation plans against code standards and TDD compliance.
  Use after writing plans and before executing them.
  Triggers: 'review plan', 'validate plan', 'check plan'.
---

# Reviewing plans

**Core principle:** Bad plans produce bad code. Validate before executing.

## When this skill applies

Use after a plan has been written and before execution begins.
This is the quality gate between planning and implementation.

## The process

### Step 1: Locate plan files
Find plan files in `.planning/phases/` or `docs/plans/`.

### Step 2: Review dimensions
Check each dimension: structure completeness, TDD compliance,
code quality standards, right-sized engineering, task granularity.

### Step 3: Report verdict
Deliver READY or NEEDS REVISION with specific issues and locations.

## Output format

| Dimension | Status | Notes |
|-----------|--------|-------|
| Structure | PASS/FAIL | [specific finding] |
| TDD | PASS/FAIL | [specific finding] |
| Code quality | PASS/FAIL | [specific finding] |
```

### Low freedom (exact sequence)

For fragile operations where deviation causes silent failures. States precisely what to do, in what order, with validation at each step.

```markdown
---
name: filling-pdf-forms
description: >-
  Fills PDF forms using pdf-lib with exact field mapping and validation.
  Use when populating PDF forms programmatically.
  Triggers: 'fill PDF form', 'populate form', 'form filling'.
allowed-tools: Bash(node *), Read
---

# Filling PDF forms

**Core principle:** Extract field names first, then map, then fill.
Guessing field names produces silently empty forms.

## Before filling any form

1. Read `${CLAUDE_SKILL_DIR}/FORMS.md` for the field mapping reference
2. Extract field names: `node ${CLAUDE_SKILL_DIR}/scripts/extract_fields.js input.pdf`
3. Match extracted fields against the mapping before writing any fill code

## Workflow

### Step 1: Extract fields
```bash
node ${CLAUDE_SKILL_DIR}/scripts/extract_fields.js "$0"
```

### Step 2: Generate fill script
Use the field mapping from FORMS.md. Set every field explicitly.

### Step 3: Execute and validate
```bash
node fill_script.js && node ${CLAUDE_SKILL_DIR}/scripts/validate_fill.js output.pdf
```

### If validation fails
Read error output, fix the field mapping, re-execute, re-validate.
Do not proceed with a partially filled form.
```

---

## Validation checklist

Source: [Claude Code Skills](https://platform.claude.com/docs/en/claude-code/skills)

### Structure
- [ ] SKILL.md in correct location (matches `name` directory)
- [ ] Valid YAML frontmatter with required fields
- [ ] Body under 500 lines
- [ ] Heavy content in separate reference files

### Description quality
- [ ] Third person ("Analyzes..." not "Analyze...")
- [ ] Includes what it does and when to use it
- [ ] Contains trigger phrases matching natural user language
- [ ] Under 1024 characters
- [ ] No XML tags in description

### Content quality
- [ ] Core principle stated (one sentence)
- [ ] Steps are sequential and numbered
- [ ] States desired behavior in positive terms
- [ ] Motivation provided for constraints (why, not just what)
- [ ] Examples are concrete with specific inputs and outputs
- [ ] No time-sensitive claims (or clearly dated)
- [ ] Consistent terminology throughout
- [ ] File references are one level deep from SKILL.md
- [ ] Files over 100 lines have a table of contents

### Technical correctness
- [ ] `allowed-tools` specified if skill needs specific tools
- [ ] `argument-hint` included if skill accepts arguments
- [ ] `paths` set if skill applies only to certain file types
- [ ] String substitutions use correct syntax
- [ ] Script references use `${CLAUDE_SKILL_DIR}` for portability
- [ ] MCP tools use fully qualified names (`ServerName:tool_name`)

### Testing readiness
- [ ] At least 3 evaluation scenarios identified
- [ ] Covers a typical case, an edge case, and a decline/clarify case
- [ ] Golden rule: a colleague could follow this skill without extra context

---

## Evaluation loop

For skill drafts that need iteration:

1. Trigger the skill with 2-3 representative user requests.
2. Note failure modes (missed triggers, wrong output format, overstepped scope).
3. Tighten trigger phrases, add examples, or adjust degree of freedom for the failure class only.

Anthropic's **self-correction chaining** pattern extends this: generate a draft, have Claude review it against the validation checklist, then refine based on the review.
