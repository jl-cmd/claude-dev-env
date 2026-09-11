---
name: babysit-pr
description: Drive a PR to green CI with terse heartbeat reporting
---
Given a PR number:
1. `gh pr checks <PR> --watch` until terminal state.
2. For each failing job, fetch logs with `gh run view --log-failed`, root-cause, fix with the MINIMUM diff.
3. Show `git diff` in chat for every change. No prose summaries.
4. Push, re-watch. Report ONLY: check name -> pass/fail -> one-line cause.
5. Never mark ready-for-review; leave draft and report status.
