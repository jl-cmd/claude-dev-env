# Agent Spawn Protocol (Mandatory)

**When this applies:** Before any Agent or Task tool invocation (Explore, implementation, research, or team subagents).

<agent_spawn_protocol>

## Before spawning ANY agent — no exceptions

Every Agent and Task tool call must follow this protocol. This includes Explore agents, research agents, execution agents, and team members.

### Step 1: Context sufficiency check

Before writing any agent prompt, verify you can answer all of these:
- [ ] What specific files, directories, or areas of the codebase are involved?
- [ ] What constraints apply? (patterns to follow, things NOT to change, boundaries)
- [ ] What does success look like? (expected output, acceptance criteria)
- [ ] Is the task unambiguous enough to delegate?

If ANY answer is "I don't know" -- investigate first (read files, search code) or ask the user. Do NOT spawn with incomplete context.

### Step 2: Craft the prompt with /prompt-generator

Run the `/prompt-generator` skill to produce a structured prompt. Feed it:
- The task description and goal
- Target files/directories discovered in Step 1
- Constraints and boundaries
- Expected output format
- Acceptance criteria

The skill will ask 1-3 clarifying questions if information is missing -- this is the built-in context verification.

Use the skill's output as the agent's `prompt` parameter.

### Step 3: Spawn the agent

Pass the structured prompt from Step 2 to the Agent/Task tool.

</agent_spawn_protocol>

## Why

Agents receiving vague prompts waste tokens exploring in circles, produce code that misses constraints, and require expensive rework. A 30-second investment in prompt quality via /prompt-generator saves 5-minute agent failures. This applies equally to Explore agents (which waste context on unfocused searches) and execution agents (which write wrong code).

## Relationship to other rules

- **conservative-action.md** gates acting when ambiguous. This extends that: do not delegate when the task is ambiguous—investigate or ask the user first.
- Project-specific rules or `~/.claude/CLAUDE.md` may define *whether* to use subagents or teams; this rule governs *how* to craft prompts when you do delegate.
