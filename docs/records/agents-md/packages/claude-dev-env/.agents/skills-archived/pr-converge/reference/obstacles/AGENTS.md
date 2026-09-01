# pr-converge/reference/obstacles

Per-obstacle runbooks for known failure modes in the `pr-converge` convergence loop. Each file covers one specific obstacle: what causes it, how to detect it, and how to recover.

## Files

| File | Obstacle |
|---|---|
| `fix-post-replies.md` | Posting inline review replies fails or posts to the wrong thread |
| `fix-publish-summary.md` | Publishing the bugteam summary comment fails |
| `fix-push.md` | `git push` fails during a fix commit |
| `fix-read-filelines.md` | Reading file line ranges for a fix fails |
| `fix-reset-state.md` | State JSON becomes corrupt or inconsistent between ticks |
| `fix-resolve-threads.md` | Resolving inline comment threads via GraphQL fails |
| `fix-spawn-clean-coder.md` | Spawning the `clean-coder` subagent fails or produces no output |
| `fix-stage-commit.md` | Staging or committing a fix fails |
| `fix-trigger-bugbot.md` | Triggering Cursor Bugbot via an issue comment fails |
| `fix-write-test.md` | Writing a failing test before a fix fails |

## Conventions

- Each runbook is loaded on demand when the convergence loop hits that specific obstacle.
- Runbooks do not overlap with `per-tick.md`; they cover edge cases and recovery paths that fall outside the normal tick flow.
