# AHK auto-continue loop pacing (pr-converge)

Load this document when **`ScheduleWakeup` is not available** in this session (orchestrated teams disabled, restricted tool registry, Cursor
  without that primitive, or the user wants a visibly-running pacer). Follow it for **every** instruction below that depends on that choice.
  Shared bugbot / bugteam / Fix protocol steps stay in the main `SKILL.md`.

## Session behavior

Keep ticks in the **same** window the auto-typer targets so each `continue` re-enters here and reads the same state line and `gh` context.

## Why this path exists

It is not a separate "mode" the user must remember — bare `/pr-converge` already implies loop-until-done; when the primary wakeup tool is
  missing, fall through to AHK automatically. The per-tick work is unchanged; what changes is who fires the next tick. Instead of
  `ScheduleWakeup` re-entering the skill, an external AutoHotkey utility auto-types `continue` into the active Claude Code window every 5
  minutes, and the model treats each `continue` as the next tick trigger.

**AHK is loop pacing only:** every `phase == BUGTEAM` tick still runs **`/bugteam`** via the bugteam skill per Step 2 of the main skill —
  nothing here replaces that audit.

**Fix protocol** commits use **`Task`** with **`subagent_type: "generalPurpose"`** and the **clean-coder preamble** from the main
  [`SKILL.md` Fix protocol](../SKILL.md#fix-protocol) section (same as ScheduleWakeup pacing — Cursor has no `clean-coder` `subagent_type`).

Ensure `~/.claude/agents/clean-coder.md` exists (Windows: `%USERPROFILE%\.claude\agents\clean-coder.md`). Optionally also copy it to
  `.cursor/agents/clean-coder.md` in the repo when you want the file co-located with the checkout; the spawn **prompt** must still name the
  absolute path the subagent should **Read** first.

### One-time setup at the start of the loop

The skill bundles its driver scripts under `scripts/` and resolves them at runtime via `$HOME\.claude\skills\pr-converge\scripts\…` (the same
  convention `/logifix` uses). The bundled `.cmd` launchers locate their siblings via `%~dp0`, so they need no path arguments — only the AHK
  target PID.

Run these two commands in order (PowerShell-friendly Bash escaping):

1. Resolve the PID of the GUI ancestor that hosts this Claude Code session:
   ```bash
   pwsh -NoProfile -ExecutionPolicy Bypass -File "$HOME\.claude\skills\pr-converge\scripts\caller-window-pid.ps1"
   ```
   Capture the printed integer as `caller_pid`. Verify it points at the right window before continuing:
   ```bash
   pwsh -NoProfile -Command "Get-Process -Id $caller_pid | Select-Object Id,ProcessName,MainWindowTitle"
   ```
2. Launch the auto-typer attached to that PID with auto-start enabled. The bundled launcher accepts the PID as its first arg and the
  `--start-on` flag is forwarded to the AHK script:
   ```bash
   "$HOME\.claude\skills\pr-converge\scripts\cursor-agents-continue.cmd" $caller_pid --start-on
   ```
   AutoHotkey v2 must be installed at `C:\Program Files\AutoHotkey\v2\AutoHotkey64.exe`.

### Per-tick behavior under this driver

- Run Steps 1–3 of **Per-tick work** in the main `SKILL.md` exactly as written.
- In **Step 4**, do **not** call `ScheduleWakeup` — the auto-typer is the pacer (this is the fallback branch of Step 4 in the main skill).
- End every assistant response with the literal sentence `Awaiting next "continue" tick.` so the next iteration is unambiguously identifiable
  in the transcript.
- When the next user message is `continue` (auto-typed by AHK) or any close paraphrase, treat it as the next tick of default-loop
  `/pr-converge` and re-enter from Step 1 against the freshest PR state.

### Convergence cleanup

On back-to-back clean (the existing convergence rule in the main skill), run `gh pr ready`, then kill the auto-typer when this session used
  this AHK pacing path:

```bash
pwsh -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='AutoHotkey64.exe'\" | Where-Object CommandLine -like '*cursor-agents-continue.ahk*' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
```

Report convergence in the same one-sentence shape as the standard flow, plus a second sentence noting the auto-typer was stopped. The skill
  returns; no next tick fires.

### Gotchas

- **Resolver fallback semantics matter.** `caller-window-pid.ps1` walks up the parent process chain, terminates at `explorer.exe`, and falls
  back to the foreground window when no GUI ancestor is found. Always verify `MainWindowTitle` after capture — if it isn't the Claude Code
  session, the auto-typer will fire `continue` into the wrong window and the loop stalls silently.
- **Tick-duration vs. 5-minute cadence.** The auto-typer fires every 5 minutes regardless of model activity. A tick that runs longer than 5
  minutes will receive a queued `continue` while still in flight; Claude Code processes these sequentially, so there's no corruption, but the
  loop pace becomes irregular. Don't try to "fix" this by shortening the AHK interval — the `bugbot run` cadence already has its own pacing
  baked into the standard flow.
- **AHK runs as `#SingleInstance Force`.** Re-running the launcher replaces the prior instance silently. Safe to re-issue if the loop appears
  stalled.
- **`Stop-Process -Force` on `AutoHotkey64` is broad.** It kills every AHK instance, not just the one this skill started. When the user has
  unrelated AHK utilities running, scope the kill by command-line match instead:
  ```bash
  pwsh -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='AutoHotkey64.exe'\" | Where-Object CommandLine -like '*cursor-agents-continue.ahk*' | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
  ```
- **State-line responsibility is unchanged.** The state line (phase, bugbot_clean_at, inline_lag_streak, tick_count) is still emitted at the
  end of every tick — it's how the next tick reads prior state. The auto-typer only fires `continue`; it does not preserve state for you.
- **No `tick_count` ceiling.** `tick_count` is observability-only (same as the main skill and `state-schema.md`). This path ends on convergence or **Stop conditions** in `SKILL.md`, not on a tick counter.
- **`/bugteam` is not optional for BUGTEAM ticks.** AHK only paces **when** the next tick runs; it does not replace the bugteam skill. Skipping
  **`/bugteam`** after a clean Bugbot review breaks the back-to-back contract.
- **Fix protocol:** use **`Task` + `generalPurpose`** with the clean-coder **Read** preamble from the main [`SKILL.md` Fix protocol](../SKILL.md#fix-protocol)
  (never a bare `generalPurpose` production edit). Ensure the clean-coder agent markdown exists at `~/.claude/agents/clean-coder.md` (Windows:
  `%USERPROFILE%\.claude\agents\clean-coder.md`); copy into `.cursor/agents/` only if you want a repo-local duplicate.

## BUGBOT inline-lag (this path only)

When Step 2 BUGBOT branch c routes to API lag and you are on **this** pacing path: complete Step 4 per **Per-tick behavior under this driver**
  above (fixed AHK cadence — there is no 60s shortcut). The inline comments should appear on the next tick.

## Convergence

On back-to-back clean: stop the auto-typer per **Convergence cleanup** above; omit `ScheduleWakeup` (not used on this path).

## Stop / safety (this path)

On hard blockers or user stop: omit loop pacing and stop the AHK auto-typer if it was started, per main skill **Stop conditions**. Use the same **scoped** `Get-CimInstance` / `Stop-Process` command as **Convergence cleanup** (command-line match on `cursor-agents-continue.ahk`) so unrelated AutoHotkey instances are not killed.
