---
name: pull-request
description: >-
  Validate and publish GitHub pull request actions. Triggers: create PR, open
  pull request, edit PR, update PR body, comment on PR, review PR, publish a
  draft PR, scoped GitHub author.
---

# Pull request

## Contents

- [Principle](#principle)
- [When this applies](#when-this-applies)
- [Constraints](#constraints)
- [Dependencies](#dependencies)
- [Sub-skills](#sub-skills)
- [Task seeding](#task-seeding)
- [Process](#process)
- [Exit handling](#exit-handling)
- [Examples](#examples)
- [Gotchas](#gotchas)
- [File index](#file-index)
- [Folder map](#folder-map)

## Principle

Publish one GitHub pull request action from validated local files and a
process-local author value. Keep the parent environment unchanged.

## When this applies

Use this skill for one pull request action:

- Create a draft pull request.
- Edit a pull request title or body.
- Add a pull request comment.
- Submit a pull request review.
- Recover one selected legacy author record before the action.

Send issue create, edit, and comment work to `issue-tracker`. Send review
convergence to `pr-cleanup` or `autoconverge`. Send commits to
`source-command-commit`.

Require one repository and one action target. Stop before author lookup or
network work when the repository, pull request, action, author, or required
local file is missing or ambiguous.

Use these exact refusal responses when the request belongs to another skill:

- Issue action: `Use issue-tracker for this GitHub issue action.`
- Commit or push: `Use source-command-commit for this commit or push.`
- Missing target: `Provide one repository and one pull request action target.`

## Constraints

- Run local validation and privacy checks before account lookup or network work.
- Use a body file. Do not send inline body text through the shell.
- Keep `GITHUB_DEFAULT_ACCOUNT`, the parent environment, and global GitHub CLI
  state unchanged.
- Run one create, edit, comment, review, or recovery action per command.
- Use global account switching only for one explicitly selected legacy record.
- Read back the remote state before reporting success.

## Dependencies

The commands use Python 3.11 or later and the Python standard library. GitHub
actions also require an authenticated `gh` executable. The linter and artifact
uploader ship in this package. Set `GITHUB_DEFAULT_ACCOUNT` to one exact GitHub
CLI login when the action needs a selected author. Leave it unset to use the
current process environment.

## Sub-skills

| Skill | When | Produces | If missing |
|---|---|---|---|
| `pr-description-writer` | Before create or a full body rewrite | A reviewed title and body file | Stop the create or rewrite and report that authoring is required |
| `pr-title-description` | Optional title and body review | Review findings for the writer's output | Continue with the required writer output |
| `privacy-hygiene` | Before any durable GitHub post | A clean body and repository privacy sweep | Stop before publication and report the missing gate |
| `issue-tracker` | Issue create, edit, or comment requests | Issue state and issue URLs | Route the request there. |
| `pr-cleanup` | Placement, naming, sizing, or cleanup convergence | Cleanup findings or a focused PR boundary | Route the request there. |
| `autoconverge` | Autonomous PR review and fix loops | A converged draft or ready-state decision | Route the request there. |
| `source-command-commit` | Commit or push requests | A verified commit or pushed branch | Route the request there. |

## Task seeding

At the start of the work, register every item in
`reference/publication-tasks.md` through `TaskCreate`, `TodoWrite`, or the host
task equivalent when one is available. If no task tool is available, use the
catalog and the running work ledger. Mark each task with `PASS`, `FAIL` plus
file and line evidence, or `N/A` plus a reason for a conditional task.

## Process

### 1. Scope the action

Resolve the repository, action, and selected GitHub author. For create, resolve
the source branch, base, and head. For other actions, resolve one existing pull
request target. Create actions publish drafts. Record the target before any write.

### 2. Author the title and body

For create and full body rewrite, invoke the installed
`pr-description-writer`. Require its title and body file as the authoring
output. `pr-title-description` may review that output. A comment or review may
use a supplied body file when it does not rewrite the pull request description.

### 3. Run the local linter

Run `_shared/pr-loop/scripts/durable_post_lint.py` with the matching action and
title or body file. Use `pr-create`, `pr-edit`, `pr-comment`, or `pr-review`.
The linter owns the action-specific body, title, and volatile-path rules.

Exit code `0` continues to the next gate. Any non-zero exit stops the action. Fix
the named local input and rerun the linter. Do not look up the author or make a
network call while validation fails.

### 4. Run privacy and artifact checks

Invoke `privacy-hygiene` before the GitHub post. Upload binary evidence with
`scripts/gh_artifact_upload.py` and replace local artifact references with
permanent URLs. Rerun the linter after changing the body.

### 5. Resolve the process-local author

Run `.agents/skills/pull-request/scripts/pull_request.py` with one structured
action and the selected author. The command runs the linter again, resolves
the author value, and passes it only to the child `gh` process. It never
changes the parent environment or calls `gh auth switch`.

If the selected author has no usable value, stop and report the account lookup
failure. Never print the value.

### 6. Recover a selected legacy record

Run `.agents/skills/pull-request/scripts/recover_legacy_author.py
<exact-state-file> --confirm-inactive` only when the user selects one legacy
state file. The command checks the record's age, secure file metadata, and
contents. The confirmation flag records that the caller verified inactivity.
Leave every other record untouched. Delete the selected record only after a
successful restore. Mark this step `N/A` when no legacy state file is selected.

### 7. Run the action

Run `pull_request.py` for exactly one of `create`, `edit`, `comment`, or
`review`. Supply the validated body file path. Treat a non-zero exit as a
failed publication and preserve the local inputs for retry.

### 8. Read back the remote state

Use the same selected process-local author for a read-only remote readback.
Confirm the pull request URL and number, title, body, head SHA, and draft state.
For comments and reviews, confirm the new remote entry. Report artifact URLs
without exposing author values.

## Exit handling

Stop before network work when authoring, local validation, privacy, or author
selection fails. A failed action preserves its body and any recovery record.
Report the generic error and the next required input. A successful action ends
only after remote readback proves the requested state.

## Examples

Create example: the writer produces `pr-body.md`. The linter exits `0` for
`pr-create`. `pull_request.py create` publishes one draft pull request. The
readback matches the title, body, head SHA, and draft state.

Rejected comment example: the comment body names a worktree file. The linter
returns a non-zero exit. No account lookup or GitHub request runs. Replace the
path with inline text or a permanent artifact URL, then rerun.

Recovery example: one old record remains after an interrupted legacy account
swap. The user selects that exact file and confirms its session is inactive.
The recovery command restores the named account and deletes only that record.

## Gotchas

- Relative body-file paths depend on the caller directory. Use an absolute path
  when another process or worktree starts the command.
- A record older than 30 minutes can still belong to a live session. Require
  `--confirm-inactive` before recovery.
- Normal pull request actions never call `gh auth switch`. If that command
  appears outside explicit recovery, stop.
- GitHub CLI output can contain account data. The command captures account
  lookup and recovery output and prints only generic errors.

## File index

| Path | Purpose |
|---|---|
| `SKILL.md` | Hub for pull request publication, validation, author selection, recovery, and readback |
| `reference/publication-tasks.md` | Ordered tasks for every publication gate |
| `scripts/pull_request.py` | Command for author selection and create, edit, comment, and review actions |
| `scripts/github_pr_command_constants/` | Constants for pull request actions, recovery, exit codes, and generic messages |
| `scripts/test_pull_request.py` | Tests for `pull_request.py` |
| `scripts/recover_legacy_author.py` | Command for one selected legacy author record |
| `scripts/test_github_pr_command_constants.py` | Tests for the command and recovery constants |
| `scripts/test_recover_legacy_author.py` | Tests for `recover_legacy_author.py` |
| `_shared/pr-loop/scripts/durable_post_lint.py` | Shared action-aware title, body, and path validator |
| `_shared/pr-loop/scripts/test_durable_post_lint.py` | Tests for the shared validator |
| `scripts/gh_artifact_upload.py` | Helper for permanent GitHub binary evidence URLs |
| `scripts/tests/test_gh_artifact_upload.py` | Tests for binary evidence upload |

## Folder map

```text
pull-request/
├── SKILL.md
├── reference/
│   └── publication-tasks.md
└── scripts/
    ├── pull_request.py
    ├── github_pr_command_constants/
    ├── recover_legacy_author.py
    ├── test_pull_request.py
    └── test_recover_legacy_author.py
```
