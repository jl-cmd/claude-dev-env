---
name: syncing-submodules
description: >-
  Records a submodule's current commit in its parent repository.
  Triggers: submodule sync, /submodule-sync, sync parent submodule,
  update parent pointer, record submodule commit, commit submodule pointer,
  sync superproject, update superproject pointer, parent repo submodule update,
  finish submodule commit. Does not handle clone, checkout, update main,
  or ordinary commits.
---

# Syncing submodules

## Principle

A submodule commit changes the child repository first. Change the parent pointer only when this skill runs. Limit the parent commit to the submodule path so other staged work stays staged.

## Gotchas

- Inherited `GIT_*` variables can redirect child Git commands. The script removes them from its Git environment.
- Submodule paths can contain brackets or wildcard characters. The script sends Git a literal pathspec.
- `git diff --cached --quiet` uses exit 1 for a changed pointer. Any higher exit is a failure.
- The parent repository may already contain staged work. The path-only commit must leave it staged.
- A repository without a superproject is a successful `not_submodule` result.
- The old hook returned success after a failed parent commit. This command returns a nonzero exit.

## When this applies

Use this skill after committing inside a checked-out submodule when its parent repository should record the new commit.

Refusals use the first matching line:

- Clone, initialize, or check out a submodule: `Use Git's submodule commands. This skill records an existing submodule commit in its parent.`
- Fast-forward `main`: `Use /update. This skill changes one parent submodule pointer.`
- Make an ordinary commit or push: `Use /source-command-commit. This skill commits only a parent submodule pointer.`

## Process

### Seed the run tasks

Register every item in `reference/run-tasks.md` as a session task with the host task tool. Complete each task with an exit code, JSON field, or repository readback. If the host has no task tool, stop with `A task tool is required to track this repository-changing operation.`

### Run the command

Execute the bundled script. Do not reconstruct the Git sequence by hand.

```text
python "${CLAUDE_SKILL_DIR}/scripts/sync_parent_pointer.py" --repository "<submodule-path>"
```

Python 3 and Git are required. GitHub CLI is optional and only supplies an open pull request URL.

The script writes one JSON object to standard output. Exit 0 permits `updated`, `unchanged`, and `not_submodule`. Exit 1 reports a Git or repository failure. Exit 2 reports invalid arguments. Treat every nonzero exit as incomplete work. Fix the reported condition, rerun the command, and keep the task open until the command exits 0.

### Report the result

- `updated`: report `parent_repository`, `submodule_path`, `commit`, and `parent_commit`.
- `unchanged`: report that the parent already records `commit`.
- `not_submodule`: report that no parent repository changed.
- `pull_request_url`: invoke `/pr-title-description` with that URL after reporting the sync result.

If `/pr-title-description` is not installed, report `pull_request_url` and finish the successful sync.

## Constraints

- Run the script from this skill package.
- Commit only the literal submodule path in the parent repository.
- Preserve every unrelated staged parent path.
- Never push, switch branches, rewrite commits, or change Git configuration.
- Never treat a failed Git command as success.

## Examples

- Updated pointer: `status` is `updated`, `submodule_path` is `modules/child`, and `parent_commit` names the new parent commit.
- No superproject: `status` is `not_submodule`; every parent and commit field is null.
- Failed stage: exit 1, `status` is `error`, and standard error starts with `syncing-submodules:`.

## Sub-skills

| Skill | When | Produces | Missing behavior |
|---|---|---|---|
| `/pr-title-description` | The result includes `pull_request_url` | A title and description based on the full pull request diff | Report the URL and keep the completed sync |

## File index

| File | Purpose |
|---|---|
| `SKILL.md` | Selection, operation boundary, result handling, and peer routing |
| `reference/run-tasks.md` | Task seeds for each repository-changing run |
| `scripts/sync_parent_pointer.py` | Execute the parent pointer sync and return one JSON result |
| `scripts/submodule_sync.py` | Own the Git operation and typed sync report |
| `scripts/test_sync_parent_pointer.py` | Prove command parsing, JSON output, and hook deletion |
| `scripts/test_submodule_sync.py` | Prove exact commits, preserved staging, no-op states, and failures |
| `scripts/submodule_sync_constants/__init__.py` | Mark the constants package |
| `scripts/submodule_sync_constants/config/__init__.py` | Mark the configuration package |
| `scripts/submodule_sync_constants/config/constants.py` | Named command, message, field, and exit-code constants |

## Folder map

- `reference/` contains the run task seeds.
- `scripts/` contains the executable command, Git operation, tests, and constants package.
