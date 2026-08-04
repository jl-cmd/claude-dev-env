# Sol rung

Detail behind the **Host profiles → Sol rung — any host** section of [`advisor-protocol.md`](../advisor-protocol.md).
Open this when `ADVISOR_SOL_XHIGH` is set and a bind is starting.

## Flag

`ADVISOR_SOL_XHIGH=1` (or `true` / `yes` / `on`) opens the rung, set in the environment or by the consuming skill's invocation.
Flag off: the walk starts at the host's Claude ladder, Fable first.
A Windows `setx` write only updates the persisted user environment; only a process started after that write inherits the new value, so an already-running session needs the flag set directly in its own invoking process environment.

## Preflight

Flag on: run the Codex preflight first —

```
python ~/.claude/skills/codex-review/scripts/codex_usage_probe.py
```

Repo home: `packages/claude-dev-env/skills/codex-review/scripts/`.

The shared entry point is `~/.claude/_shared/advisor/scripts/codex_sol_advisor.py`; it calls the installed probe and owns Sol bind or resume parsing. Bind with `python ~/.claude/_shared/advisor/scripts/codex_sol_advisor.py --bind --cwd <repo-root>` and pipe the charter on stdin. Resume with `--resume <session_id>` and pipe the delta consult on stdin.

The gate passes only when the probe exits 0, `percent_left` is finite numeric data, and `percent_left` is strictly greater than `WEEKLY_USAGE_GATE_THRESHOLD_PERCENT` from the existing probe. The exact-threshold case selects Fable.

## Branches

**Preflight pass** — bind one Codex CLI session at `gpt-5.6-sol` with `model_reasoning_effort="xhigh"`, `--sandbox read-only`, and JSON output. The helper receives the standing-reviewer charter on stdin and returns only parsed ENDORSE / CORRECTION / PLAN / STOP guidance with a session ID.

**Preflight fail** — probe failure, non-zero exit, timeout, missing or malformed usage, `null`, non-finite usage, or usage at or below the threshold selects Fable and continues the normal walk.

The helper owns the Sol attempt and returns an explicit fallback result. The consuming advisor path owns the Fable bind. Apply the same gate to every Sol attempt, including resume.
