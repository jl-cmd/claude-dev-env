---
description: Scan and update all documentation (.md files, skills, agents) for the current project
---

You are being invoked as the **docupdate** command to comprehensively audit and update documentation for the current project.

## Core Philosophy

**Documentation must match implementation.** After completing work, documentation often becomes stale. This command:
1. Uses an **Explore agent** to FIND all documentation that might need updates
2. You (the orchestrator) analyze the findings and decide what actually needs updating
3. Creates/updates project-specific skills when appropriate
4. NEVER modifies global skills/agents unless the change is truly universal

## MANDATORY: Two-Phase Architecture

### Phase 1: Discovery (Explore Agent)

**IMMEDIATELY** launch an Explore agent with this prompt:

```
Task tool with subagent_type="Explore":

"Documentation Discovery for /docupdate command

Find ALL documentation files in this project. For EACH file found, report:
1. **Location**: Full file path
2. **Filename**: Just the filename
3. **Category**: One of [README, Skill, Agent, Command, API Doc, Guide, Changelog, Session State, Config Doc, Other]
4. **Summary**: 1-2 sentence description of what the doc covers

## Search Locations

**Project .claude/ directory:**
- .claude/skills/**/*.md
- .claude/agents/**/*.md
- .claude/commands/**/*.md
- .claude/SESSION_STATE.md
- .claude/*.md

**Project root and subdirectories:**
- README.md, CHANGELOG.md, CLAUDE.md
- docs/**/*.md
- **/*.md (any other markdown)

**Scripts/modules with their own docs:**
- scripts/**/README.md
- scripts/**/docs/*.md

## Also Identify

1. **Recent code changes** - What files were modified recently (git log/diff if available, or file timestamps)
2. **Key source files** - Main implementation files that docs should reference
3. **Potential gaps** - Areas with code but no documentation

## Output Format

Return a structured report:

### Documentation Inventory

| # | Location | Filename | Category | Summary |
|---|----------|----------|----------|---------|
| 1 | path/to/file.md | file.md | Category | Brief summary |
| 2 | ... | ... | ... | ... |

### Recent Changes (if git available)
- List of recently modified files that might affect docs

### Key Source Files
- Main implementation files the docs should reference

### Potential Documentation Gaps
- Code without corresponding documentation

Be thorough - check ALL subdirectories. Do not skip any .md files."
```

### Phase 2: Orchestration (You)

After the Explore agent returns its inventory, YOU:

1. **Triage** the inventory by priority (see below)
2. **Read each doc** that might be affected by recent changes
3. **Compare against source** - Does the doc match current implementation?
4. **Decide what to update** using the decision tree
5. **Make updates** to stale documentation
6. **Generate summary report**

## Decision Tree: Global vs Project-Specific

**CREATE PROJECT-SPECIFIC skill/doc when:**
- The work was specific to THIS project (e.g., scheduled-report for automation)
- The patterns only apply to this codebase
- The configuration/credentials are project-specific
- The workflow integrates with project-specific systems

**UPDATE GLOBAL skill/doc when:**
- The change is a universal best practice
- The pattern applies to ALL projects (e.g., git workflow, code standards)
- The fix corrects an error in the global documentation

**When in doubt, create project-specific.** It's easier to promote to global later than to untangle project-specific details from global docs.

## Phase 2 Detailed Workflow

### Step 1: Triage the Inventory

From the Explore agent's report, categorize docs:

| Priority | Category | Action |
|----------|----------|--------|
| HIGH | Skills, Agents, READMEs in changed areas | Read and compare to source |
| MEDIUM | General docs in project | Skim for staleness |
| LOW | Unchanged areas, global docs | Note but don't modify |

### Step 2: Read and Compare

For HIGH priority docs:
1. Read the documentation file
2. Read the source code it documents
3. Identify discrepancies:
   - Outdated function names
   - Missing new features
   - Incorrect paths or configurations
   - Stale examples

### Step 3: Update Stale Documentation

**Priority order:**
1. `.claude/skills/` - Project skills (most impactful)
2. `.claude/CLAUDE.md` - Project instructions
3. `scripts/*/README.md` - Module READMEs
4. `README.md` - Project overview
5. `.claude/agents/` - Project agents
6. `docs/*.md` - Other guides

**MANDATORY: Skills must match code.** For each project skill:
1. Identify the source files the skill documents
2. Read both skill AND source files
3. Update skill if source has changed (paths, functions, data sources, workflows)

### Step 4: Archive Obsolete Documentation

Identify and archive documentation that is:
- **Completed plans** - Implementation plans that have been fully executed
- **Superseded docs** - Old versions replaced by newer documentation
- **Stale analysis** - Analysis docs for decisions already made

**Archive strategy:**
```
docs/plans/2025-01-*.md  -> docs/archive/2025-01-completed-plans/
docs/plans/2025-11-*.md  -> docs/archive/2025-11-completed-plans/
```

**Archiving rules:**
1. Keep active/current plan (most recent, still in progress)
2. Move completed plans to `docs/archive/YYYY-MM-completed-plans/`
3. Move stray docs to appropriate folders (e.g., `docs/guides/`)
4. Create archive README if folder has 3+ files

**Do NOT archive:**
- Active SESSION_STATE.md
- Current README.md
- Skills/Agents (they evolve, not archive)
- Recent plans still being implemented

### Step 5: Create New Skills When Needed

If recent work introduced a significant workflow without documentation:

**Create skill in:** `.claude/skills/<skill-name>/SKILL.md`

```yaml
---
name: skill-name
description: What this does and when to use it. Use when [trigger phrases].
---

# Skill Name

Brief overview.

## When to Use This Skill
- Trigger condition 1
- Trigger condition 2

## Quick Start
Minimal example to get started.

## Instructions
1. Step one
2. Step two

## Configuration
Key settings and where they live.

## Troubleshooting
Common issues and fixes.
```

## Output Requirements

After completing both phases, provide:

### 1. Discovery Summary (from Explore agent)
```markdown
## Discovery Summary

**Files Found:** X documentation files
**Categories:** X Skills, X Agents, X READMEs, X Other

### Documentation Inventory
[Include the table from Explore agent]

### Recent Changes Detected
[List from Explore agent]
```

### 2. Analysis Results (your decisions)
```markdown
## Analysis Results

### Needs Update (HIGH priority)
| File | Reason |
|------|--------|
| path/file.md | [specific reason] |

### Current (No changes needed)
- file.md - Still accurate
- file2.md - Matches implementation

### Out of Scope (Global/Unrelated)
- ~/.claude/skills/X - Not affected by project work
```

### 3. Changes Made
```markdown
## Documentation Update Summary

### Updated
- `path/to/file.md` - [what changed]

### Created
- `path/to/new.md` - [why created]

### Archived
- `docs/plans/2025-01-*.md` -> `docs/archive/2025-01-completed-plans/` - [completed implementation]

### Skipped
- `path/file.md` - [why skipped]

### Global Resources (NOT Modified)
- `~/.claude/skills/X` - [why not touched]
```

### 4. Recommendations
```markdown
## Recommendations

### Manual Review Needed
- [docs that need human attention]

### Future Documentation
- [suggested new docs to create]

### Next /docupdate
- Run after [specific trigger]
```

## Skill-Source Mapping

For each skill, identify its source files. Common patterns:

| Skill Pattern | Source Files to Check |
|--------------|----------------------|
| periodic-reports | generator.py, batch_run*.py |
| *-automation | automation/*.py, scripts/*.py |
| *-workflow | Main orchestration scripts |

**When source changes, skill MUST be updated:**
- Data sources (CSV -> SQLite, API changes)
- File paths and locations
- Function signatures and workflows
- Configuration and credentials
- New features or removed functionality

## Important Guidelines

1. **Always launch Explore agent first** - Don't skip discovery phase
2. **Project-first mindset:** Default to project-specific documentation
3. **Don't over-update:** Only change what's actually stale
4. **Be specific:** Include actual file names, discrepancies found
5. **Preserve history:** Add to docs, don't delete useful content
6. **Test triggers:** Ensure skill descriptions will activate correctly

## Error Handling

- If no .claude directory exists, create it
- If no git repo, work with file modification dates
- If Explore agent finds no docs, report "No documentation found - consider creating README.md"
- If unsure about a change, flag for manual review instead of guessing

## Example Execution

```
User: /docupdate

Claude:
1. Launches Explore agent for documentation discovery
2. Receives inventory: 15 docs found, 3 skills, 1 agent, 2 READMEs
3. Identifies Code.gs was heavily modified recently
4. Triages: SKILL.md and README.md are HIGH priority
5. Reads SKILL.md, finds it references old function names
6. Updates SKILL.md with:
   - New architecture section
   - Updated function references
   - New troubleshooting items
7. Reads README.md, finds it's current
8. Generates summary report
9. Notes global skills weren't affected
```
