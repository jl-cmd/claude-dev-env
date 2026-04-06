---
name: dream
description: Consolidate, prune, and reorganize auto memory files. Simulates Auto Dream -- fixes format drift, deduplicates facts, enforces index structure. Use when memory feels stale or cluttered. Triggers on '/dream', 'consolidate memory', 'clean up memory', 'dream'.
disable-model-invocation: true
---

# Dream: Memory Consolidation

## Overview

Consolidate auto memory by enforcing the format contract, pruning stale content, deduplicating facts, and rebuilding MEMORY.md as a clean index.

**Announce at start:** "Running memory consolidation (dream)."

**Context:** Standalone maintenance utility. Run periodically or when memory feels cluttered. Simulates the Auto Dream feature that is in gradual rollout.

## The Format Contract

Source: Claude Code client system prompt + [official docs](https://code.claude.com/docs/en/memory).

**MEMORY.md is an index, not a memory.** It should contain only one-line pointers to topic files:
- Format: `- [Title](file.md) -- one-line hook`
- Target: under ~150 characters per entry
- Hard limit: 200 lines / 25KB (only this much loads at session start)
- No content, tables, or multi-line facts directly in MEMORY.md

**Topic files require frontmatter:**
```yaml
---
name: {{topic name}}
description: {{one-line description}}
type: {{user | feedback | project | reference}}
---
```

**Organization:** Semantic by topic, not chronological by session.

## The Process

### Phase 1: Audit

Read MEMORY.md and every file in the memory directory. For each file, check:

1. **Frontmatter present?** Must have name, description, type fields.
2. **Type correct?** Must be one of: user, feedback, project, reference.
3. **Named by topic?** Files named `session-YYYY-MM-DD-*` should be renamed to their actual topic.

For MEMORY.md, check:
1. **Index entries only?** Flag any line that is NOT a `- [Title](file.md)` link or a `##` section header.
2. **Content leaking into index?** Flag inline facts, tables, multi-line bullet points.
3. **Under 200 lines?** Flag if approaching the limit.

### Phase 2: Propose Changes

Present a structured report to the user with these sections:

**Format violations** -- files missing frontmatter, content in MEMORY.md
**Stale content** -- items older than 14 days with forward-looking TODOs or "Next/Pending" sections that may be completed
**Duplicates** -- facts that appear in both topic files and MEMORY.md inline, or across multiple topic files
**Rename candidates** -- session-dated files that should be topic-named
**Proposed actions** -- numbered list of specific changes (extract, merge, prune, rename, add frontmatter)

Do NOT execute any changes yet. Wait for user approval.

### Phase 3: Execute

After user approves (all or selected items):

1. **Extract** inline MEMORY.md content into new or existing topic files with proper frontmatter.
2. **Add frontmatter** to files that lack it.
3. **Rename** session-dated files to topic names.
4. **Deduplicate** by removing redundant copies (keep the most complete version).
5. **Prune** stale forward-looking content (TODOs, "Next" sections) from old files.
6. **Rebuild MEMORY.md** as a clean index -- one-line entries only, grouped by `##` section headers.

### Phase 4: Verify

After execution, read the rebuilt MEMORY.md and confirm:
- Every entry is a one-line link
- Every referenced file exists and has valid frontmatter
- No orphaned files (files in directory but not in index)
- Total line count under 200

Report the results: files changed, lines saved, violations fixed.

## Output Format

Phase 2 report structure:

```
## Dream Report

### Format Violations (X found)
- [file] -- [issue]

### Stale Content (X flagged)
- [file] -- [what's stale] -- [age]

### Duplicates (X found)
- [fact] -- appears in [file1] and [file2]

### Proposed Actions
1. [action] -- [file] -- [reason]
2. ...

Approve all, select by number, or cancel?
```

## After Completion

Report summary: files modified, created, renamed, deleted. Line count before/after.

## Best Practices

- Run after long sessions or when starting fresh on a project
- Check stale flags manually -- dream cannot verify if TODOs were completed without reading the actual codebase
- The 14-day staleness threshold is a heuristic, not a hard rule
- When in doubt about whether to prune, flag it for the user rather than proposing deletion
