---
name: build-goal
description: >-
  Authors a paste-ready goal-mode prompt plus a human-readable brief from the
  current session's context and task list, then stops without implementing the
  goal's work. Triggers: /build-goal, build goal, goal from context, goal-cmd
  from session, make a goal prompt, goal mode prompt from tasks, package this
  session into a goal.
---

# build-goal

**Principle:** One turn turns what the session already knows — the aim, the done-when facts, the task list, and the context — into a paste-ready goal-mode prompt and a matching human brief, then stops.

## Contents

- [Gotchas](#gotchas)
- [When this applies](#when-this-applies)
- [Packet contract](#packet-contract)
- [Process](#process)
- [Task seeding](#task-seeding)
- [Sub-skills](#sub-skills)
- [Constraints](#constraints)
- [File index](#file-index)
- [Folder map](#folder-map)

## Gotchas

- Inventing tasks not on the live task list is the top failure mode. TASKS always comes verbatim from `TaskList`/`TodoWrite` — never fabricated.
- This skill is not `/task-build`. `/task-build` registers *new* tasks from the conversation; `/build-goal` only *exports* the existing list. It never creates tasks.
- Every DONE WHEN bullet is a checkable fact — a command, a test, a repo state. No vibes, no "make it good."
- The job ends at delivering the two files and showing the fence in chat. Never start the goal's own work.
- OUT OF SCOPE lines carry real new substance a reader would not already infer from DONE WHEN. Do not restate an exclusion DONE WHEN already implies.
- When the aim or the task list is too thin to fill the packet, ask exactly one `AskUserQuestion`, then continue. Never chain a second clarifying question.

## When this applies

- The user or a caller wants a paste-ready goal-mode prompt built from the current session: `/build-goal`, "build goal", "goal from context", "package this session into a goal".
- A caller (an orchestrator, a planning skill) needs a handoff prompt plus a plain-language brief for a fresh session or a fresh `/goal` run.

**Does not apply (refuse with the quoted line):**

- Caller wants the goal's actual work done now → "This skill only authors the goal-cmd prompt and the human brief; it does not carry out the goal's work. Paste the goal-cmd prompt into a new session to start the work."
- Caller wants new tasks registered from the conversation → "Use /task-build to register new tasks; /build-goal only exports the task list already on TaskList or TodoWrite."
- Caller wants a full XML system or developer prompt built in plan mode → "Use /anthropic-plan or prompt-generator for that; /build-goal produces the lighter goal-cmd and brief pair, not a plan packet."
- Caller wants a retrospective report of what happened → "Use /session-log for a retrospective report; /build-goal looks forward, not back."

## Packet contract

The script never gathers session facts itself — this session does, then writes them as JSON to a temp file:

```json
{
  "objective": "string, required, non-empty",
  "done_when": ["string", "..."],
  "in_scope": ["string", "..."],
  "out_of_scope": ["string", "..."],
  "tasks": [{"id": "string", "status": "pending|in_progress|completed", "subject": "string"}],
  "context": {"repo": "string|null", "branch": "string|null", "pr": "string|null", "paths": ["string"], "constraints": ["string"]},
  "execution_notes": ["string"]
}
```

`objective` and a non-empty `done_when` are required. Every other list may be empty — an empty list renders its header with no bullets beneath, never a placeholder sentence.

## Process

1. **Gather.** Read the conversation for the aim, the done-when facts, in/out-of-scope lines, and execution notes. Call `TaskList` (or `TodoWrite`) directly for the live task rows — never reconstruct tasks from memory. Read repo/branch/PR/paths and constraints already stated (git/gh state, named files). When the aim or the task list is too thin, ask exactly one `AskUserQuestion`, then continue.
2. **Write the packet.** Write the JSON packet above to a temp file with the session's own Write tool.
3. **Fill the templates.** Run `${CLAUDE_SKILL_DIR}/scripts/write_goal_pair.py <packet-json-path>`.
   - Exit 0 → stdout carries exactly two lines: `GOAL_CMD_PATH: <path>` and `HUMAN_BRIEF_PATH: <path>`.
   - Exit 2 → stderr names the missing field. Fix the packet from session facts (never invent the missing fact) and rerun.
4. **Deliver and stop.** Read the goal-cmd file back and show it in chat inside a fenced code block. State both absolute paths. Stop — do not begin the goal's own work.

## Task seeding

This process is four short steps run inside one turn — gather, write the packet, fill the templates, deliver. It is short enough that no task-seed list applies; work the steps directly.

## Sub-skills

N/A — pure leaf skill. `orchestrator` is named only inside the *rendered* EXECUTION NOTES text as a fact about the current session; this skill never invokes it as a process step. Related skills stay separate: `task-build` (registers new tasks; this skill only reads the list), `prompt-generator` (heavier XML plan-mode prompts), `session-log` (a retrospective report, not a forward-looking prompt).

## Constraints

- Invent nothing. Every fact in the packet traces to the live session — the conversation, the task list, git/gh state, or a named file.
- The job stops after the file pair and the fence in chat. Carrying out the goal's work is out of scope.
- Goal-cmd and brief prose stays in the present tense and states the aim directly, with no comparison to a path not taken.
- SKILL.md and both `templates/*.md` files are `.md` writes that must pass the `state_description_blocker` and `plain_language_blocker` hooks — write them clean the first time.
- Every non-obvious literal in `write_goal_pair.py` lives in `build_goal_constants/` — no bare magic strings or numbers in the function bodies.

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | This hub: principle, gotchas, when-applies, packet contract, process, constraints |
| `templates/goal-cmd-template.md` | Fixed goal-mode prompt skeleton the script fills |
| `templates/human-brief-template.md` | Fixed skim-table brief skeleton the script fills |
| `scripts/write_goal_pair.py` | **Execute** — validates the packet, fills both documents, writes them atomically |
| `scripts/test_write_goal_pair.py` | Behavioral tests against real files and the real templates |
| `build_goal_constants/__init__.py` | Package marker |
| `build_goal_constants/write_goal_pair_constants.py` | Named constants the script imports |

## Folder map

- `templates/` — the two fixed skeletons the script fills
- `scripts/` — the deterministic CLI and its paired test
- `build_goal_constants/` — named constants the CLI imports
