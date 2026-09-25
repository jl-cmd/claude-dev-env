# Review Closure Is a Check

**When this applies:** Any pull request an agent drives, from the first review comment on it to the merge.

## Rule

A review finding on the head is answered before the pull request merges. The agent driving it replies, pushes the fix, or both. The check named `Review closure` reads that state on every push and on every review event, and reports red while a finding waits.

One command prints the same verdict:

```
python packages/claude-dev-env/scripts/review_closure.py <owner>/<name> <number>
```

It prints `CLOSED` and exits 0 when every finding on the head is answered. It prints `OPEN`, one line per waiting finding, and exits 1. It exits 2 when the state could not be read.

## What closes a finding

| The thread | Closed by |
|---|---|
| A review comment on code | A push that replaced the code it points at |
| A review comment on code | A reply from the account driving the pull request |
| A review comment on code | Resolution, where the comment carries no red circle |
| A red-circle finding | A reply from the driving account, or a push that replaced the code |
| A thread the driving account opened | Itself |
| A blocking `Claude Approvals` row | A push, which moves the head the check reports on |

A red circle marks a finding a review states as blocking, so resolution in silence leaves it open. The reply says what changed or why the finding stands, and the reviewer reads it beside the diff.

The driving account is the one that opened the pull request. Where the agent comments under a second login, `--driver-login <login>` names it, repeatably.

## Where the check runs

`.github/workflows/review-closure.yml` runs it here on a push to a pull request, on a submitted or dismissed review, and on a review comment. Each run reports on the pull request's head commit, so a finding posted after the last push still turns the check red.

A private repository that installs this package runs the same command from its own workflow, against the revision of this package that its workflow pins.

A repository that merges through a merge queue also runs the check on `merge_group` and lists `Review closure` as a required check. The queue ref `gh-readonly-queue/<base>/pr-<number>-<sha>` names the pull request number the command takes. A finding posted while an entry waits in the queue then fails the queue build. Without that trigger, the entry merges on the verdict it carried when it joined the queue.

## Sibling rules

| Rule | Role |
|---|---|
| [`agent-merges-its-own-green-pull-request.md`](agent-merges-its-own-green-pull-request.md) | The agent that drives a pull request merges it once its gate passes |
| [`git-workflow.md`](git-workflow.md) | Draft first, and confirm each required context fired after the push |
| [`correction-lens.md`](correction-lens.md) | A correction becomes a control at the highest layer that can hold it |
