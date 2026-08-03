# Sol rung

Detail behind the **Host profiles → Sol rung — any host** section of [`advisor-protocol.md`](../advisor-protocol.md).
Open this when `ADVISOR_SOL_XHIGH` is set and a bind is starting.

## Flag

`ADVISOR_SOL_XHIGH=1` (or `true` / `yes` / `on`) opens the rung, set in the environment or by the consuming skill's invocation.
Flag off: the walk starts at the host's Claude ladder, Fable first.

## Preflight

Flag on: run the Codex preflight first —

```
python ~/.claude/skills/codex-review/scripts/codex_usage_probe.py
```

Repo home: `packages/claude-dev-env/skills/codex-review/scripts/`.

## Branches

**Preflight pass** — exit 0 with `percent_left` above the gate threshold, or null — bind one Codex CLI session at the sol model with xhigh reasoning effort, chartered with the same standing-reviewer contract (ENDORSE / CORRECTION / PLAN / STOP, reply-only).

**Preflight fail** — non-zero exit or an exhausted meter — fall back to the Claude ladder and continue the normal walk.
