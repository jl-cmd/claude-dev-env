# post_audit_thread.py invocation contract

Single source of truth for how every PR-loop caller runs
[`scripts/post_audit_thread.py`](scripts/post_audit_thread.py) to post one
audit review per pass. The script posts an `APPROVE` review on `CLEAN` (an
empty findings list, zero inline comments) and a `REQUEST_CHANGES` review on
`DIRTY` (one inline anchored comment per finding). It reads its body skeleton
from [`audit-reply-template.md`](audit-reply-template.md) at runtime.

## Invocation

```
python "<pr-loop-scripts>/post_audit_thread.py" \
  --skill <caller> \
  --owner <owner> \
  --repo <repo> \
  --pr-number <N> \
  --commit <head_sha> \
  --state <CLEAN|DIRTY> \
  --findings-json <path>
```

Capture `<head_sha>` with `git rev-parse HEAD` in the caller's cwd right before
the call, so the review attaches to the commit the audit scoped. `--findings-json`
points to a JSON file whose root is a list; on `CLEAN` the list is empty (`[]`).

## Exit codes

The script retries on its own with 1s / 4s / 16s backoff across four tries (one
plus three retries). It then exits:

| Exit | Meaning |
|---|---|
| `0` | Review posted. The new review's `html_url` is on stdout. |
| `1` | User input error: bad arguments, malformed findings JSON, or a missing template. |
| `2` | Retry exhaustion: every try failed. |

## Per-caller policy

The same exit codes carry different weight per caller:

- **bugteam** — an exit `2` is a hard blocker. The lead exits with
  `error: post_audit_thread retry exhausted`, and does not retry or fall back to
  a flat issue comment.
- **autoconverge clean-audit** — any post that does not land (a denied post, an
  error, or an agent that never ran) is a recorded bypass, not a blocker. Every
  review lens already cleared the HEAD, so the CLEAN post is a record-keeping
  artifact. The run records a bypass note, sets the convergence check's
  `--bugteam-post-blocked` flag, and proceeds to the terminal Bugbot gate. Full
  policy: [`../../autoconverge/reference/stop-conditions.md`](../../autoconverge/reference/stop-conditions.md)
  § "Clean-audit post bypassed".
