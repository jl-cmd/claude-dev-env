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

## Orchestrator state fields

PR-loop state (`pr-converge-state.json` under `$CLAUDE_JOB_DIR`) carries:

| Field | Role |
|---|---|
| `codex_clean_at` | HEAD SHA where the last Codex pass reported clean (no findings) |
| `codex_down` | Sticky boolean: true when Codex is down or opted out for this run |

`check_convergence.py` honors both: a matching `codex_clean_at` passes the conditional Codex gate; sticky `codex_down` (or `--codex-down` / `CLAUDE_REVIEWS_DISABLED=codex`) bypasses it. Full gate rules live in `pr-converge/reference/convergence-gates.md` and `pr-converge/reference/state-schema.md`.
