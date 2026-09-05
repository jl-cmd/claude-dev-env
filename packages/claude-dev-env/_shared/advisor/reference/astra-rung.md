# Astra rung

Detail behind the **Host profiles → Astra rung** section of [`advisor-protocol.md`](../advisor-protocol.md).
Open this when Fable is out of usage on a Claude or ThirdParty host and an Astra fallback bind is starting.
On a Codex host, Astra is the in-session default; see [`identity.md`](identity.md).

## Flag

`ADVISOR_ASTRA=1` (or `true` / `yes` / `on`) opens the Astra fallback after Fable is out of usage. Two channels exist: set the variable in the helper's process environment, or pass `--enable-astra` on the helper invocation — the CLI flag opens the rung for that run without touching the environment.
Flag off both ways: fail closed when Fable did not bind.
A Windows `setx` write only updates the persisted user environment; only a process started after that write inherits the new value, so an already-running session either sets the flag in its own invoking process environment or passes `--enable-astra`.

## Effort

`ADVISOR_EFFORT` selects Codex `model_reasoning_effort` for Astra and `--effort` for Fable: `low`, `medium`, `high`, `xhigh`, or `max`. The default is `low`, which sends `model_reasoning_effort="low"`. Pass `--effort <level>` on the helper to set effort for that Astra run without changing the environment. An unset or unrecognized value uses `low`.

Every fallback reply carries a `fallback_kind` field: `declined` when policy closed the rung (flag off, usage meter at or below the gate) and `broken` when the Astra path itself failed (missing executable, spawn error, timeout, malformed reply). A `broken` fallback is a defect to report, not a routing outcome.

## Preflight

Flag on: run the Codex preflight first —

```
python ~/.claude/_shared/pr-loop/scripts/codex_usage_probe.py
```

**GOTCHA — probe path:** that installed path is the only one. `codex_astra_advisor.resolve_usage_probe_path` builds `~/.claude/_shared/pr-loop/scripts/codex_usage_probe.py` and stops. Do not hunt `skills/codex-review/`, Codex worktrees under `C:\dev\.codex\worktrees\`, or other copies. Repo home: `packages/claude-dev-env/_shared/pr-loop/scripts/`.

The shared entry point is `~/.claude/_shared/advisor/scripts/codex_astra_advisor.py`; it calls the installed probe and owns Astra bind or resume parsing. Bind with `python ~/.claude/_shared/advisor/scripts/codex_astra_advisor.py --bind --enable-astra --cwd <repo-root>` and pipe the charter on stdin. Resume with `--resume <session_id>` and pipe the delta consult on stdin.

The gate passes only when the probe exits 0, `percent_left` is finite numeric data, and `percent_left` is strictly greater than `WEEKLY_USAGE_GATE_THRESHOLD_PERCENT` from the existing probe. The exact-threshold case fails closed when Fable did not bind.

## Branches

**Preflight pass** — bind one Codex CLI session at `gpt-6-astra` with `model_reasoning_effort` set from `ADVISOR_EFFORT` (default `low`), `--sandbox read-only`, and JSON output. The helper receives the standing-reviewer charter on stdin and returns only parsed ENDORSE / CORRECTION / PLAN / STOP guidance with a session ID.

**Preflight fail** — probe failure, non-zero exit, timeout, missing or malformed usage, `null`, non-finite usage, or usage at or below the threshold fails closed when Fable did not bind.

The helper owns the Astra attempt and returns an explicit fallback result. The consuming advisor path owns the Fable bind. Apply the same gate to every Astra attempt, including resume.
