# logifix/scripts

PowerShell recovery script for the `logifix` skill.

## Key files

| File | Purpose |
|---|---|
| `logifix.ps1` | Restores the LCore tray icon: stops LCore, runs one elevated UAC step (starts `LogiRegistryService`, stops explorer, lets Windows auto-respawn), then re-launches LCore a configurable number of times |

## Conventions

- The script accepts three optional parameters: `-ExplorerAutoRespawnWaitSeconds` (default 5), `-LCoreInitializationWaitSeconds` (default 5), `-LCoreRelaunchAttemptCount` (default 2).
- The full relaunch count always runs — an early-exit on a responsive LCore is intentional behavior per the recovery procedure.
- The elevated block does **not** call `Start-Process explorer`; Windows shell auto-respawn handles that to avoid a duplicate admin-context Explorer.
- Run directly as: `pwsh -File "$HOME\.claude\skills\logifix\scripts\logifix.ps1"`.
