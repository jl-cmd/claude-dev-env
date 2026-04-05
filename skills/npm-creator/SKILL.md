---
name: npm-creator
description: Scaffold an npm-installable package for any Claude Code plugin repo. Detects plugin directories (rules/, hooks/, agents/, etc.), asks about package metadata, then generates package.json and a cross-platform Node.js installer (bin/install.mjs). Use when turning a plugin repo into an npx-installable package.
user_invocable: true
---

# npm-creator

## Overview

Scaffold a cross-platform npm package for Claude Code plugin repos so users can install via `npx <package-name>`.

**Core principle:** The installer copies plugin files to ~/.claude/ using only Node.js built-ins. Zero external dependencies, works on Linux, macOS, and Windows.

**Announce at start:** "I'm using the npm-creator skill to scaffold an npm package for this plugin repo."

**Context:** Use after a plugin repo has its content files (rules, hooks, agents, etc.) in place. This skill adds the packaging layer on top.

## The Process

### Step 1: Detect Plugin Structure

Scan the current repo root for these directories:

| Directory | Purpose | Install destination |
|-----------|---------|-------------------|
| `rules/` | Behavioral rules (.md) | `~/.claude/rules/` |
| `docs/` | Reference documents (.md) | `~/.claude/docs/` |
| `commands/` | Slash commands (.md) | `~/.claude/commands/` |
| `agents/` | Agent definitions (.md) | `~/.claude/agents/` |
| `skills/` | Skill packages (subdirs) | `~/.claude/skills/` |
| `hooks/` | Hook scripts (+ optional hooks.json manifest) | Merge into `~/.claude/settings.json` |

Use Glob to find which directories exist and count files in each. Report findings to the user.

If the repo has no recognized directories, say so and ask if the structure uses different names.

### Step 2: Gather Package Metadata

Ask the user (use AskUserQuestion, one call with all questions):

1. **Package name** — suggest the repo directory name. Ask if scoped (@org/) or unscoped.
2. **Description** — suggest based on detected content ("Claude Code plugin with X rules, Y agents, Z hooks").
3. **CLAUDE.md generation** — should the installer concatenate rules + docs into a CLAUDE.md? (Yes if both rules/ and docs/ exist.)
4. **Python detection** — does the plugin use Python hooks? (Yes if hooks/ contains .py files.) If yes, the installer will detect python3/python/py at install time.

### Step 3: Generate package.json

Create `package.json` at the repo root with:

- `name`: from Step 2
- `version`: "1.0.0"
- `description`: from Step 2
- `type`: "module"
- `bin`: `{ "<package-name>": "./bin/install.mjs" }`
- `files`: array of detected directories + `["bin/"]`
- `keywords`: `["claude-code", "plugin", "cli"]`
- `license`: "MIT"
- `repository`: detect from `git remote get-url origin` if available

### Step 4: Generate bin/install.mjs

Create `bin/install.mjs` with a shebang (`#!/usr/bin/env node`) and these capabilities:

**Imports:** Only `node:fs`, `node:path`, `node:os`, `node:child_process`, `node:url`.

**Path resolution:**
- `CLAUDE_HOME` = `path.join(os.homedir(), '.claude')`
- `PACKAGE_ROOT` = resolve from `import.meta.url` using `fileURLToPath` and `path.dirname`

**Install mode (default — no flags):**

For each detected directory from Step 1:
- Copy files from package to CLAUDE_HOME, preserving directory structure
- For skills/, copy recursively (each skill is a subdirectory)
- For each file, log with status icon:
  - New file: `  ✓ rules/tdd.md (new)`
  - Existing file: `  ↻ rules/tdd.md (updated)`

If CLAUDE.md generation is enabled:
- Concatenate all rules/*.md under `# Project Rules (from <package-name> plugin)`
- Concatenate all docs/*.md under `# Reference Docs`
- Each file gets an `## {filename without extension}` header
- Write to `CLAUDE_HOME/CLAUDE.md`

If Python hooks detected:
- Try `python3 --version`, then `python --version` (verify Python 3), then `py -3 --version`
- Use the first that succeeds
- If none work: print error and exit with code 1

If hooks/hooks.json exists:
- Read it and the destination `CLAUDE_HOME/settings.json` (create `{}` if missing)
- For each event type, for each matcher group:
  - Replace `python3` with detected python command (if applicable)
  - Replace `${CLAUDE_PLUGIN_ROOT}` with the absolute CLAUDE_HOME hooks path
  - Check for duplicate matcher groups (idempotent — skip if already present)
  - Append new groups
- Write settings.json with `JSON.stringify(data, null, 4)`

Important runtime note:
- `~/.claude/settings.json` is the runtime source of truth for hooks.
- `hooks/hooks.json` is a packaging/install manifest input for merge workflows, not a runtime file Claude reads directly.

Print summary:
```
Installed <package-name>:
  Rules: N files (X new, Y updated)
  Agents: N files (X new, Y updated)
  Hooks: N groups merged into settings.json
  Python: python3
```

**Uninstall mode (`--uninstall` flag):**
- Remove only files matching the package's file list (never delete user-created files)
- Log each removal: `  ✗ rules/tdd.md (removed)`
- Remove hook entries from settings.json by matching command paths
- Remove generated CLAUDE.md if it exists
- Print removal summary

**Error handling:**
- Create CLAUDE_HOME with `fs.mkdirSync(path, { recursive: true })` if missing
- If settings.json is malformed JSON, print error and exit (never clobber)
- Skip missing source directories with a warning

### Step 5: Update README.md

If a README.md exists, offer to update the install section with:

```
## Install

\`\`\`bash
npx <package-name>
\`\`\`

To uninstall:

\`\`\`bash
npx <package-name> --uninstall
\`\`\`
```

Preserve all other README content.

## Output Format

Two new files created:
1. `package.json` at repo root
2. `bin/install.mjs` at bin/ directory

One file optionally updated:
3. `README.md` install section

## After Completion

Suggest the user test locally:
- `node bin/install.mjs` (install)
- `node bin/install.mjs --uninstall` (uninstall)
- Verify files appeared in `~/.claude/`
- Verify hooks merged into `~/.claude/settings.json`

When ready to publish: `npm publish`

## Red Flags - STOP

- Repo has no recognized plugin directories (rules/, hooks/, agents/, etc.)
- hooks.json references tools or paths outside the plugin structure
- Package name conflicts with an existing npm package (suggest checking npmjs.com)
- Plugin files contain secrets or credentials that would be published

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "I'll add cross-platform support later" | Use path.join() and os.homedir() from the start. Retrofitting is painful. |
| "Shell commands are simpler for file copying" | Shell commands break on Windows. fs APIs work everywhere. |
| "One big install function is fine" | Separate install/uninstall/detect functions keep each under 50 lines. |
| "We can skip idempotency" | Users will run the installer multiple times. Duplicate hooks break sessions. |

## Remember

- Zero external dependencies — only Node.js built-ins
- If present, hooks.json in the repo stays canonical (python3 + ${CLAUDE_PLUGIN_ROOT})
- Rewriting happens only in the destination settings.json (runtime source of truth)
- path.join() everywhere — never concatenate paths with `/` or `\`
- Idempotent: running twice produces the same result
- Log every file action so the user sees what changed
