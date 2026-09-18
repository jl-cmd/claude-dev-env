# CI Owns the Gate

**When this applies:** Before pushing a branch, and any time you are about to
run a repository's full check suite or policy gate on your own machine to
predict what CI will say.

## Rule

CI is the gate. Push, and read its verdict. Do not run the whole suite,
`local_verify.py`, or a policy lint such as `cde_preflight.py` as a rehearsal of
the checks CI is about to run anyway.

The inner development loop is untouched. Run the single test you are writing, as
often as you like. That is how the change gets built. What this rule stops is
the second full pass whose only purpose is to guess the verdict.

## Why

**A local green often proves nothing.** A policy gate is pinned. The workflow
names an exact revision of the policy package, and that revision decides which
rules run. The copy installed under your home directory is a different artifact
at an unknown revision. A local run pointed at the home copy exits zero while
certifying nothing, and an exit code reported as a pass is a false green nobody
goes back to check. Reach for the pinned revision or do not reach at all.

**Self-hosted runners may share your machine.** Where the runners execute on the
same host as your shell, a local suite run does not borrow idle capacity from
somewhere else. It takes processor time from the runners it was meant to
protect, and it does so exactly while they work on the branch you just pushed.
Read where the runners live before assuming a local run is free.

**Running it twice does not make it truer.** The second pass reaches the same
verdict from the same inputs, or it disagrees because the two environments
differ, in which case CI is the one that counts.

## The narrow exception

Run a gate locally only when you first clone the revision the workflow pins and
point the gate at that clone. That run answers the same question CI answers.
Anything else answers a different question and must not be reported as a pass.

## No self-attestation

Do not add, and do not accept, a flag, trailer, receipt, or environment variable
by which the thing being tested tells CI that it already passed. A gate whose
subject supplies the verdict is not a gate. Signing the claim does not rescue it
where the runners and the agent share one host, because there is no second party
to the signature.

A cache CI keys and verifies by itself is a different design and is allowed. The
distinction is who computes the key. CI deriving a key from the tree it is about
to test is a cache. An agent handing CI a claim is a bypass.

## Sibling rules

| Rule | Role |
|---|---|
| [`git-workflow.md`](git-workflow.md) | Confirm each required context fired after the push |
| [`verify-runtime-state.md`](verify-runtime-state.md) | A status field is a report, not the effect |
| [`falsify-before-green.md`](falsify-before-green.md) | A green counts as evidence only after the check ran red on a deliberate break |
