# Claude Development Assistant

## Code Rules
@~/.claude/docs/CODE_RULES.md

## Core Philosophy

**TDD IS NON-NEGOTIABLE.** Build it right, build it simple. Maintainable > Clever.

## Expectations for Claude

1. **ALWAYS FOLLOW TDD** - No production code without failing test
2. **MANDATORY SELF-CHECK before proposing** - See protocol below
3. Assess refactoring after every green

**BEFORE proposing plans/implementation:**

☐ "Is this KISS?" (simplest? unnecessary complexity?)
☐ "Over-engineering?" (multiple files? premature abstractions?)
☐ Test infrastructure? (ONE file, functions, YAGNI)
☐ Tests add value? (no existence checks, no constant tests)
☐ Files (proper modules, correct dirs, no empty __init__.py)
☐ Quality (DRY, types complete, no Any/any)

## Additional Non-overlapping Rules

- **task_scope:** Match every action to what was explicitly requested. When intent is ambiguous, research official docs and present options via AskUserQuestion before making any changes. Proceed with edits only on explicit instruction.

## Tool Policies
- **context7:** Before writing code using any library/framework/SDK/API, call `resolve-library-id` then `query-docs` via Context7 MCP. Use the fetched docs to write code. Applies to all libs including React, Next.js, Django, Express, Prisma.

## Compaction
When compacting, always preserve:
- Active task and current goal
- Full list of modified files
- Any failing test names or error messages
- Current git branch and PR state
