# The Agent Merges Its Own Green Pull Request

**When this applies:** Any pull request an agent opened or was asked to drive, once its checks report.

## Rule

The agent that drives a pull request merges it. A pull request that is green, carries no open review thread, and sits at a merge state of `clean` is merged in the same run that brought it there. Waiting for the owner to type "merge" parks finished work on the person the work was done for.

Three things stay with the owner, and nothing else does:

- A pull request the owner asked to hold.
- A change the owner said they want to read first.
- A repository whose branch rule requires an approving review the agent cannot give.

Where the branch rule requires zero approvals and one status check, that check is the gate, and the agent merges on its verdict.

Validation is the precondition, and green means every check reported on the exact head commit. A branch rule that requires one status check names the floor a merge needs; a pull request whose other checks are red or still running is held until they report.

## The precondition is mechanical

One command prints the verdict:

```
python packages/claude-dev-env/scripts/agent_merge_check.py <owner>/<name> <number>
```

It prints `MERGE` and exits 0 when the pull request is ready. It prints `HOLD` with the reason and exits 1 for a draft, for a head behind or conflicting with the base, for a required check that is not passing, for a check still running or red, and for an open review thread. It exits 2 when the state could not be read.

Each hold reason names its own repair, and each repair belongs to the agent:

| Hold | What the agent does |
|---|---|
| Head behind the base | Merge the base branch in and push |
| Head conflicts with the base | Merge the base branch in, resolve, push |
| A required check is red | Read the failing check, fix it, push |
| A check is red or still running | Fix it, or wait for it, then read the verdict again |
| A review thread is open | Answer it, push the fix, resolve the thread |
| The pull request is a draft | Mark it ready once the checks pass |

## When a gate elsewhere holds the merge command

A session working inside another repository can sit behind that repository's own pre-merge gate, which reads the checkout the session works in and refuses a merge command whatever repository the pull request belongs to. That session hands the merge to the session that owns this repository's pull requests, by message, naming the pull request. The receiving session reads the verdict above and merges. The hand-off carries the work; it never lands on the owner.

## After the merge

Delete nothing by hand. The repository deletes the head branch on merge.

## Sibling rules

| Rule | Role |
|---|---|
| [`git-workflow.md`](git-workflow.md) | Draft first, and confirm each required context fired after the push |
| [`ci-owns-the-gate.md`](ci-owns-the-gate.md) | The gate runs once, and it runs on CI |
| [`correction-lens.md`](correction-lens.md) | A correction becomes a control at the highest layer that can hold it |
