# build-goal

Authors a paste-ready goal-mode prompt plus a human-readable brief from the current session's context and task list, then stops without carrying out the goal's work.

**Trigger:** `/build-goal`, "build goal", "goal from context", "goal-cmd from session", "make a goal prompt", "goal mode prompt from tasks", "package this session into a goal".

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Hub: gotchas, when-applies, packet contract, process, constraints |
| `templates/goal-cmd-template.md` | Fixed goal-mode prompt skeleton |
| `templates/human-brief-template.md` | Fixed skim-table brief skeleton |
| `scripts/write_goal_pair.py` | Deterministic CLI: validates the packet, fills both documents, writes them atomically under the OS temp directory |
| `scripts/test_write_goal_pair.py` | Behavioral tests against real files and the real templates |
| `build_goal_constants/write_goal_pair_constants.py` | Named constants the CLI imports |

## How the skill runs

1. The session gathers its aim, done-when facts, task list (via `TaskList`/`TodoWrite`), and context, then writes a JSON packet to a temp file.
2. The session runs `scripts/write_goal_pair.py <packet-json-path>`.
3. On exit 0, stdout carries the two output paths (`GOAL_CMD_PATH:` and `HUMAN_BRIEF_PATH:`); on exit 2, stderr names the missing field.
4. The session shows the goal-cmd fence in chat, states both paths, and stops.

## Conventions

- Task rows always come from the host task list — never invented.
- Every DONE WHEN bullet is a checkable fact.
- The skill stops after delivering the pair; it never starts the goal's own work.
