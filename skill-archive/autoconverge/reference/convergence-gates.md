# Convergence gates — printed labels

`check_convergence.py` in `packages/claude-dev-env/_shared/pr-loop/scripts/`
re-derives every readiness condition from GitHub and prints one numbered
PASS/FAIL line per gate. When Bugbot is down, the bugbot review-body gate is
omitted from the numbered list.

## Exact printed labels (script order)

When every gate is required and passes:

1. `bugbot_clean_at == current_head`
2. `bugbot review body clean` (omitted when Bugbot is down)
3. `bugteam_clean_at == current_head`
4. `copilot_clean_at == current_head`
5. `codex_clean_at == current_head`
6. `zero unresolved bot threads`
7. `PR is mergeable`
8. `no pending requested reviews`

Success ends with:

```
All pre-conditions met — PR is ready to mark ready.
```

Failure ends with:

```
One or more pre-conditions not met — do not mark ready.
```
