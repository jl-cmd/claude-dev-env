# Verified-Commit-Gate Skip Marker

**When this applies:** A `git commit` or `git push` through the Bash tool is blocked by the `verified_commit_gate` hook.

## The marker

Appending the comment `# verify-skip` as a trailing shell comment to the Bash command exempts that single commit or push from the gate. The hook (`hooks/blocking/verified_commit_gate.py`, marker constant `VERIFICATION_BYPASS_MARKER`) recognizes the marker only when its leading `#` sits at a word boundary and outside every quoted region — a genuine comment, not a data-only mention inside a quoted commit message or `gh` body — and lets the command run without a minted verdict.

## When the marker is allowed

Use it only when both hold:

1. The gate is blocking the command, and
2. The branch surface content is the same code a `code-verifier` already passed clean — nothing effectively changed since that clean verdict.

That situation arises when the verdict fails to cover the current surface even though the code is the same: a clean verdict that never minted (the verifier's fenced block ran in a resumed turn, so the SubagentStop minter never fired), a surface hash perturbed by index-only staging churn, or a concurrent worktree write that was fully reverted back to the verified content. Before using the marker, confirm the match yourself: the test suite the verifier ran still passes, and the diff holds no content beyond what the clean verdict covered.

## When the marker is not allowed

Every other case runs the verification: spawn the `code-verifier` agent — `model: sonnet`, worker-model routing per [`skills/orchestrator/SKILL.md`](../skills/orchestrator/SKILL.md#workflow-agent-routing); resolver-supplied sonnet-equivalent on third-party hosts — and let the SubagentStop hook mint the verdict. In particular, never use the marker to:

- Skip a branch's first verification.
- Commit or push after any real code change since the last clean verdict — one changed line means a fresh verification.
- Work around a verifier that reported findings; findings get repaired and re-verified.

## One command, one exemption

The marker exempts only the command that carries it. The next commit or push on the branch faces the gate again, so a follow-up change still verifies before it lands.
