---
name: auditing-claude-config
description: >-
  Audits a Claude Code setup (user CLAUDE.md, ~/.claude/rules/, project .claude/) for
  context-budget waste — duplicate @-imports, always-on rules to path-scope or convert
  to skills, oversized files — and produces a migration table with savings. Use when
  reviewing the startup/instruction load, when /memory shows surprising loads, when
  adding new rules, or for periodic config hygiene.
---

# Auditing Claude Config

This skill audits what gets eagerly loaded into every Claude Code session and identifies wins — duplicate imports, lazy-load candidates, skill-conversion candidates, and pointer-shrink opportunities. It is grounded in three Anthropic docs cited at the bottom.

## When to invoke

- `/memory` shows files the user did not expect to be loaded
- The user is adding new rules and wants to know if the preload is growing past the recommended ceiling (CLAUDE.md target: under 200 lines)
- Sessions feel sluggish or adherence to rules has degraded (the docs warn that bloated CLAUDE.md files cause Claude to ignore actual instructions)
- A new template or shared `.claude/` directory has just been adopted
- Periodic hygiene — quarterly is a reasonable cadence

## Background facts the audit relies on

These come from the official Claude Code documentation; do not re-derive them.

| Fact | Source phrasing |
|---|---|
| `@path` imports in CLAUDE.md and rules expand into context **at launch** — they are not pointers | "Imported files are expanded and loaded into context at launch alongside the CLAUDE.md that references them" |
| Splitting into `@`-imports does **not** reduce context | "Splitting into `@path` imports helps organization but does not reduce context, since imported files load at launch" |
| Files in `.claude/rules/` without `paths:` frontmatter load **every** session | "Rules without `paths` frontmatter are loaded unconditionally and apply to all files" |
| Path-scoped rules load **lazily** when matching files are accessed | "Rules can be scoped to specific files using YAML frontmatter with the `paths` field. These conditional rules only apply when Claude is working with files matching the specified patterns" |
| Skills preload **metadata only** | "At startup, only the metadata (name and description) from all Skills is pre-loaded. Claude reads SKILL.md only when the Skill becomes relevant, and reads additional files only as needed" |
| `@`-imports inside fenced/inline code blocks do not trigger imports | Empirical (verified in this skill's source session) — referenced files alongside backtick-wrapped `@` paths do not appear in session-start context |

## Audit workflow

### Step 1 — Inventory the always-loaded set

```
Files to count:
  ~/.claude/CLAUDE.md
  ~/.claude/CLAUDE.local.md (if present)
  ./CLAUDE.md (project root)
  ./.claude/CLAUDE.md (project alt)
  ./CLAUDE.local.md
  every file in ~/.claude/rules/ without `paths:` frontmatter
  every file in ./.claude/rules/ without `paths:` frontmatter
  every file referenced via @-import from any of the above (recursively, max depth 5)
```

Count lines with `wc -l` (cygwin/Git Bash) or `Get-Content … | Measure-Object -Line` (PowerShell). Sum is the always-loaded line budget.

Flag the result against the docs:
- CLAUDE.md alone over 200 lines → strong nudge to slim
- Total preload over ~1,000 lines → likely losing instruction adherence

### Step 2 — Find duplicate `@`-imports

Search every always-loaded file (CLAUDE.md and every rule file without `paths:`) for `@`-references. Build a multimap of `imported_path → [referrer_path, ...]`. Any entry with two or more referrers is loading the import twice into context.

Fix: delete the import from one of the parents (keep it in the file with the broader scope, typically CLAUDE.md).

### Step 3 — Classify each rule

For every rule in `~/.claude/rules/` (and project `.claude/rules/`), apply this matrix:

| Rule body describes | Verdict | Action |
|---|---|---|
| Behavior that applies every turn (TDD, conservative-action, ask-via-tool, etc.) | Keep always-on | No change |
| File-type-specific patterns (Python idioms, JS/TS, Windows fs, test patterns) | Path-scope | Add `paths:` frontmatter with appropriate globs |
| A multi-step workflow or procedure | Convert to skill | Move body to `~/.claude/skills/<name>/SKILL.md`, leave a 2-3 line pointer rule |
| Content already covered by an existing skill in `~/.claude/skills/` | Shrink to pointer | Replace body with a 2-3 line reference to the skill |
| Reference doc consumed only by one rule | Inline or co-locate | Move into the consumer rule or skill, drop the standalone doc |

When suggesting `paths:` globs, derive them from the rule's body — do not guess. Examples:
- Body discusses `shutil.rmtree`, `os.unlink` → `paths: ["**/*.py"]`
- Body discusses `mkdirSync`, `fs.promises` → `paths: ["**/*.{mjs,js,ts}"]`
- Body discusses pytest fixtures, test naming → `paths: ["**/test_*.py", "**/*_test.py", "**/conftest.py"]`

### Step 4 — Produce the migration table

Output one table with these columns: `Rule | Lines today | Verdict | Specific action | Lines removed from preload`. Total the savings. Express as both an absolute line count and a percentage of step 1's baseline.

### Step 5 — Stage the changes

Group recommendations by risk:
- **Zero-risk:** duplicate-import deletion (largest single win in most setups)
- **Low-risk:** adding `paths:` frontmatter (the docs guarantee fallback to "applies to all files" if syntax is wrong; verify with `/memory`)
- **Medium-risk:** moving content into skills (changes when content reaches Claude — skill-discovery dependent)
- **Author-required:** shrinking rules to pointers (requires deciding what content survives)

## Empirical verification (optional)

When the audit's recommendations rest on assumptions about lazy-load behavior —
especially `@`-imports nested inside path-scoped rules — install the probe hook
in [`reference/probe-hook.md`](reference/probe-hook.md) to capture every
`InstructionsLoaded` event. It carries the hook script, the `settings.json`
registration, and the test protocol that confirms a path-scoped rule loads
lazily while its nested imports follow.

## Output format

Always end an audit run with:
1. **Baseline:** total always-loaded lines today, broken down by file
2. **Findings:** the migration table from step 4
3. **Recommended next step:** the single highest-leverage change (usually duplicate-import deletion)
4. **Open questions:** anything not verified empirically

## Sources

- [Claude Code — How Claude remembers your project](https://code.claude.com/docs/en/memory)
- [Claude Code — Hooks (InstructionsLoaded)](https://code.claude.com/docs/en/hooks)
- [Claude API — Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
