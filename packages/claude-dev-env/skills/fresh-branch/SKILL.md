---
name: fresh-branch
description: Creates a fresh branch for the current repo based on origin main. Always fetches actual origin main rather than relying on local main. Suggests possible branch names via AskUserQuestion when context is available, or prompts the user to provide a name directly. Triggers on "fresh branch", "new branch from main", "/fresh-branch", "start fresh".
---

# fresh-branch

## Overview

Creates a new branch from `origin/main` (always fresh-fetched, never stale local main). Designed as a shared primitive: other skills (e.g. gotcha) invoke `/fresh-branch` to create a clean branch for their own PR workflows.

**Announce at start:** "Creating a fresh branch from origin/main."

## Instructions

### Phase 1 — Fetch origin main

Always fetch `origin/main` directly. Do not rely on the local `main` branch, which may be stale.

```
git fetch origin main
```

Confirm the fetch succeeded. If it fails (no network, no remote), report the error and stop.

### Phase 2 — Determine branch name

Branch names follow the repo's convention: lowercase, hyphen-separated, descriptive prefix.

**When context is available (the caller or prior conversation provides a topic):**

Suggest 2–4 branch names via `AskUserQuestion`. The suggestions should be short, descriptive, and follow the `prefix/description` or `description` convention visible in recent `git log` output.

Poll recent branch naming patterns to inform suggestions:

```
git branch -r --sort=-committerdate | head -20
```

**When no context is available:**

Ask the user to provide a branch name directly via `AskUserQuestion` with `multiSelect: false` and a free-text option.

### Phase 3 — Create the branch

```
git checkout -b <branch-name> origin/main
```

The `-b` flag creates the branch and checks it out. Basing on `origin/main` (not local `main`) guarantees the branch starts from the true latest state.

Confirm success:

```
git rev-parse --abbrev-ref HEAD
git log --oneline -1
```

### Phase 4 — Report

State the new branch name and its base commit. If invoked as a subroutine by another skill, return the branch name so the caller can proceed (e.g., creating a PR from it).

## What this skill does NOT do

- Does not push the branch. The caller decides when and whether to push.
- Does not create a PR. Use `gh pr create` separately.
- Does not switch an existing branch. It always creates a new one.

## Gotchas

See the gotcha reference at the bottom of this file. When a new gotcha is discovered during use, invoke `/gotcha` to add it here.
