---
name: readability-review
description: 8-dimension readability rubric scoring code so a 6-year-old could understand it through structure alone. Scores functions, then FIXES anything below threshold. Use after writing code and before committing. Triggers on "readability review", "clean code", "score readability".
---

# Readability Review

## Overview

Score every function across 8 readability dimensions (160 points total), then automatically fix anything scoring below threshold by rewriting and applying via Edit tool.

**Core principle:** A 6-year-old could understand what every line does -- through code structure alone, not comments.

**Announce at start:** "I'm using the readability-review skill to score and fix code readability across 8 dimensions."

**Context:** Use after code is written but before committing. Complements code-quality-reviewer (architectural patterns) and review-code (standards compliance). This skill focuses purely on structural readability.

## Comment Preservation (ABSOLUTE RULE)

**NEVER remove ANY existing comments. ALL existing comments are SACRED.**

This is an unconditional rule. Do not evaluate, judge, or clean up existing comments. If you are not modifying the code on that line, do not touch its comments.

- Do not add NEW inline comments -- write self-documenting code instead
- Docstrings for new files/methods/classes are allowed
- If code is untouched, its comments are untouched
- Scope: Only evaluate comments on lines YOU are actively changing

## The 8 Dimensions (20 points each, 160 total)

### 1. Naming Quality (20 pts)
Every name reads as natural English. No mental translation required. No single-letter variables.
Red flags: result, data, output, response, value, item, temp as variable names.

### 2. Function SRP (20 pts)
Every function does exactly one thing. Its name IS its documentation.

### 3. Abstraction Consistency (20 pts)
Each function operates at ONE conceptual level.

### 4. Control Flow Clarity (20 pts)
Zero nesting. Guard clauses first. Flat happy path.

### 5. Domain Language Fidelity (20 pts)
Code uses business vocabulary, not computer vocabulary.

### 6. Call Site Readability (20 pts)
Function calls read as English sentences at the call site.

### 7. State and Assignment Clarity (20 pts)
Variables never change meaning.

### 8. Visual Rhythm and Code Shape (20 pts)
Code has paragraph breaks. Related lines group together.

## The Process

### Step 1: Discover Changed Files

Identify all files modified in the current session using `git diff --name-only`. Focus on production code files, not test files or config.

### Step 2: Read Every Changed File

Read the ENTIRE file, not just the diff. Readability depends on context -- a function name that seems clear in isolation may be confusing alongside its neighbors.

### Step 3: Score Each Function

Apply all 8 dimensions to every function in the changed files. Be specific with scores -- a function scoring 14/20 on Naming Quality needs concrete feedback on which names fail.

### Step 4: Rewrite and APPLY to Source Files

For every function scoring below 16/20 in ANY dimension, write the 160/160 version and USE THE EDIT TOOL to replace the original function in-place. Verify the file on disk contains the rewritten version. NEVER remove existing comments during rewrites.

### Step 5: Report What Was Fixed

Show the before/after scores for each function that was rewritten. Include which dimensions improved and by how much.

## Output Format

```
## Readability Review: [File Name]

### [function_name] - Score: [X]/160
| Dimension | Score | Notes |
|-----------|-------|-------|
| Naming Quality | /20 | ... |
| Function SRP | /20 | ... |
| ... | ... | ... |

**Action:** [Fixed / Acceptable]
```

## After Completion

If any functions were rewritten, run the test suite to verify no behavior changed. Report the final score for all reviewed functions.

**If score is below 120/160 overall:**
- Perform deeper architectural analysis inline: check DRY violations, unnecessary abstractions, and mixed abstraction levels

## Red Flags - STOP

- Function names that require reading the body to understand
- Variables reused for different purposes (meaning changes mid-function)
- Mixed abstraction levels (SQL query next to business logic)
- Deeply nested conditionals (more than 1 level)
- Computer vocabulary where domain vocabulary exists (e.g., "handler" instead of "validator")
- No visual grouping -- wall of code with no paragraph breaks

## Rationalization Prevention

| Excuse | Reality |
|--------|---------|
| "The naming is close enough" | Close enough means the next reader pauses. Pausing means it's not readable. |
| "Refactoring this function would be too risky" | The Edit tool preserves behavior. If tests pass, the rewrite is safe. |
| "It's only one dimension below threshold" | One weak dimension drags down comprehension of the entire function. |
| "This is how the rest of the codebase looks" | Existing low scores are not a license to add more. Fix what you touch. |
| "Adding guard clauses would make it longer" | Flat code reads faster than nested code, even if it has more lines. |

## Remember

- Score ALL 8 dimensions for EVERY function -- no shortcuts
- Threshold is 16/20 in ANY single dimension, not average
- Fix without asking permission -- just fix and report
- Preserve all existing functionality and test assertions
- NEVER add comments -- code must be self-documenting
- NEVER remove existing comments -- they are sacred
- Read entire files, not just diffs -- context matters
