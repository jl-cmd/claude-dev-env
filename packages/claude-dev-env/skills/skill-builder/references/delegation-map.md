# Delegation Map

How skill-builder delegates work to subagents and `/skill-writer`.

## Delegating to skill-writer (Step 4)

skill-builder orchestrates; skill-writer authors the SKILL.md and companion files. The handoff must be structured so skill-writer has everything it needs.

### New skill handoff

```
Create a skill with these parameters:

**Skill type:** [one of 9 types from skill-types.md]
**Folder structure:** [directories to create: reference/, scripts/, etc.]
**What it does:** [one-sentence capability description]
**Domain context:** [what Claude needs to know that it doesn't already]
**Initial gotchas:** [failure patterns to document from the start]
**Degree of freedom:** [high | medium | low — with reasoning]
**Constraints:** [non-negotiables]

Produce:
1. SKILL.md with hub layout (principle, gotchas, when-applies, process, file index, folder map)
2. Companion files as needed (reference docs, workflow steps, templates)
3. Every file under 500 lines; TOC on files over 100 lines
4. File index listing every file and its purpose
```

### Refine skill handoff

```
Refine this existing skill:

**Current SKILL.md:** [reference or paste]
**What was observed:** [specific failures from Claude B usage]
**What to change:** [specific instructions to add/remove/modify]
**New gotchas to add:** [failure patterns discovered]
**What to preserve:** [working content — do not touch]

Constraint: Only change what the observations demand. Do not reorganize working content.
```

## Spawning a test subagent

To observe how Claude B uses a skill on a real task:

```
Agent(
  subagent_type="general-purpose",
  description="Test skill on real task",
  prompt="Read the skill at [skill-path]/SKILL.md and follow its instructions.

Task: [realistic user prompt]

Save a complete transcript of your work to: [workspace]/transcript.md"
)
```

Spawn with `run_in_background=true` for longer tasks. Read the transcript when the agent completes.

## Reading a transcript for observations

> "Watch for unexpected exploration paths, missed connections, overreliance on certain sections, and ignored content."

Scan the transcript for:

1. **File access order** — Did Claude read files in the expected order? Unexpected ordering means the structure is not intuitive.
2. **Missed files** — Were any reference files never accessed? They might be unnecessary or poorly signaled.
3. **Re-read files** — Did Claude re-read the same file multiple times? That content should be in SKILL.md.
4. **Gotcha moments** — Where did Claude make a wrong choice? That's a gotcha candidate.
5. **Script usage** — Did Claude execute scripts as expected, or did it try to read them instead?
6. **Tool call errors** — Any "tool not found" or path errors? Fix references.

## Delegating self-audit

After building, spawn a subagent to run the checklist independently:

```
Agent(
  subagent_type="general-purpose",
  description="Self-audit skill against checklist",
  prompt="Read the skill at [skill-path]/SKILL.md and all companion files.

Then read the self-audit checklist at [skill-builder-path]/references/self-audit-checklist.md.

Check every item. For each: PASS, FAIL with specific file:line evidence and what to fix, or N/A with reason.

Report as:
## Audit Results
[ ] Item 1: PASS
[ ] Item 2: FAIL — [file:line] — [what's wrong and how to fix]
..."
)
```

This gives an independent verification. Fix failures, then re-deliver to user.

## Testing across models

> "Test your Skill with all the models you plan to use it with."

If the skill will be used with Haiku, spawn a haiku test subagent:

```
Agent(
  subagent_type="general-purpose",
  model="haiku",
  ...
)
```

Haiku needs more explicit guidance than Opus. Observe whether the skill provides enough.
