# Self-closing loop: converge the deferred PRs

Every run leaves work behind. When a round holds only code-standard findings, the
standards-deferral path opens a draft environment-hardening PR and reports it in
`deferredPrs`. That PR is itself a draft that needs to reach ready, and its own
convergence can defer more standard findings, opening more hardening PRs. The
self-closing loop drives that chain to the ground: after teardown, the
orchestrator (the session that launched the workflow) converges the deferred
PRs, then the PRs their runs defer, and so on until a generation opens none.

This loop runs by default at the end of every autoconverge run — single-PR and
multi-PR alike. It stops only when a generation's deferred-PR list comes back
empty.

## Seed the loop

Collect the first generation of deferred PRs from the run that just finished:

- A single-PR run seeds from its `deferredPrs`.
- A multi-PR run seeds from its `allDeferredPrs`.

When the seed list is empty, the loop is already done — the run deferred nothing,
so there is nothing to converge. Report that and stop.

## Each generation

Given a non-empty list of deferred PRs `{ owner, repo, prNumber, copilotDisabled, bugbotDisabled }`
(a generation may span more than one repository — a hardening PR lands in whichever repo owns
the surface that blocks the deferred class, so `JonEcho/llm-settings` for hooks
and `jl-cmd/claude-dev-env` for rules and skills both appear):

1. **Check out each deferred PR.** Run the
   [multi-PR pre-flight](multi-pr.md#multi-pr-pre-flight-main-session) once per
   deferred PR. Because a deferred PR can live in a repo the first run never
   touched, first find a local checkout of that PR's repo; when none exists,
   clone it under the session temp dir, then add the per-PR worktree on the PR's
   head ref. Drop any PR whose strict pre-flight fails rather than stopping the
   whole generation. Grant project permissions once per repository the
   generation spans.
2. **Converge the generation.** Launch `workflow/converge_multi.mjs` with one
   entry per checked-out deferred PR, exactly as the
   [multi-PR launch](multi-pr.md#launch-the-multi-pr-workflow) describes. Each
   child run checks Copilot and Bugbot availability through the workflow's own
   preflight-git probe, carried across rounds, so a reviewer that is down or out
   of quota is never spawned in any generation; the
   `copilotDisabled`/`bugbotDisabled` flags each deferred PR carries seed that
   check for the first round.
3. **Tear down.** Run the [multi-PR teardown](multi-pr.md#multi-pr-teardown-on-workflow-completion)
   over the generation's `results`, and revoke project permissions once per
   repository.
4. **Take the next seed.** The generation's `allDeferredPrs` is the next
   generation's seed list. When it is empty, the loop is done.

Repeat from step 1 with each new seed. The depth is unbounded: the loop keeps
opening generations until one converges every deferred PR without deferring
anything new.

## Report each generation

Log one line as each generation finishes, so a watcher sees the chain close:

```
Self-closing generation <k>: <converged>/<total> deferred PR(s) converged, <new> new deferred PR(s) opened
```

When the loop ends, print a final line naming the generation count and the total
deferred PRs converged across every generation.

## Conventional titles on deferred PRs

Each hardening PR the loop opens targets a repo whose CI validates the PR title
as a Conventional Commit. The commit step's prompt directs the agent to title
the hardening PR as a Conventional Commit — a type prefix, an optional scope,
then a colon and a short summary — so a deferred PR carries a conforming title
(`feat(hooks): …`, `chore(rules): …`) before it exists. That prompt is where the
conforming title is enforced.

The `conventional_pr_title_gate` hook is a best-effort backstop on that title,
not the guarantee. It blocks a `gh pr create` with a non-conforming `--title`
only for a repo whose semantic-pull-request workflow leaves the action's
`types:` input at the default Conventional Commits list. For a repo that pins
its own explicit `types:` list — which the main target repo does in
`.github/workflows/pr-check.yml` — the hook fails open and lets the title
through, and the CI title check on GitHub has the final say.
