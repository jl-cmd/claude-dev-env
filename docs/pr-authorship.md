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
dispatches this workflow instead of calling a GitHub pull-request-create
tool directly. The workflow file lives in each repository it serves
(`Echo-Visuals-Inc/python-automation` and this repository both carry a
copy), because a self-hosted runner pool is registered per repository and a
cross-repository reusable workflow call cannot reach it.

## Commit authorship

A commit an agent pushes carries `JonEcho <24366590+JonEcho@users.noreply.github.com>`
as its author, set through `git config user.name` / `user.email` before the
commit. `agent-bridge.yml`'s commit-and-push step sets this identity for
every builder-produced commit. `24366590` is Jon's GitHub account id, so the
address links the commit to his account without needing his email.

## What this does not change

Graphite reviewing the pull request is a fact to confirm on each one, not
a property this workflow guarantees; check that the `Graphite / AI Reviews`
check run appears on a pull request before treating it as reviewed. Who
merges a pull request stays what [`merge-policy.md`](merge-policy.md)
states: the driving agent, once its gates pass.
