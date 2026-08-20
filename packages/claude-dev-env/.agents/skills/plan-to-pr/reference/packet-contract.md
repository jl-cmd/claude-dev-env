# Native Plan-to-PR packet contract

The planning phase produces one self-contained packet at
`docs/plans/<slug>/`. The slug contains lowercase letters, numbers, and single
hyphens, starts and ends with a letter or number, and is unique among active
plans. The packet is complete before `TaskCreate` or `TodoWrite` runs.

## Required files

| File | Required content |
|---|---|
| `packet.json` | Validates against `reference/packet-schema.json`; includes every required field. |
| `context.md` | Request, repository facts, constraints, source references, and open questions. |
| `plan.md` | Ordered implementation approach, decisions, dependencies, and risks. |
| `tasks.md` | Ordered task list with one deliverable, file set, acceptance command, and commit per task. |
| `handoff.md` | Exact task-seeding input and the approval state. |

## Deterministic boundaries

- `packet.json` is the machine-readable authority. Markdown restates the same
  scope, tasks, files, commands, and acceptance criteria.
- `status` is `draft` while writing and `approved` only after all checks pass.
- `allowed_files` contains repository-relative file paths only. Every task file
  belongs to that set, so task edits stay within the packet scope.
- `tasks` is ordered, non-empty, and each task has exactly one deliverable,
  one non-empty `allowed_files` list, one acceptance command, one test command,
  one verification command, and one commit.
- Every source reference identifies a repository-relative path and a line or
  section locator. Unknown facts are recorded in `open_questions`.
- Acceptance commands are executable, deterministic checks against real behavior.
  Each task carries an executable command rather than a prose-only statement.
- `handoff.md` names the packet path, validation result, task order, and exact
  host-task fields. It lists exactly the tasks declared in `packet.json`.

## Validation sequence

1. Parse `packet.json` as JSON and validate it against the schema.
2. Validate the slug, required files, path boundaries, task uniqueness, and
   task-to-file containment.
3. Confirm every source reference, command, and acceptance check is concrete.
4. Compare Markdown task and handoff content with `packet.json`.
5. Set `status` to `approved` after every check passes. Keep `draft` packets in
   planning and validation until that approval state is reached.
