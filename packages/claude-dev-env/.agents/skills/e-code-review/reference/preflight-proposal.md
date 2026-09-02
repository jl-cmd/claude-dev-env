# Review preflight proposal mode

Apply the canonical proposal contract at:

```text
@~/.claude/_shared/pr-loop/preflight-proposal.md
```

Use this review extension when the caller selects `preflight-proposal`:

```text
/e-code-review preflight-proposal <pr_number> --level low --base-sha <base_sha> --head-sha <head_sha> --worktree <isolated_worktree>
```

## Review extension

The caller resolves the review level before invocation and always passes `--level`. Use this mapping:

| Caller selection | Resolved `--level` |
|---|---|
| Omitted override | `low` |
| `low` | `low` |
| `medium` | `medium` |
| `xhigh` | `xhigh` |

The `review_level` evidence mirrors the resolved `--level` value.

Run the selected level as `<review_level> --fix loop`. The selected level owns its normal finding and fix rules. Require `HEAD` to equal the supplied head SHA before each round.

Keep Gate 1, Gate 2, the bare code-rules gate, and exact required tests. Extend the canonical evidence record with:

```yaml
review_level: low | medium | xhigh
findings:
  - severity: blocker | high | medium | low | nit
    verdict: CONFIRMED | PLAUSIBLE
    outcome: fixed | no_change_needed | skipped
```

The canonical contract owns the immutable range, worktree boundary, proposal identity, changed paths, exact tests and outcomes, mutation boundary, and downstream selection.
