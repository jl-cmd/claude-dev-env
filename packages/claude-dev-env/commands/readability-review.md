---
description: "8-dimension readability review: scores and FIXES code to 160/160. Also handles paste-rewrite via arguments."
allowed-tools: Skill, Read, Edit, Grep, Glob, Bash
---

Invoke the `readability-review` skill to review and fix code readability.

## Steps

1. Invoke the `readability-review` skill via the Skill tool
2. The skill will: load its rubric → discover target code → read it → score every function → FIX anything below 16/20 → report

## User Arguments

If the user provided arguments: $ARGUMENTS

- If arguments contain **pasted code**: locate the code in the codebase (Grep for a unique line), read the full file, score it against all 8 dimensions, rewrite to 160/160, and apply via Edit tool
- If arguments contain a **file path**: review only that file
- If arguments contain **"score-only"**: skip the fix phase and just report scores
- If **no arguments**: review all changed files in the session (via `git diff --name-only`)
