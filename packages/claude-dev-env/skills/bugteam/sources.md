# Bugteam skill — sources and citations

Canonical URLs and verbatim quotes that `SKILL.md` relies on. Load this file when verifying wording against upstream documentation or when expanding citations. Domain-oriented narrative (without duplicating these quotes) lives under [`reference/README.md`](reference/README.md).

---

## Claude Code — Agent teams

**URL:** [Orchestrate teams of Claude Code sessions](https://code.claude.com/docs/en/agent-teams)

**Enable flag (operational link used in refusal copy):** [Enable agent teams](https://code.claude.com/docs/en/agent-teams#enable-agent-teams)

### Teammate context isolation (clean-room basis)

Direct quote:

> "Each teammate has its own context window. When spawned, a teammate loads the same project context as a regular session: CLAUDE.md, MCP servers, and skills. It also receives the spawn prompt from the lead. The lead's conversation history does not carry over."

**Skill use:** Independent context per teammate enforces the clean-room audit property; the same sentence is cited again where per-loop `Agent` spawns are justified.

### Subagents vs agent teams

Direct quote:

> "Use subagents when you need quick, focused workers that report back. Use agent teams when teammates need to share findings, challenge each other, and coordinate on their own."

**Skill use:** Subagents return into the lead context (accumulates across loops); agent-team teammates do not pollute the lead. This skill needs the independent-context property.

### Team creation in natural language

Direct quote:

> "tell Claude to create an agent team and describe the task and the team structure you want in natural language. Claude creates the team, spawns teammates, and coordinates work based on your prompt."

**Skill use:** Maps to the `TeamCreate` tool step in the process section.

### Referencing subagent types when spawning teammates

Direct quote:

> "When spawning a teammate, you can reference a subagent type from any subagent scope: project, user, plugin, or CLI-defined. This lets you define a role once... and reuse it both as a delegated subagent and as an agent team teammate."

**Skill use:** Bugfind / bugfix roles reference `code-quality-agent` and `clean-coder` by subagent type name.

### Lead cleanup and active teammates

Direct quote:

> "When the lead runs cleanup, it checks for active teammates and fails if any are still running, so shut them down first."

**Skill use:** Step 4 shutdown sequence before `TeamDelete`.

### Ending the team

Direct quote:

> "When you're done, ask the lead to clean up: 'Clean up the team'."

**Skill use:** Maps to calling `TeamDelete()` after shutdown messages.

---

## Claude — Agent skills best practices

**Base URL:** [Agent Skills best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)

### Table of contents for long skills

**URL:** [Structure longer reference files with table of contents](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#structure-longer-reference-files-with-table-of-contents)

**Skill use:** Justifies the top-of-file Contents section so partial reads still expose scope.

### Progressive disclosure and utility scripts

**URL:** [Progressive disclosure patterns](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#progressive-disclosure-patterns)

**Skill use:** Shell helpers live under `scripts/` and are executed, not loaded as primary context.

### Concise is key

**URL:** [Concise is key](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices#concise-is-key)

Direct quotes:

> "However, being concise in SKILL.md still matters: once Claude loads it, every token competes with conversation history and other context."

Heading and following line (section uses the heading as its own emphasis):

> Default assumption: Claude is already very smart

> "Only add context Claude doesn't already have. Challenge each piece of information:"

**Skill use:** `SKILL.md` revisions that drop redundant narration and trust the reader’s prior knowledge.
