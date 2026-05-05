---
name: bg-agent
description: Delegates a task to a background agent. Invoked as "bg-agent [task to do]". Claude picks a suitable agent type from the available agents list and spawns it via Agent with run_in_background: true. Triggers on "/bg-agent", "bg-agent", "background agent for this".
---

# bg-agent

## Overview

Delegates a task to a background agent so the main session can continue without waiting. This is the programmatic invocation path for background work — other skills (e.g. gotcha) and the user can both invoke it.

**Announce at start:** "Delegating to a background agent: `<one-line summary of task>`."

## Instructions

### Step 1 — Parse the task

The user (or calling skill) provides a task description after `bg-agent`. Example:

```
bg-agent add a gotcha to the rebase skill about force-push lease format
```

Extract the full task description from the arguments.

### Step 2 — Select the right agent

Review the available agent types (listed in the system prompt's Agent tool description) and pick the most suitable one for the task:

- **Read-only tasks** (research, search, exploring code) → Explore agent or general-purpose agent.
- **Code authoring tasks** (writing/editing skill files, creating PRs) → general-purpose agent with `run_in_background: true`.
- **Specialized tasks** → pick the agent whose description best matches the task. For example, use `pr-description-writer` for PR descriptions, `git-commit-crafter` for commits.

If no specialized agent fits, use the general-purpose agent.

### Step 3 — Spawn the background agent

Use the `Agent` tool with `run_in_background: true`. Write a self-contained prompt that:

- States the exact goal and expected output.
- Lists the files or directories involved (from the caller's context).
- Includes any constraints (do not create a PR, do not push, etc.).
- Specifies what success looks like.

Example for a gotcha-adding task:

```
Agent({
  description: "Add gotcha to skill file",
  prompt: "Add a gotcha entry to packages/claude-dev-env/skills/rebase/SKILL.md. The gotcha is: 'force-push --force-with-lease requires the full <branch>:<sha> format, not just the branch name.' Add it under the ## Gotchas section. If no ## Gotchas section exists, create one at the bottom of the file.",
  subagent_type: "general-purpose",
  run_in_background: true
})
```

### Step 4 — Report spawn

Confirm the agent was spawned and state its task in one sentence. The caller does not need to wait for completion — background agents notify on completion automatically.

## Constraints

- Always use `run_in_background: true`. This skill is specifically for background delegation.
- Never run the task inline in the main session. The point is to offload it.
- If the task requires a PR, the spawned agent handles the full flow (branch → commit → push → PR).
- Return control to the caller immediately after spawning. Do not poll for completion.

## Gotchas

See the gotcha reference at the bottom of this file. When a new gotcha is discovered during use, invoke `/gotcha` to add it here.
