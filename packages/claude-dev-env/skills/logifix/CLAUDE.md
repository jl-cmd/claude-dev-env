# logifix skill

Restores the Logitech Gaming Software (LCore) tray icon when it disappears on Windows. Runs a PowerShell script that reproduces the verified recovery procedure.

**Trigger:** `/logifix`, "logitech tray icon missing", "LCore tray gone", "logitech is not loaded".

## Key files

| File | Purpose |
|---|---|
| `SKILL.md` | Full procedure description, invocation options, fallback steps |
| `scripts/logifix.ps1` | PowerShell script that runs the recovery procedure |

## Subdirectories

| Directory | Role |
|---|---|
| `scripts/` | The PowerShell recovery script |

## What the script does

1. Takes a state snapshot (Explorer instances, Logitech services, LCore process).
2. Stops LCore in user context.
3. Runs one elevated UAC step: starts `LogiRegistryService`, stops `explorer.exe`, and lets Windows shell auto-respawn rebuild it (does **not** call `Start-Process explorer` from the elevated block).
4. Waits for shell auto-respawn (default 5 seconds).
5. Confirms exactly one Explorer in the user's session.
6. Runs `LCoreRelaunchAttemptCount` full stop-then-launch cycles of `LCore.exe /minimized` (default 2). Always runs the full count.
7. Takes a final state snapshot.

## Invocation

```
/logifix
```

Optional parameters: `-ExplorerAutoRespawnWaitSeconds`, `-LCoreInitializationWaitSeconds`, `-LCoreRelaunchAttemptCount`.
