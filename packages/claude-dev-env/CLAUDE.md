# Claude Development Assistant

## Code Rules (NON-NEGOTIABLE)
@~/.claude/docs/CODE_RULES.md

## Core Philosophy

**TDD IS NON-NEGOTIABLE.** Build it right, build it simple. Maintainable > Clever.

## Working with Claude

### Expectations

1. **ALWAYS FOLLOW TDD** - No production code without failing test
2. **MANDATORY SELF-CHECK before proposing** - See protocol below
3. Assess refactoring after every green

### Mandatory Self-Check Protocol

**BEFORE proposing plans/implementation:**

☐ Project rules review (e.g. Tasklings `tasklings-preferences` when in that repo path)
☐ "Is this KISS?" (simplest? unnecessary complexity?)
☐ "Over-engineering?" (multiple files? premature abstractions?)
☐ Test infrastructure? (ONE file, functions, YAGNI)
☐ Tests add value? (no existence checks, no constant tests)

## Pre-PR Submission Checklist

**Run `/check-pr` OR verify:**
- ☐ KISS / preferences (multiple requirements.txt? over-engineered?)
- ☐ KISS (simplest? one file? functions not classes?)
- ☐ Files (proper modules, correct dirs, no empty __init__.py)
- ☐ Quality (no dupes, types complete, no Any/any)
- ☐ Tests (no existence checks, no constant value tests)
- ☐ Self-checked before proposing?

## Compaction
When compacting, always preserve:
- Active task and current goal
- Full list of modified files
- Any failing test names or error messages
- Current git branch and PR state