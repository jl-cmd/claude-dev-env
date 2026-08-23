# Sol rung

Detail behind the **Host profiles → Sol rung — any host** section of [`advisor-protocol.md`](../advisor-protocol.md).
Open this when Fable is out of usage and a Sol fallback bind is starting.

## Flag

`ADVISOR_SOL=1` (or `true` / `yes` / `on`) opens the Sol fallback after Fable is out of usage. Two channels exist: set the variable in the helper's process environment, or pass `--enable-sol` on the helper invocation — the CLI flag opens the rung for that run without touching the environment.
Flag off both ways: fail closed when Fable did not bind.
A Windows `setx` write only updates the persisted user environment; only a process started after that write inherits the new value, so an already-running session either sets the flag in its own invoking process environment or passes `--enable-sol`.

## Effort

`ADVISOR_EFFORT` selects Codex `model_reasoning_effort` for Sol and `--effort` for Fable: `low`, `medium`, `high`, `xhigh`, or `max`. The default is `low`, which sends `model_reasoning_effort="low"`. Pass `--effort <level>` on the helper to set effort for that Sol run without changing the environment. An unset or unrecognized value uses `low`.

Every fallback reply carries a `fallback_kind` field: `declined` when policy closed the rung (flag off, usage meter at or below the gate) and `broken` when the Sol path itself failed (missing executable, spawn error, timeout, malformed reply). A `broken` fallback is a defect to report, not a routing outcome.

## Preflight

Flag on: run the Codex preflight first —

```
python ~/.claude/_shared/pr-loop/scripts/codex_usage_probe.py
```

Repo home: `packages/claude-dev-env/_shared/pr-loop/scripts/`.

The shared entry point is `~/.claude/_shared/advisor/scripts/codex_sol_advisor.py`; it calls the installed probe and owns Sol bind or resume parsing. Bind with `python ~/.claude/_shared/advisor/scripts/codex_sol_advisor.py --bind --cwd <repo-root>` and pipe the charter on stdin. Resume with `--resume <session_id>` and pipe the delta consult on stdin.

The gate passes only when the probe exits 0, `percent_left` is finite numeric data, and `percent_left` is strictly greater than `WEEKLY_USAGE_GATE_THRESHOLD_PERCENT` from the existing probe. The exact-threshold case fails closed when Fable did not bind.

## Branches

**Preflight pass** — bind one Codex CLI session at `gpt-5.6-sol` with `model_reasoning_effort` set from `ADVISOR_EFFORT` (default `low`), `--sandbox read-only`, and JSON output. The helper receives the standing-reviewer charter on stdin and returns only parsed ENDORSE / CORRECTION / PLAN / STOP guidance with a session ID.

**Preflight fail** — probe failure, non-zero exit, timeout, missing or malformed usage, `null`, non-finite usage, or usage at or below the threshold fails closed when Fable did not bind.

The helper owns the Sol attempt and returns an explicit fallback result. The consuming advisor path owns the Fable bind. Apply the same gate to every Sol attempt, including resume.
