# Loop integration

Stable home for how `codex-review` plugs into PR-loop orchestrators and standalone runs.

## Target selection

| Caller context | Target |
|---|---|
| PR loop (`pr-converge`, `autoconverge`, `bugteam`, or an open PR on the branch) | Diff against the PR base branch |
| Standalone (no PR) | Uncommitted work (staged and unstaged) per the wrapper contract |

## Findings handoff

When classification is `findings`, the skill invokes `pr-fix-protocol` by name with the findings payload, PR scope, and worktree path. The fix protocol owns test-first fixes, commit, push, and reply-and-resolve.

## Re-entry after a fix

Orchestrators that keep looping after a push:

1. Re-resolve current HEAD.
2. Re-run the Codex wrapper against the same target class (base branch vs uncommitted).
3. Re-classify. `clean` ends the Codex gate; `findings` re-enters the fix protocol; `down` marks the Codex gate skipped or stops per the caller's policy.

Exact orchestrator parameter names and state fields for a Codex clean-SHA belong in this page when the loop-integration child fills them in.
