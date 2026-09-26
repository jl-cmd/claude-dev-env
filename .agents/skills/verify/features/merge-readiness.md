# Merge readiness

Three read-only commands tell the agent that drives a pull request whether it may merge. The merge check reads the live pull request and prints `MERGE` or `HOLD`. The review closure check prints `CLOSED` or `OPEN` for the review findings on the head commit. The merge gate check holds `docs/merge-policy.md` to the branch ruleset on `main`.

## Sub-features

- `merge-verdict` prints one `MERGE` or `HOLD` line for a pull request. It exits 0, 1, or 2.
- `merge-hold-reasons` names one repair for a draft, a head behind the base, a conflict, a failing required check, a failing or running check, an unknown merge state, and open review threads.
- `review-closure-verdict` prints one `CLOSED` or `OPEN` line, then one line per waiting finding. It exits 0, 1, or 2.
- `review-closure-driver` counts replies from the account that opened the pull request, plus each `--driver-login`.
- `review-closure-workflow` runs the closure check as the `Review closure` job on each pull request push, review, and review comment, and posts a `Review closure` check run on the head for each top-level comment posted or edited.
- `merge-gate-snapshot` compares the policy document with the checked-in ruleset snapshot.
- `merge-gate-live` compares the policy document with the live ruleset, and `--refresh` rewrites the snapshot.

## How to get to it (user POV)

- The agent runs the merge check before it merges a pull request it drives.
- The agent reads the `Review closure` check on the pull request, or runs the same command.
- A pull request that changes `docs/merge-policy.md` or the ruleset snapshot runs the paired test.
- A private consumer repository runs `review_closure.py` from its own workflow, against the package revision that workflow pins.

## Driving it with the package

Preconditions:

- `GH_TOKEN` or `GITHUB_TOKEN` holds a token that can read pull requests and check runs.
- Commands run from the repository root with Python 3.11 or later.

- **Merge verdict on a draft.** Run `python packages/claude-dev-env/scripts/agent_merge_check.py jl-cmd/claude-dev-env <draft number>`. The line reads `HOLD jl-cmd/claude-dev-env#<number> <short sha> :: The pull request is a draft` and the exit code is `1`.
- **Merge verdict on a ready pull request.** Run the same command on an open ready pull request. A clean head with no open thread prints `MERGE ... :: green, no open review thread, ready for the agent to merge` and exits `0`. A red required check prints `HOLD ... :: A required status check is not passing on this head` and exits `1`.
- **Unreadable state.** Run the command with a pull request number that does not exist. It prints `HTTP Error 404: Not Found` to stderr and exits `2`.
- **Review closure.** Run `python packages/claude-dev-env/scripts/review_closure.py jl-cmd/claude-dev-env <number>`. A head with every finding answered prints `CLOSED ... :: every review finding on this commit is answered` and exits `0`. A waiting finding prints `OPEN ... :: <count> review finding(s) wait on the driving agent`, one `  - <file, comment URL, or check>: <reason>` line per finding, and exits `1`.
- **Policy snapshot.** Run `python packages/claude-dev-env/scripts/merge_gate_checks.py --document docs/merge-policy.md --ruleset docs/merge-policy-ruleset.json`. It prints `docs/merge-policy.md: the ruleset requires every named check` and exits `0`. Add `--repository jl-cmd/claude-dev-env --live` to compare with the live ruleset.
- **Proof.** Run `python -m pytest scripts/test_agent_merge_check.py scripts/test_merge_gate_checks.py scripts/tests/test_review_closure.py scripts/tests/test_review_closure_model.py scripts/tests/test_review_closure_github.py -q` from `packages/claude-dev-env`. Every test passes. The tests cover the `OPEN`, red-circle, and `Claude Approvals` branches with fixtures.

## Gotchas

- A merged pull request reads `HOLD ... merge state as unknown`. GitHub reports `unknown` after a merge, and the check reads five times, three seconds apart, before it gives that verdict.
- Only the account that opened the pull request counts as the driver. A reply from a second login leaves the thread open until `--driver-login <login>` names that login.
- A thread whose first comment carries a red circle stays open after resolution. It closes on a driver reply or on a push that makes the thread outdated.
- A `Claude Approvals` check run that concludes `failure` or `action_required` on the head adds one `OPEN` finding. A repository without that check skips this finding.
- Both scripts read review threads from the Claude Code session route first and fall back to GraphQL. A proxy that refuses both routes makes the command exit `2`.
- `--refresh` writes `docs/merge-policy-ruleset.json`. Run it only when the ruleset change is intended, and commit the new snapshot with the policy change.
- The branch rule requires an up-to-date head. After one merge, every other ready pull request reads `HOLD` with the behind reason until its branch takes the new `main`.
