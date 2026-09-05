# Review preflight proposal mode

Use this mode when the caller selects `preflight-proposal`:

```text
/e-code-review preflight-proposal <pr_number> --level low --base-sha <base_sha> --head-sha <head_sha> --worktree <isolated_worktree>
```

## Required inputs

| Input | Contract |
|---|---|
| `pr_number` | Resolved open pull-request number |
| `--level` | Resolved review level: `low`, `medium`, or `xhigh` |
| `--base-sha` | Full immutable base commit SHA |
| `--head-sha` | Full immutable head commit SHA |
| `--worktree` | Caller-supplied isolated worktree path |

## Proposal contract

1. Validate every required input before the first review command.
2. Run `git rev-parse HEAD` in the supplied worktree and require exact equality with the head SHA.
3. Gather changed paths and review scope from the exact `base_sha...head_sha` range. Use the resolved pull-request number for pull-request metadata.
4. Run the complete selected review and findings against the immutable range and worktree.
5. Keep every review edit and test inside the caller-supplied isolated worktree.
6. Create an immutable proposal identity. Use the existing commit SHA for committed proposals. For working-tree edits, use a deterministic diff hash over the baseline `HEAD` SHA, base SHA, head SHA, sorted normalized changed paths, status records, and file bytes.
7. Record every changed path, including tracked, untracked, renamed, and deleted paths.
8. Record exact tests and outcomes: each test command, exit code, and outcome.
9. Return selected-candidate-ready proposal evidence with the proposal ID, isolated worktree path, changed paths, findings, tests, and outcomes.
10. Keep commit, push, pull-request body, pull-request comment, pull-request review, pull-request update, merge, rebase, and Ready-state mutations disabled.
11. Return the proposal for downstream disposition. The downstream owner adds the proposal ID to its selected or dispositioned proposal collection. Reapplication uses exactly the selected records and their changed paths. Give each later finding a new proposal ID and evidence record.

## Review level

The caller resolves the review level before invocation and always passes `--level`. Omitted `--level` is `low`. Passed `low`, `medium`, or `xhigh` stay as given.

The `review_level` evidence is the resolved `--level` value.

Run the selected level as `<review_level> --fix loop`. The selected level keeps its normal finding and fix rules. Require `HEAD` to equal the supplied head SHA before each round.

Gate 1, Gate 2, the bare code-rules gate, and exact required tests still apply.

## Evidence record

```yaml
mode: preflight-proposal
pr_number: <resolved PR number>
review_level: low | medium | xhigh
base_sha: <immutable base SHA>
head_sha: <immutable head SHA>
proposal_id:
  kind: commit-sha | diff-sha256
  value: <immutable identity>
isolated_worktree: <caller-supplied path>
changed_paths:
  - <normalized path>
findings:
  - severity: blocker | high | medium | low | nit
    verdict: CONFIRMED | PLAUSIBLE
    outcome: fixed | no_change_needed | skipped
tests:
  - command: <exact command>
    exit_code: <integer>
    outcome: <exact outcome>
downstream_selection: required
```
