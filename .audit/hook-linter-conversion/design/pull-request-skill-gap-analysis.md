# Gap analysis: pull-request skill

## Skill type

Type 7, CI/CD and deployment. The skill publishes and updates pull requests through one guarded command.

## Task description

Create, edit, comment on, or review a GitHub pull request through validated files and process-local credentials.

## Degree of freedom

Low. GitHub writes, credential selection, post validation, and legacy account recovery have exact inputs, failure states, and side effects.

## Composition plan

- Capability sentence: Publish one pull request action through validated inputs and process-local credentials.
- `pr-description-writer`: invoke before pull request creation or a full description rewrite. It produces the required title and body file without a spawn marker.
- `pr-title-description`: use only when another title and body review helps the writer.
- `privacy-hygiene`: invoke before the GitHub post. It produces a clean body and staged repository sweep.
- `issue-tracker`: owns issue create, edit, and comment actions and calls the shared body linter.
- `pr-cleanup` and `autoconverge`: own review convergence.
- `source-command-commit`: owns commits.
- `gh_artifact_upload.py`: reuse through the artifact guidance. It owns permanent binary artifact URLs.
- Split decision: one pull-request leaf skill plus one shared body linter used by existing pull request, issue, and GitHub tool workflows.
- Missing sub-skills: none. The existing issue skill receives a linter call without a new issue workflow.

## Description triggers

- Capability stem: validated GitHub pull request create, edit, comment, and review actions.
- Trigger phrases: create PR, open pull request, edit PR, update PR body, comment on PR, review PR, publish draft PR, use scoped GitHub author.
- Leave issue filing to `issue-tracker`. Leave commit creation to `source-command-commit`.
- Draft description:

```yaml
description: >-
  Validate and publish GitHub pull request actions. Triggers: create PR, open pull request, edit PR, update PR body, comment on PR, review PR, publish draft PR, scoped GitHub author.
```

## Deterministic elements inventory

| Step | Class | Home path | Evidence | Paired test |
|---|---|---|---|---|
| Validate GitHub post body | deterministic | `_shared/pr-loop/scripts/durable_post_lint.py` | Same file and action produce the same findings and exit status. | `_shared/pr-loop/scripts/test_durable_post_lint.py` |
| Resolve process-local author | deterministic | `.agents/skills/pull-request/scripts/pull_request.py` | Account input maps to one token lookup and child environment. | `.agents/skills/pull-request/scripts/test_pull_request.py` |
| Run pull request action | deterministic | `.agents/skills/pull-request/scripts/pull_request.py` | Structured arguments map to one `gh` child command and exit status. | `.agents/skills/pull-request/scripts/test_pull_request.py` |
| Recover one legacy swap record | deterministic | `.agents/skills/pull-request/scripts/recover_legacy_author.py` | One selected stale record maps to one verified restore attempt. | `.agents/skills/pull-request/scripts/test_recover_legacy_author.py` |
| Author title and body | judgment | `pr-title-description` skill | The writer derives human-facing text from the full diff. | N/A, existing skill |
| Upload binary evidence | deterministic | `scripts/gh_artifact_upload.py` | Existing uploader returns the permanent GitHub URL. | `scripts/tests/test_gh_artifact_upload.py` |
| Required publication gates | deterministic | `reference/publication-tasks.md` | Each action completes the same evidence-backed gates. | task list |

## Gaps identified

### Global credential mutation

- What happened: the PreToolUse hook switched the global GitHub CLI account and depended on two later hooks to restore it.
- What was needed: resolve the selected account token and pass it only to the one child process.
- Frequency: every pull request creation when `GITHUB_DEFAULT_ACCOUNT` names another account.
- Example task: create two pull requests concurrently with different author accounts.

### Action-time blocks before the command owner

- What happened: body shape, writer tracking, post input loading, title shape, and local path checks stopped valid pull request commands.
- What was needed: validate the structured title and post input in the publishing command before network access.
- Frequency: every pull request creation, edit, comment, or review that matches a global hook.
- Example task: create a draft pull request from an isolated worktree with a durable body file.

### Shared GitHub post coverage

- What happened: two hook files covered pull requests, issues, and GitHub tool calls. Deleting them for pull requests alone would remove issue coverage.
- What was needed: one action-aware body linter used by the new pull request command and the existing issue and GitHub tool owners.
- Frequency: every durable GitHub post.
- Example task: comment on an issue with a local worktree artifact path in the body.

### Pending legacy swap records

- What happened: a crash could leave the global account switched and a secure recovery record in the system temporary directory.
- What was needed: an explicit command that recovers one selected stale record, leaves ambiguous or active records alone, and deletes only after success.
- Frequency: uncommon, but high impact during upgrade.
- Example task: recover one old record while a second record remains untouched.

## Patterns

- Each policy belongs beside the GitHub action that consumes it.
- Shared body checks need an action enum because descriptions, comments, reviews, and issues have different required structure.
- Process-local environment values remove global account restore and cleanup phases.
- Legacy recovery stays explicit because multiple records do not define one final account.

## Initial gotcha candidates

- Require `pr-description-writer` for authoring without proving its spawn through a session marker.
- Validate every local file before token lookup or network use.
- Keep tokens out of standard output, standard error, exceptions, and result objects.
- Never call `gh auth switch` from normal pull request actions.
- Recover one verified stale state record at a time. Preserve every record on failure.
