# Spawn-walk log

Detail behind the **Model floor** section of [`advisor-protocol.md`](../advisor-protocol.md).

## Record shape

Write the log as JSON with these field names:

- `own_tier`: the consuming session's tier.
- `host_profile`: `Claude`, `Codex`, or `ThirdParty`. Omit to default to `Claude`.
- `candidate_tiers`: on Claude and ThirdParty, Opus, plus Astra when `astra_enabled` is true. On Codex, Astra only.
- `astra_enabled`: a boolean recorded before candidate selection. On Claude and ThirdParty, `true` adds Astra after Opus and `false` walks Opus alone. On Codex this flag does not change the walk.
- `attempts`: one `{tier, result}` entry appended as each bind try happens. `result` is `codex` for an Astra helper bind, `spawned` for an in-session spawn (Claude Agent or Codex native Astra), `cli` for a CLI Claude-chain bind, or a failure reason such as `unavailable`.
- `selected_tier`: the tier of the first successful bind (first `codex`, `spawned`, or `cli` entry), or `null` paired with a `fallback_reason` string when none bound.
- `evidence`: the versioned reference, fallback, and consult record described in `docs/references/advisor-tool.md`. A reference status records optional path repair separately from bind status.

## Log path

Write to a path the session controls, typically `<job-temp-dir>/model-tier-run.json`, or the OS temp directory when no job directory exists.

## Validator

```
python "$HOME/.claude/_shared/advisor/scripts/model_tier_run_validator.py" <path-to-model-tier-run.json>
```

Exit code `0` means every invariant holds.
Exit code `1` means a ladder invariant failed.
Exit code `2` means the path or JSON was unusable.
The same checks are available in-process via `validate_model_tier_run(run)`.

The validator checks ladder shape and validates `evidence` when it is present. On Claude and ThirdParty, Astra is attempted after Opus when `astra_enabled` is enabled, and `selected_tier: "Astra"` requires `result: "codex"`. On Codex, the walk is Astra only, and `result: "spawned"` or `result: "codex"` counts as success. A Codex success record uses `reply_path: "native"` and `advisor_flag: "passed"` or `advisor_flag: "unavailable"`. A missing `advisor_flag` or `advisor_flag: "omitted"` fails validation.
Host policy sits on top of it. See the Model floor section of the protocol.
