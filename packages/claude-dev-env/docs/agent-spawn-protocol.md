# Agent Spawn Protocol

Full protocol behind the always-on `rules/agent-spawn-protocol.md` kernel. It applies before any Agent or Task tool invocation — Explore, implementation, research, or team subagents.

## Step 1: Context sufficiency check

Before writing any agent prompt, confirm you can answer all of these:

- What specific files, directories, or areas of the codebase are involved?
- What constraints apply — patterns to follow, things to leave untouched, boundaries?
- What does success look like — expected output, acceptance criteria?
- Is the task unambiguous enough to delegate?

When any answer is "I don't know", investigate first (read files, search code) or ask the user. Do not spawn with incomplete context.

## Step 2: Craft the prompt with /prompt-generator

Run the `/prompt-generator` skill to produce a structured prompt. Feed it:

- The task description and goal
- Target files and directories found in Step 1
- Constraints and boundaries
- Expected output format
- Acceptance criteria

The skill asks one to three clarifying questions when information is missing — this is the built-in context verification. Use the skill's output as the agent's `prompt` parameter.

## Step 3: Spawn the agent

Pass the structured prompt from Step 2 to the Agent or Task tool.

## Why

An agent that receives a vague prompt wastes tokens exploring in circles, produces code that misses constraints, and needs a second pass. A small investment in prompt quality through `/prompt-generator` saves a long agent failure. This holds for Explore agents, which waste context on unfocused searches, and for execution agents, which write wrong code.

## Relationship to other rules

- `conservative-action.md` gates acting when intent is ambiguous. This protocol extends that: an ambiguous task goes to investigation or a user question first, never straight to a subagent.
- Project-specific rules or `~/.claude/CLAUDE.md` may decide whether to use subagents at all; this protocol governs how to craft the prompt once you delegate.
