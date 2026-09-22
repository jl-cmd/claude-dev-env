# Pull request authorship

Graphite's review app skips a pull request a bot account opened. A pull
request the Claude GitHub App opens shows as `claude[bot]`; a pull request
`agent-bridge.yml`'s own commit-and-push step opens under the job's
`GITHUB_TOKEN` shows as `github-actions[bot]`. Neither gets a Graphite
review.

## How a pull request opens as Jon

`.github/workflows/open-pr-as-jon.yml` runs on the `agent-pc` runner pool,
where `gh` is already signed in as `JonEcho`. It takes `head`, `base`,
`title`, `body`, and `draft` as `workflow_dispatch` inputs, checks that the
signed-in account is `JonEcho`, and calls `gh pr create` from that session.
It pushes nothing; the branch it opens against is pushed first, by whatever
wrote the change.

An agent that finishes a branch and is ready to open its pull request
dispatches this workflow to open it. The workflow file lives in each repository it serves
(`Echo-Visuals-Inc/python-automation` and this repository both carry a
copy), because a self-hosted runner pool is registered per repository and a
cross-repository reusable workflow call cannot reach it.

## Commit authorship

A commit pushed from the `agent-pc` or `jon-pc` runner pool carries
`JonEcho <24366590+JonEcho@users.noreply.github.com>` as its author, set
through `git config user.name` / `user.email` before the commit.
`agent-bridge.yml`'s commit-and-push step sets this identity for every
builder-produced commit. `24366590` is Jon's GitHub account id, so the
address links the commit to his account without needing his email.

A commit a cloud thread session pushes stays authored as `Claude
<noreply@anthropic.com>`, whatever the session's own `git config` says: the
platform stamps that identity on the commit itself, separately from the
push credential. Setting `git config user.name`/`user.email` to Jon's
identity from a cloud session changed nothing on the commit that push
produced; confirmed on this repository's own
`0944be69d03a16669c76ffe1e939ff2dac034b56` and
`Echo-Visuals-Inc/python-automation`'s `bf9c28971f1750f0a7bf96f9b786e17f6a21886a`,
both pushed from a cloud session with `user.name` set to `JonEcho` and both
landing authored as `Claude`. Opening the pull request as Jon through the
workflow above does not depend on this and is unaffected by it.

## What this does not change

Graphite reviewing the pull request is a fact to confirm on each one, not
a property this workflow guarantees; check that the `Graphite / AI Reviews`
check run appears on a pull request before treating it as reviewed. Who
merges a pull request stays what [`merge-policy.md`](merge-policy.md)
states: the driving agent, once its gates pass.
