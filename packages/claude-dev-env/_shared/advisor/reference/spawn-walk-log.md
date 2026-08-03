# Spawn-walk log

Detail behind the **Model floor** section of [`advisor-protocol.md`](../advisor-protocol.md).
The log makes the bind walk checkable mechanically.

## Record shape

Write the log as JSON with these field names:

- `own_tier` — the floor tier.
- `candidate_tiers` — the ladder slice down to that floor.
- `attempts` — one `{tier, result}` entry appended as each bind try happens; `result` is `spawned` for a Claude Agent spawn, `cli` for a CLI Claude-chain bind, or a failure reason such as `unavailable`.
- `selected_tier` — the tier of the first successful bind (first `spawned` or `cli` entry), or `null` paired with a `fallback_reason` string when none bound.

## Log path

Write to a path the session controls — typically `<job-temp-dir>/model-tier-run.json`, or the OS temp directory when no job directory exists.

## Validator

```
python "$HOME/.claude/_shared/advisor/scripts/model_tier_run_validator.py" <path-to-model-tier-run.json>
```

Exit code `0` means every invariant holds.
Exit code `1` means a ladder invariant failed.
Exit code `2` means the path or JSON was unusable.
The same checks are available in-process via `validate_model_tier_run(run)`.

The validator checks ladder shape only: the candidate slice, the order of bind tries, and the success-token rules per tier.
Host policy sits on top of it — see the Model floor section of the protocol.
