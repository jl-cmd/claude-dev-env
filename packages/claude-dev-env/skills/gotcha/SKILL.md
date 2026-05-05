---
name: gotcha
description: When a skill encounters an obstacle requiring user intervention, this skill invokes bg-agent to add the gotcha to the skill file's gotcha section and creates a PR via fresh-branch. Triggers on "/gotcha", "add a gotcha", "document this gotcha", "record this obstacle".
---

# gotcha

## Overview

When a skill is executed and hits an obstacle that requires user intervention to resolve, `/gotcha` captures that knowledge so future invocations avoid the same trap. It delegates the mechanical work to `bg-agent`, which writes the gotcha entry and opens a PR using `fresh-branch`.

**Announce at start:** "Recording this gotcha and opening a PR."

## Instructions

### Step 1 — Collect the gotcha

The caller provides the obstacle context. Distill it into:

- **Which skill file** hit the obstacle (full path, e.g. `packages/claude-dev-env/skills/rebase/SKILL.md`).
- **What happened** — the specific failure or blocker, in one or two sentences.
- **What the user had to do** to resolve it.
- **What to do differently next time** (the actionable gotcha).

Determine which repo the skill lives in. Usually this is `claude-code-config`, but if the skill is in another repo (e.g. a project-specific `.claude/skills/` directory), use that repo instead.

### Step 2 — Delegate to bg-agent

Invoke `/bg-agent` with a task like:

```
bg-agent add a gotcha to <skill-file-path> in repo <repo-name>. The gotcha is: "<one-line summary>". Details: "<what happened, what the user did, and what to do next time>."

Steps:
1. Use /fresh-branch to create a branch named gotcha/<short-slug>.
2. In <skill-file-path>, add the gotcha entry under a ## Gotchas section (create the section at the bottom of the file if it does not exist).
3. Format each gotcha as a bullet: "- **<title>:** <description>."
4. Commit with message "fix(<skill-name>): add gotcha — <title>".
5. Push and create a draft PR.
6. Report the PR URL.
```

The bg-agent will pick a suitable agent type and run the full workflow in the background.

### Step 3 — Confirm

Tell the user: "Recording gotcha in the background. You will be notified when the PR is ready."

## Gotcha entry format

Every gotcha entry follows this format:

```markdown
## Gotchas

- **<title>:** <what happens>. <what to do instead>.
```

If a `## Gotchas` section already exists, append to it. If not, create it at the bottom of the skill file.

## Which repo

| Skill location | Repo |
|---|---|
| `packages/claude-dev-env/skills/<name>/` | `jl-cmd/claude-code-config` |
| `~/.claude/skills/<name>/` | `jl-cmd/claude-code-config` (user skills) |
| Project `.claude/skills/<name>/` | That project's repo |

When unsure, ask the user which repo. Otherwise, default to `claude-code-config`.

## Gotchas

- **The bg-agent prompt must be self-contained.** The background agent has no access to this conversation. Include the skill file path, the gotcha text, the repo, and the exact workflow steps in the prompt.
