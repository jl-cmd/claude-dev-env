---
name: skill-writer
description: >-
  Write, create, or improve Claude Code skills (SKILL.md files) with correct
  frontmatter, progressive disclosure, and prompt-engineering principles.
  Covers workflow skills, enforcement rules, advisory guidance, reference
  lookups, and automation scripts.
---
@packages/claude-dev-env/skills/skill-writer/REFERENCE.md

# Skill writer

**Core principle:** A skill is a prompt -- the SKILL.md body is injected into Claude's context when triggered. The same principles that make prompts effective make skills effective.

**Canonical source:** https://platform.claude.com/docs/en/claude-code/skills -- the official reference for skill structure, frontmatter fields, progressive disclosure, and string substitutions.

## Skill-only output rule (overrides all other delivery instructions)

This skill produces skill artifacts. It does not perform the underlying task the skill would automate.

When this skill is active, your response contains exactly one of:
1. **Clarifying questions** to gather information needed to write a better skill (Step 3) -- then stop and wait.
2. **The skill artifact** in fenced code blocks (SKILL.md and optionally REFERENCE.md) -- then stop.

Prohibited responses: executing the task the skill would automate, proposing implementation changes unrelated to skill authoring, explaining what *you would do* to accomplish the underlying task.

## When this skill applies

Trigger for any request to **author**, **refine**, or **restructure** a Claude Code skill: SKILL.md files, skill frontmatter, skill body content, reference files, or skill directory structure.

Use this skill when the user needs a structured skill artifact; for quick answers about skill syntax, answer directly in plain text.

When invoked with arguments (e.g. `/skill-writer improve this: [paste]`), treat `$ARGUMENTS` as the skill content to refine.

### Ground-up multi-file packages (required)

When the user is creating a **new** skill as a **package** (workspace with `ARCHITECTURE.md`, `REFERENCE.md`, `EXAMPLES.md`, `WORKFLOWS.md`, `evals/*.json`, per-file human review), **before** drafting `SKILL.md`:

1. Read `packages/claude-dev-env/skills/prompt-generator/templates/skill-from-ground-up.md` (installed layout: sibling folder `prompt-generator/templates/skill-from-ground-up.md` under the same `skills/` parent).
2. Ensure `/prompt-generator` has run with that template filled so architecture-first steps, checkpoint gates, and eval evidence rules are already agreed.

If the task is **only** editing an existing `SKILL.md` or a small single-file tweak, this subsection does not apply.

### Refinement multi-file packages (required)

When the user is **refining** an existing skill as a **package** (baseline skill directory, `ARCHITECTURE.md` with planned deltas, checkpointed updates to REFERENCE / EXAMPLES / WORKFLOWS / `evals/`), **before** rewriting multiple files:

1. Read `packages/claude-dev-env/skills/prompt-generator/templates/skill-refinement-package.md` (installed layout: `prompt-generator/templates/skill-refinement-package.md` under the same `skills/` parent).
2. Ensure `/prompt-generator` has run with that template filled so baseline root, workspace root, observation inputs, and evidence rules are fixed before edits proceed.

If the change set is a **small single-file** tweak, this subsection does not apply.

## Workflow (run in order)

### 1. Classify the skill type

Pick one primary:

| Type | Purpose | Example |
|------|---------|---------|
| `workflow` | Multi-step process with sequential phases | TDD enforcement, plan review, PR submission |
| `enforcement` | Rules that constrain behavior | Code standards, comment preservation, commit rules |
| `advisory` | Guidance where multiple approaches are valid | Best practices, design patterns, optimization tips |
| `reference` | Lookup material loaded on demand | API docs, field mappings, configuration tables |
| `automation` | Script-driven with tool calls | PDF form filling, browser automation, file processing |

### 2. Set degree of freedom

Match specificity to task fragility:

- **High:** Multiple valid approaches; use numbered goals and acceptance criteria. The skill states *what* to achieve, not *how*.
- **Medium:** Preferred pattern exists; use structured steps with room for adaptation. The skill states a recommended approach but allows deviation when justified.
- **Low:** Fragile or safety-critical; use exact steps, exact field names, and boundary constraints. The skill states precisely what to do and what not to do.

### 3. Collect missing facts

Ask 1-3 short questions if needed. Focus on:
- What capability does the skill provide? (one skill = one capability)
- When should the skill trigger? (specific phrases, file patterns, workflow position)
- What tools does the skill need? (Bash, Read, Grep, MCP tools)
- What does the skill produce? (output format, files created, state changes)
- Where does it fit in existing workflows? (before/after other skills)

### 4. Choose location

**Personal skills** (`~/.claude/skills/` or package-managed):
- Individual workflows, experimental skills, cross-project utilities

**Project skills** (`.claude/skills/`):
- Team conventions, project-specific expertise, committed to git

### 5. Write frontmatter

Apply official constraints from the canonical source:

```yaml
---
name: skill-name-here
description: >-
  [What it does] in third person. [When to use it].
  Triggers: '[phrase 1]', '[phrase 2]', '[phrase 3]'.
---
```

**Name:** lowercase, hyphens, numbers only. Max 64 chars. No `anthropic` or `claude`. Must match directory name.

**Description:** max 1024 chars. Third person. No XML tags. Include trigger phrases that match how users naturally ask for this capability.

**Optional fields** -- include only when needed:
- `allowed-tools` -- when the skill requires specific tools (e.g., `Bash(node *), Read`)
- `argument-hint` -- when the skill accepts arguments (e.g., `[filename] [format]`)
- `paths` -- when the skill applies only to certain file types (e.g., `"*.py"` or `["*.ts", "*.tsx"]`)
- `context: fork` -- when the skill needs isolated execution without conversation history
- `disable-model-invocation: true` -- when the skill should only trigger via explicit `/name` invocation
- `effort` -- when the skill benefits from a specific thinking depth (`low`, `medium`, `high`, `max`)

See REFERENCE.md for the complete field table with types, defaults, and constraints.

### 6. Build the skill body

Apply prompt-engineering principles -- a skill body is a prompt. Source: https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices

**Structure with XML section tags** where content mixes instructions, context, and examples. Anthropic: "Use consistent, descriptive tag names across your prompts. Nest tags when content has a natural hierarchy." For skills under ~20 lines, use concise plain structure instead.

**Set a role** when the skill benefits from focused behavior. Anthropic: "Setting a role in the system prompt focuses Claude's behavior and tone for your use case. Even a single sentence makes a difference."

**Add motivation behind constraints.** Anthropic: "Providing context or motivation behind your instructions... can help Claude better understand your goals and deliver more targeted responses." State *why* a rule exists, not just *what* it forbids.

**Frame positively.** State the desired behavior directly. Anthropic: "Your response should be composed of smoothly flowing prose paragraphs" provides clearer guidance than a prohibition-only instruction. Write "validate field names before filling" rather than "never guess field names."

**Emotion-informed framing.** Anthropic's emotion concepts research (2026) found internal activation patterns that causally influence output quality. Apply to skill writing: (1) provide clear success criteria and escape routes; (2) use collaborative framing; (3) frame tasks as interesting problems; (4) invite transparency -- include "say so if you're unsure" when appropriate; (5) use constructive, forward-looking tone.

**Golden rule check.** Anthropic: "Show your prompt to a colleague with minimal context on the task and ask them to follow it. If they'd be confused, Claude will be too." Apply the same test to the skill body.

**Progressive disclosure.** Keep the SKILL.md body under 500 lines. Move heavy content (field tables, long examples, lookup data, scripts) into REFERENCE.md or separate files that load only when referenced.

#### Body structure template

```markdown
# Skill Name

**Core principle:** [One sentence capturing the essential insight]

## When this skill applies
[Trigger conditions, workflow position]

## The Process

### Step 1: [First Action]
[Instructions -- narrative, not verbose checklists]

### Step 2: [Second Action]
[Continue with clear sequential steps]

## Output Format
[What the skill produces -- be specific]

## Examples
[3-5 concrete scenarios with inputs and expected outputs]
```

### 7. Control output format

If the skill produces structured output, specify the format explicitly. Use XML format indicators when the skill should produce tagged sections. Match the formatting style in the skill body to the desired output style -- Anthropic notes the prompt's own formatting influences the response.

### 8. Add examples

Include 3-5 concrete examples showing the skill in action. Wrap in `<example>` tags with diverse, representative inputs. Anthropic: "Include 3-5 examples for best results. You can also ask Claude to evaluate your examples for relevance and diversity."

Examples should cover:
- A typical use case
- An edge case or boundary condition
- A case where the skill should decline or ask for clarification

### 9. Self-check

Before delivering, verify against this rubric:

- [ ] Description is third person with trigger phrases
- [ ] Under 500 lines
- [ ] States what to do in positive terms (not prohibition-heavy)
- [ ] Degree of freedom matches task fragility
- [ ] Progressive disclosure used (heavy content in REFERENCE.md)
- [ ] No time-sensitive claims unless clearly dated
- [ ] Examples are concrete, not abstract
- [ ] Frontmatter fields are valid per official docs
- [ ] If tools needed: specifies `allowed-tools`
- [ ] If arguments expected: includes `argument-hint`
- [ ] Workflow steps are sequential and numbered
- [ ] Golden rule: a colleague could follow this skill without extra context
- [ ] Motivation provided for constraints (why, not just what)
- [ ] One skill = one capability (not a bundle of loosely related features)
- [ ] String substitutions used correctly (`$ARGUMENTS`, `${CLAUDE_SKILL_DIR}`, etc.)

### 10. Deliver

Final artifact as **fenced code blocks** the user can paste as-is: one block for SKILL.md, optionally one for REFERENCE.md. The fenced blocks are your entire response -- no surrounding commentary or explanation.

## Claude 4.6 considerations

When writing skills for current Claude models, apply these patterns:

- **Overtriggering:** Dial back aggressive language. Anthropic: "Where you might have said 'CRITICAL: You MUST use this tool when...', you can use more normal prompting like 'Use this tool when...'." Skills that shout get ignored or cause erratic behavior -- write in a direct, conversational tone.
- **Overeagerness:** Include scope constraints. Anthropic: "Claude Opus 4.5 and Claude Opus 4.6 have a tendency to overengineer by creating extra files, adding unnecessary abstractions, or building in flexibility that wasn't requested." Skills should state their boundary clearly.
- **Overthinking:** Anthropic: "Replace blanket defaults with more targeted instructions. Instead of 'Default to using [tool],' add guidance like 'Use [tool] when it would enhance your understanding of the problem.'" Write conditional triggers, not blanket rules.
- **Conservative vs proactive action:** For skills that should act, use explicit language. For skills that should advise, include: "Default to providing information and recommendations. Proceed with changes only when the user explicitly requests them."

## Autonomy and safety pattern

For `automation` and `enforcement` skill types, include reversibility guidance. Anthropic provides this pattern:

```text
Consider the reversibility and potential impact of your actions. You are encouraged to take local, reversible actions like editing files or running tests, but for actions that are hard to reverse, affect shared systems, or could be destructive, ask the user before proceeding.
```

## Conflict resolution

When skill-writing guidance conflicts across sources, defer to the authority tier:

1. **Tier 1 (primary):** Anthropic -- the model provider's own documentation is authoritative for Claude behavior
2. **Tier 2 (strong secondary):** OpenAI, Google DeepMind, Microsoft Research -- major lab guidance often transfers across models
3. **Tier 3 (supplementary):** Community resources, courses, individual blogs -- valuable for patterns and intuition, not authoritative on model specifics
