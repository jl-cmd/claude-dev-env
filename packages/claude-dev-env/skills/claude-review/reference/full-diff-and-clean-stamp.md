# Full-diff rule and clean-stamp contract

## Contents

- [Full-diff rule](#full-diff-rule)
- [Usage probe (pre-step)](#usage-probe-pre-step)
- [Invoker JSON shape](#invoker-json-shape)
- [Successful serve](#successful-serve)
- [Clean stamp](#clean-stamp)
- [Clean PR issue comment](#clean-pr-issue-comment)
- [Caller phase machine](#caller-phase-machine)

## Full-diff rule

Every claude-review pass audits the full `origin/main...HEAD` diff — every file
the branch touches. Do not:

- Delta-scope to commits after a prior clean SHA
- Scope to a single file
- Scope to bugbot-flagged paths only

A partial-scope round does not count and cannot set `code_review_clean_at`.

Run with no path arguments so the built-in command sees the whole branch diff
against `origin/main` (see Claude Code local diff review docs).

## Usage probe (pre-step)

`claude_usage_probe.py` prints one JSON object:

| Key | Type | Meaning |
|---|---|---|
| `session_utilization` | number or null | 5-hour percent spent |
| `weekly_utilization` | number or null | Weekly percent spent |
| `weekly_near_cap` | bool or null | Weekly WARN flag from usage-pause |
| `session_has_usage_left` | bool or null | True when the session meter is known and below threshold |
| `source` | string | Resolver source, or `unavailable` |
| `probe_ok` | bool | True only when the usage-pause resolver succeeded |

Callers may pass the decision as `--session-has-usage-left true|false|unknown`.
When the flag is omitted or `unknown`, `invoke_code_review.py` auto-runs the
probe and maps `session_has_usage_left` into the mode choice. Explicit
`true`/`false` skip the auto-probe. `false` forces `mode=chain` even on
Claude+opus. Probe failure does not block the review.

## Invoker JSON shape

`invoke_code_review.py` prints one JSON object on stdout only:

| Key | Type | Meaning |
|---|---|---|
| `mode` | string | `in_session` or `chain` |
| `served_command` | string or null | Chain binary that served, or null |
| `returncode` | int | Process return code (`0` for in-session handoff) |
| `dirty_tree` | bool | Working tree dirty after chain (or equivalent after in-session) |

On `ChainConfigurationError` or host `ValueError`, the helper still prints this
shape (non-zero `returncode`, null `served_command`) and exits non-zero — never
a traceback-only failure. The invoker outcome keys stay fixed; usage-probe
fields stay on the separate probe CLI.

## Successful serve

A successful serve requires:

- `returncode == 0`
- When `mode == chain`: `served_command` is non-null

In-session mode hands the slash command to the skill, so `served_command` stays
null by design and still counts as a successful handoff when `returncode == 0`.

Package helpers:

- `is_successful_code_review(outcome)`
- `is_code_review_clean_stamp_allowed(outcome)`

## Clean stamp

A clean stamp (`code_review_clean_at = current_head` for converge callers)
requires **both**:

1. Successful serve (above)
2. `dirty_tree` false (and empty porcelain after in-session)

| Situation | Stamp clean? |
|---|---|
| Chain success, clean tree | Yes |
| Chain success, dirty tree | No — fixes applied |
| Chain failure, clean tree | **No** — failed serve |
| In-session handoff, then slash fails | No |
| In-session handoff, slash ok, dirty porcelain | No — fixes applied |
| In-session handoff, slash ok, clean porcelain | Yes |

## Clean PR issue comment

After a clean stamp (or a standalone clean outcome), post one PR **issue
comment** (not a review thread) via the clean-comment poster:

```bash
python "$HOME/.claude/scripts/post_claude_review_clean_comment.py" \
  --cwd <PR-worktree> --head-sha <sha> [--mode ...] [--served-command ...] \
  [--effort ...]
```

Body starts with `## claude-review CLEAN` and includes `head_sha`, the review
prompt built from `--effort`, and mode / served_command when known. Named
tokens live in
`dev_env_scripts_constants/post_claude_review_clean_comment_constants.py`.

- **Idempotent:** same marker + same `head_sha` line → skip repost.
- **Fails closed on an empty `--head-sha`:** an explicitly empty value never
  falls back to live git HEAD, so no comment stamps a SHA no review covered.
- **Served command is a bare name:** only the final path segment reaches the
  comment body.
- **Soft-fail:** helper always exits `0`; `posted=false` never undoes the stamp.
- Portable `after-code-review` emits this argv in `commands` on the clean path.

## Caller phase machine

This skill does not own converge phase fields. Callers (pr-converge CODE_REVIEW,
portable autoconverge) keep:

- Failed review → stay CODE_REVIEW, no stamp
- Dirty tree → fix protocol, push, reset `*_clean_at`, re-enter CODE_REVIEW
- Clean → set `code_review_clean_at`, emit clean-comment command, advance phase

See [`../../pr-converge/reference/per-tick.md`](../../pr-converge/reference/per-tick.md)
for the tick state machine.
