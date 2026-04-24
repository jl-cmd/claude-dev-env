# Claude Development Assistant

## Code Rules
@~/.claude/docs/CODE_RULES.md

## File-Global Constants

**file_global_constants_use_count:** Every module-level constant in production code outside `config/` must be referenced by at least two methods, functions, or classes in the same file. One reference → move to `config/` and import as a local alias. Zero references → delete (dead code). Test files are exempt.

Full rule including the decision table, examples, and exemption details: [`packages/claude-dev-env/rules/file-global-constants.md`](rules/file-global-constants.md).

## SOLID Principles

**SRP (Single Responsibility)** always applies: one reason to change per function, class, or module — regardless of paradigm.

**OCP, LSP, ISP, DIP** apply where two or more concrete implementations already share a contract. With a single concretion, Right-Sized Engineering takes precedence: use concrete classes, functions when no state, and direct imports. Refactor toward OCP/DIP at the commit that introduces the second concrete implementation.

Full rule including the reconciliation with Right-Sized Engineering, misapplication signals, and when-it-adds-value criteria: [`packages/claude-dev-env/docs/CODE_RULES.md`](docs/CODE_RULES.md) §7.5.

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
