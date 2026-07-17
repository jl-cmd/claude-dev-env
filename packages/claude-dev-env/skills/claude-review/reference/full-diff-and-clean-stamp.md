# Full-diff rule and clean-stamp contract

## Contents

- [Full-diff rule](#full-diff-rule)
- [Invoker JSON shape](#invoker-json-shape)
- [Successful serve](#successful-serve)
- [Clean stamp](#clean-stamp)
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
a traceback-only failure.

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

## Caller phase machine

This skill does not own converge phase fields. Callers (pr-converge CODE_REVIEW,
portable autoconverge) keep:

- Failed review → stay CODE_REVIEW, no stamp
- Dirty tree → fix protocol, push, reset `*_clean_at`, re-enter CODE_REVIEW
- Clean → set `code_review_clean_at`, advance phase

See [`../../pr-converge/reference/per-tick.md`](../../pr-converge/reference/per-tick.md)
for the tick state machine.
