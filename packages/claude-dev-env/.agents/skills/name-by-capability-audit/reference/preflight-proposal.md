# Preflight proposal mode

Use this mode when the caller selects `preflight-proposal`. The mode prepares a reviewable candidate and returns evidence for downstream selection.

```text
name-by-capability-audit preflight-proposal <pr_number> --base-sha <base_sha> --head-sha <head_sha> --worktree <isolated_worktree>
```

## Required inputs

| Input | Contract |
|---|---|
| `pr_number` | Resolved open pull-request number |
| `--base-sha` | Full immutable base commit SHA |
| `--head-sha` | Full immutable head commit SHA |
| `--worktree` | Caller-supplied isolated worktree path |

## Contract

1. Resolve and validate the PR number, base SHA, head SHA, and isolated worktree before the first audit command.
2. Run `git rev-parse HEAD` in the supplied worktree and require exact equality with the head SHA.
3. Gather changed paths and audit scope from the exact `base_sha...head_sha` range. Use the resolved PR number for PR metadata only.
4. Run the complete audit and findings against that immutable range and worktree.
5. Keep every audit edit and test inside that worktree. The worktree is the complete write boundary.
6. Create an immutable proposal identity. Use the existing commit SHA when the proposal is already committed. For working-tree edits, use a deterministic diff hash over the baseline `HEAD` SHA, base SHA, head SHA, sorted normalized changed paths, status records, and file bytes.
7. Record every changed path, including tracked, untracked, renamed, and deleted paths.
8. Record exact tests and outcomes: every test command, exit code, and outcome.
9. Return selected-candidate-ready proposal evidence with the proposal ID, isolated worktree path, changed paths, findings, tests, and outcomes.
10. Suppress commit, push, pull-request body, pull-request comment, pull-request review, pull-request update, merge, rebase, and Ready-state mutations.
11. Add the proposal ID to the downstream owner's selected or dispositioned proposal collection. A finding discovered after proposal creation receives a new proposal ID and new evidence.

## Evidence record

Use this record shape:

```yaml
mode: preflight-proposal
pr_number: <resolved PR number>
base_sha: <immutable base SHA>
head_sha: <immutable head SHA>
proposal_id:
  kind: commit-sha | diff-sha256
  value: <immutable identity>
isolated_worktree: <caller-supplied path>
changed_paths:
  - <normalized path>
findings:
  - <finding with violation or OK-driver classification>
tests:
  - command: <exact command>
    exit_code: <integer>
    outcome: <exact outcome>
downstream_selection: required
```

The downstream owner adds proposal IDs from these records to selected or dispositioned collections. Reapplication uses exactly the selected records and their changed paths. New findings use new records.
