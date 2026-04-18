---
name: rule-audit
description: Audit AGENTS.md, rules, hooks, and docs across user and project layers for enforcement gaps, duplication, and compliance
user-invocable: true
disable-model-invocation: true
---

# Rule Audit

Full enforcement audit of AGENTS.md, `.Codex/rules/`, hooks (settings.json), and referenced docs.

Works across **two layers** — user-global (`~/.Codex/`) and project-local (cwd). Detects cross-layer duplication where project rules restate user rules, wasting instruction budget.

Produces a scored report with corrective actions.

## Phase 0: Layer Detection

Before launching agents, detect which layers exist:

```
User layer (always present):
  ~/.Codex/AGENTS.md
  ~/.Codex/rules/*.md
  ~/.Codex/settings.json (hooks)
  ~/.Codex/docs/*.md

Project layer (check cwd):
  <cwd>/AGENTS.md
  <cwd>/.Codex/AGENTS.md
  <cwd>/.Codex/rules/*.md
  <cwd>/.Codex/settings.json (project hooks)

If cwd == ~ (home directory), skip project layer (same as user layer).
If no project-layer files exist, report "single-layer audit (user only)".
If project-layer files exist, report "dual-layer audit (user + project)".
```

## Phase 1: Inventory (Parallel Discovery)

Launch 3 agents in parallel to inventory the full enforcement landscape.

If dual-layer: each agent inventories BOTH layers, tagging each file with its layer (`user` or `project`).

### Agent 1: Rules & AGENTS.md Inventory

Read and catalog every advisory-layer file:

```
User layer:
  ~/.Codex/AGENTS.md
  ~/.Codex/rules/*.md

Project layer (if exists):
  <cwd>/AGENTS.md
  <cwd>/.Codex/AGENTS.md
  <cwd>/.Codex/rules/*.md

For EACH file, extract:
  - file_path
  - layer (user | project)
  - line_count
  - purpose (1-sentence summary of what this file tries to enforce)
  - rules (list of individual rules/instructions, one per line)
  - framing (count of negative rules using "never/don't/do not/no" vs positive rules)
  - has_rationale (does each rule explain WHY?)
  - has_code_examples (are commands in code fences?)
  - duplicates (rules that appear in multiple files -- list which files AND which layers)
```

Output as structured markdown to the conversation.

### Agent 2: Hook Inventory

Read settings.json hooks config and each referenced hook script:

```
User hooks:
  ~/.Codex/settings.json
  ~/.Codex/hooks/**/*.py

Project hooks (if <cwd>/.Codex/settings.json exists):
  <cwd>/.Codex/settings.json
  <cwd>/.Codex/hooks/**/*.py

For EACH hook entry in settings.json (both layers):
  - layer (user | project)
  - event (PreToolUse, PostToolUse, SessionStart, etc.)
  - matcher
  - hook_script_path (extract from the command string after the last quote)
  - Read the actual script file
  - purpose (what rule does this hook enforce?)
  - enforcement_type: "blocking" (exit 2 stderr, or PreToolUse exit 0 + JSON deny) | "advisory" (stdout message) | "validation" (post-check)
  - method: "exit_code_2_stderr" | "pretooluse_json_stdout" (hookSpecificOutput.permissionDecision; see https://code.claude.com/docs/en/hooks) | "stdout" | "other"
  - which_rule_file (which .Codex/rules/*.md or AGENTS.md rule does this correspond to?)
  - orphaned (hook exists on disk but NOT in settings.json?)
```

Also check for hook scripts on disk that are NOT referenced in settings.json (orphaned hooks).

### Agent 3: Docs Inventory

Read referenced documentation files:

```
User docs:
  ~/.Codex/docs/*.md (glob to discover all)

Project docs (if exists):
  <cwd>/.Codex/docs/*.md

For EACH file:
  - file_path
  - layer (user | project)
  - line_count
  - purpose
  - loaded_when (is this always loaded, or on-demand via reference?)
  - overlaps_with (which rules/*.md files cover the same topics?)
  - hook_enforced (which rules in this doc are enforced by hooks vs purely advisory?)
```

## Phase 2: Cross-Reference Analysis

After all 3 agents return, analyze the combined inventory:

### 2A: Duplication Map

Build a matrix of where each concept appears:

```
| Rule/Concept | AGENTS.md | rules/*.md | docs/*.md | hooks | Count |
|---|---|---|---|---|---|
| BDD first | line 52, 92 | bdd.md | - | tdd-enforcer.py | 3 advisory + 1 hook |
| No magic values | - | code-standards.md | CODE_RULES.md:49 | code_rules_enforcer.py | 2 advisory + 1 hook |
| ... | ... | ... | ... | ... | ... |
```

Flag any concept appearing 3+ times across advisory files (duplication tax on instruction budget).

### 2B: Enforcement Gap Analysis

For each rule/concept, classify its enforcement level:

```
| Level | Description | Example |
|---|---|---|
| ENFORCED | Hook blocks the action deterministically | destructive-command-blocker.py |
| VALIDATED | PostToolUse checks after the fact | mypy_validator.py, auto-formatter.py |
| ADVISORY | In AGENTS.md/rules but no hook backs it | most rules |
| REDUNDANT | Codex already does this by default | "write clean code" |
| ORPHANED | Hook exists but no corresponding rule | hook with no rule backing |
```

### 2C: Formatting Compliance Score

Score each rule file against research-backed criteria:

```
| Criterion | Weight | Description |
|---|---|---|
| Positive framing | 25% | % of rules using positive "do X" vs negative "don't X" |
| Rationale included | 20% | % of rules with WHY explanation |
| Actionable | 20% | % of rules an agent could execute without interpretation |
| Concise | 15% | Line count relative to unique rule count (lower = better) |
| Code fences | 10% | Commands in code fences vs prose |
| No duplication | 10% | % of rules NOT duplicated elsewhere |
```

Score: 0-100 per file. Weight by instruction count contribution.

### 2D: Cross-Layer Duplication (dual-layer only)

If both user and project layers exist, compare them:

```
| Rule/Concept | User Layer File | Project Layer File | Verdict |
|---|---|---|---|
| BDD first | code-standards.md | AGENTS.md line 5 | DUPLICATE — remove from project |
| No magic values | code-standards.md | rules/code-quality.md | DUPLICATE — remove from project |
| Use pytest fixtures | (not present) | rules/testing.md | PROJECT-ONLY — keep |
| Django migrations | docs/DJANGO_PATTERNS.md | AGENTS.md line 22 | DUPLICATE — remove from project |
```

Verdicts:
- **DUPLICATE**: Rule exists in both layers. Project copy wastes budget. Remove from project unless it narrows/overrides the user rule.
- **OVERRIDE**: Project rule intentionally changes a user rule (e.g., user says "use pytest", project says "use unittest"). Keep and document.
- **PROJECT-ONLY**: Rule exists only in project layer. Keep — it's project-specific.
- **USER-ONLY**: Rule exists only in user layer. Expected for cross-cutting rules.

### 2E: Combined Budget Analysis

Calculate the total instruction count across all loaded files from BOTH layers:

```
User layer:
  ~/.Codex/AGENTS.md:         ~X instructions
  ~/.Codex/rules/*.md total:  ~Y instructions
  ~/.Codex/docs (if loaded):  ~Z instructions

Project layer (if exists):
  <cwd>/AGENTS.md:             ~A instructions
  <cwd>/.Codex/AGENTS.md:     ~B instructions
  <cwd>/.Codex/rules/*.md:    ~C instructions

COMBINED TOTAL:                ~N instructions
Cross-layer duplicates:        ~D instructions (wasted)
Effective total:               ~(N - D) instructions

Research ceiling:  150 instructions (compliance degrades beyond this) [Source 1]
Budget remaining:  150 - (N - D) = deficit/surplus
```

## Phase 3: Corrective Action Plan

Generate a priority-ordered action plan:

### Priority 1: Cut (Remove or Merge)

Items that waste instruction budget:
- Rules Codex already follows by default (REDUNDANT)
- Rules duplicated 3+ times across files (consolidate to ONE location)
- Rules in AGENTS.md that belong in scoped rules/*.md files
- Docs content that duplicates rules content

### Priority 2: Rewrite (Improve Formatting)

Items scored below 60/100 in formatting compliance:
- Flip negative rules to positive framing
- Add rationale where missing
- Put commands in code fences
- Make vague rules actionable

### Priority 3: Promote (Advisory -> Enforced)

Rules that SHOULD have hook enforcement but don't:
- High-violation rules that Codex repeatedly ignores
- Rules with deterministic criteria (can be pattern-matched)
- Safety-critical rules where violation has real cost

For each, specify:
- Which hook event (PreToolUse, PostToolUse, Stop)
- Blocking vs advisory
- Pattern to match
- Estimated implementation effort

### Priority 4: Demote (Enforced -> Removed)

Hooks that add latency without value:
- Hooks that never fire (check if the pattern is too narrow)
- Advisory hooks that could be rules instead
- Hooks using deprecated methods (exit code 2 instead of permissionDecision)

### Priority 5: Deduplicate Across Layers (dual-layer only)

For each DUPLICATE from 2D:
- If project rule is identical to user rule: delete from project
- If project rule narrows user rule: keep in project, add comment referencing user rule
- If project rule conflicts with user rule: flag for user decision (OVERRIDE vs mistake)

### Priority 6: Restructure

Optimal placement recommendations:
- What stays in AGENTS.md (critical, cross-cutting, <50 lines target)
- What moves to rules/*.md (domain-specific, scopable)
- What moves to skills (on-demand workflows, not always relevant)
- What becomes a hook (deterministic enforcement)

## Phase 4: Output

Write the audit report to the Obsidian vault:

**Path:** `sessions/[Project] Rule Audit [date].md`

**Format:**

```markdown
---
tags: [audit, rules, enforcement, Codex]
date: YYYY-MM-DD
type: rule-audit
---

## Rule Audit Report -- [Date]

### Inventory Summary
[File counts, total instruction count, budget analysis]

### Duplication Map
[Table from 2A]

### Enforcement Gaps
[Table from 2B -- sorted by risk level]

### Formatting Scores
[Table from 2C -- sorted by score ascending]

### Corrective Actions
[Numbered list from Phase 3, grouped by priority]

### Implementation Checklist
[ ] Priority 1 items (with specific file edits)
[ ] Priority 2 items (with before/after examples)
[ ] Priority 3 items (with hook specifications)
[ ] Priority 4 items (with removal justification)
[ ] Priority 5 items (with move-from/move-to)
```

Present the report to the user and ask which priorities to tackle first.
