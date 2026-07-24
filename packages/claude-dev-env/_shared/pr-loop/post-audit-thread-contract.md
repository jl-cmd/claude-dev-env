# post_audit_thread.py invocation contract

Single source of truth for how every PR-loop caller runs
[`scripts/post_audit_thread.py`](scripts/post_audit_thread.py) to post one
audit review per pass. It reads its body skeleton
from [`audit-reply-template.md`](audit-reply-template.md) at runtime.

## Event mapping

| State | Review event | Inline comments |
|---|---|---|
| `CLEAN` | `APPROVE` | none (empty findings list) |
| `DIRTY` | `REQUEST_CHANGES` | one inline anchored comment per finding |
| Self-PR, no alternate reviewer account | `COMMENT` | CLEAN posts none; DIRTY keeps one per finding |

When the author reviews their own PR and no alternate reviewer account is
configured, GitHub rejects a self-approval, so the event downgrades to
`COMMENT`: CLEAN's `APPROVE` and DIRTY's `REQUEST_CHANGES` both become
`COMMENT`, and the review body ends with an appended transport disclosure. A
self-PR with an alternate reviewer account posts the `APPROVE` or
`REQUEST_CHANGES` review with no downgrade.

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
| `0` | Review posted. Line 1 of stdout is the new review's `html_url`; on a self-PR downgrade a second line marks the `COMMENT` downgrade. |
| `1` | User input error: bad arguments, malformed findings JSON, or a missing template. |
| `2` | Retry exhaustion: every try failed. |

## Stdout

On exit `0`, the first stdout line is always the posted review's `html_url`. A
self-PR downgrade to `COMMENT` prints a second line: a plain marker naming the
downgrade. A non-downgrade post is one line; a downgrade post is two.

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
  policy: [`../../skills/autoconverge/reference/stop-conditions.md`](../../skills/autoconverge/reference/stop-conditions.md)
  § "Clean-audit post bypassed".
