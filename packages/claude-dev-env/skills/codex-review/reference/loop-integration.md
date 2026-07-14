# Loop integration

How `codex-review` plugs into PR-loop orchestrators and standalone runs.

## Target selection

| Caller context | Target |
|---|---|
| PR loop (`pr-converge`, `autoconverge`, `bugteam`, or an open PR on the branch) | Diff against the PR base branch (`--base`) |
| Standalone (no PR) | Uncommitted work via `--uncommitted` (staged + unstaged + untracked) |

## Classification vocabulary

Orchestrators re-enter on the skill-level classes from `SKILL.md` Step 4. CLI failures map through `codex_down` in [cli-contract.md](cli-contract.md).

| Skill class | CLI observation | Orchestrator next step |
|---|---|---|
| `down` | `codex_down` / probe miss | Mark the Codex gate skipped or stop per the caller's policy |
| `clean` | Success stream, no finding bullets | End the Codex gate |
| `findings` | Success stream with finding bullets | Re-enter `pr-fix-protocol` |

## Findings handoff

When classification is `findings`, the skill invokes `pr-fix-protocol` by name with the findings payload, PR scope, and worktree path. The fix protocol owns test-first fixes, commit, push, and reply-and-resolve.

## Re-entry after a fix

Orchestrators that keep looping after a push:

1. Re-resolve current HEAD.
2. Re-run the classifying path (`codex exec … review --json`) against the same target class (base branch vs `--uncommitted`).
3. Re-classify with the table above.
