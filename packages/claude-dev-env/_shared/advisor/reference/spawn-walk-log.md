# Spawn-walk log

Detail behind the **Model floor** section of [`advisor-protocol.md`](../advisor-protocol.md).

## Record shape

Write the log as JSON with these field names:

- `own_tier` — the consuming session's tier (recorded; it does not add Opus to the advisor walk).
- `host_profile` — `Claude`, `Codex`, or `ThirdParty`. Omit to default to `Claude`.
- `candidate_tiers` — on Claude and ThirdParty, Fable, plus Sol when `sol_enabled` is true. On Codex, Sol only.
- `sol_enabled` — a boolean recorded before candidate selection; on Claude and ThirdParty, `true` adds Sol after Fable and `false` walks Fable alone. On Codex this flag does not change the walk.
- `attempts` — one `{tier, result}` entry appended as each bind try happens; `result` is `codex` for a Sol helper bind, `spawned` for an in-session spawn (Claude Agent or Codex native Sol), `cli` for a CLI Claude-chain bind, or a failure reason such as `unavailable`.
- `selected_tier` — the tier of the first successful bind (first `codex`, `spawned`, or `cli` entry), or `null` paired with a `fallback_reason` string when none bound.

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

The validator checks ladder shape only: the candidate slice, the order of bind tries, and the success-token rules per tier and host. On Claude and ThirdParty, Sol is attempted after Fable when `sol_enabled` is true, and `selected_tier: "Sol"` requires `result: "codex"`. On Codex, the walk is Sol only, and `result: "spawned"` or `result: "codex"` counts as success.
Host policy sits on top of it — see the Model floor section of the protocol.
