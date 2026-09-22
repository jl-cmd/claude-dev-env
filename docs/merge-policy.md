# Merge policy

This document states how a change reaches `main` in this repository. It names
the gates in the order they run, says which ones hold the merge and which ones
report only, says who performs the merge, and states the rollback path.

## The gates, in order

| Order | Gate | Holds the merge | Where it runs |
|---|---|---|---|
| 1 | The pull request opens as a draft with a Before and an After in its body | yes | the agent that opens it |
| 2 | The full Python and JavaScript suites run on the draft | yes | GitHub Actions |
| 3 | The required status check reports green on the head commit | yes | GitHub Actions |
| 4 | The head is up to date with `main`, because the branch rule is strict | yes | GitHub Actions |
| 5 | Every review thread on the head is answered or resolved by the driving agent | yes | the driving agent |
| 6 | The `Review closure` check reports green on the head commit | yes | GitHub Actions |
| 7 | The merge check reads the live pull request and reports `MERGE` | yes | the driving agent |
| 8 | Advisory findings the follow-up ledger holds | no | the policy lint |
| 9 | Review-bot findings the reviewing bot marks optional | no | the review bots |

Gate 6 goes red while a blocking review finding on the head has no reply and no
resolving push, so a finding holds the merge until the driving agent answers it.
The check runs from the revision `.github/workflows/review-closure.yml` pins.

Gate 7 reads the pull request's live state: out of draft, merge state clean,
and no open review thread. It prints `HOLD` with the repair when one of those
fails, and every repair belongs to the driving agent.

Gates 8 and 9 report and record. A finding there opens its own pull request and
never holds this one.

## The required status checks

The branch ruleset on `main` requires this context:

```required-status-checks
instruction-pairs / instruction-pairs
```

The branch rule asks for zero approvals and keeps heads up to date, so no human
approval is needed to merge here.

`packages/claude-dev-env/scripts/merge_gate_checks.py` reads the block above
and the branch ruleset, and reports every context named here that the ruleset
stopped requiring.
`packages/claude-dev-env/scripts/test_merge_gate_checks.py` runs that
comparison against the checked-in ruleset snapshot at
[`merge-policy-ruleset.json`](merge-policy-ruleset.json). Refresh the snapshot
with:

```
python packages/claude-dev-env/scripts/merge_gate_checks.py \
  --document docs/merge-policy.md \
  --ruleset docs/merge-policy-ruleset.json \
  --repository jl-cmd/claude-dev-env \
  --refresh
```

## Gates this repository has adopted and not yet built

These two gates hold the merge once they ship, and each one joins the table
above in the pull request that builds it. A gate that cannot go red on a
scratch branch stays off the list until it can.

- An install playtest that installs the package into a scratch home, starts a
  session-start hook and one blocking hook against a fixture payload, and reads
  the output envelope.
- A verification swarm that reproduces the Before and the After from the pull
  request body and posts one verdict for the head commit.

## Who merges

The agent that drives the pull request merges it, once the gates above pass.
This repository runs no merge queue, so the merge is a direct call on the pull
request.

No agent overrides a red check. A person merges by hand only when Jon says to
merge. Writes to the live Samsung portals, to the theme database, and to Jon's
machine outside an `agent-pc` job stay behind Jon's word.

## Rollback

A merge that has to come out goes back through the same path. The merge handler
thread opens a revert pull request, drives it through the gates above, and
merges it. Nobody pushes to `main` and nobody force-pushes it.
