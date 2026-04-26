---
name: logifix
description: Restore the Logitech Gaming Software (LCore) tray icon when it disappears on Windows. Calls a PowerShell script that reproduces the verified Session 2 recovery procedure from 2026-04-25. Triggers on "logifix", "/logifix", "logitech tray icon missing", "LCore tray gone", "logitech is not loaded".
---

# logifix

## Overview

Restore the Logitech Gaming Software (LCore) tray icon by reproducing the verified recovery procedure documented in `sessions/System Support/2. Logitech Tray Icon Fix Recurrence.md`.

**Announce at start:** "Running /logifix to restore the LCore tray icon."

## What the script does

`scripts/logifix.ps1` runs this sequence (verified during Session 2 on 2026-04-25):

1. **State snapshot.** Explorer instances per session, Logitech services state, LCore process state.
2. **Stop LCore in user context.** `Stop-Process -Name LCore -Force`.
3. **Single elevated UAC step:**
   - `Start-Service -Name LogiRegistryService` (handles the recurrence case where the service is Stopped).
   - `Stop-Process -Name explorer -Force`.
   - **Does NOT** call `Start-Process explorer` from inside the elevated block. Windows shell auto-respawn handles the user-session explorer cleanly. Skipping this line is the operative fix discovered in Session 2 — including it created a duplicate admin-context `explorer.exe` (no resolvable owner, parent = the admin pwsh) that blocked LCore tray registration.
4. **Wait for Windows shell auto-respawn** (default 5 seconds).
5. **Verify exactly one explorer in the user's session.**
6. **Perform `LCoreRelaunchAttemptCount` full stop-then-launch cycles of `LCore.exe /minimized`** (default 2). The full count always runs — a responsive LCore on the first attempt does NOT imply the tray icon registered. Per Session 2 gotcha #2, the first relaunch can leave LCore responsive with no tray icon; only a second stop+launch reliably triggers `Shell_NotifyIcon` registration.
7. **Final state snapshot.**

## Invocation

From Claude Code:

```
/logifix
```

Direct PowerShell:

```
pwsh -File "$HOME\.claude\skills\logifix\scripts\logifix.ps1"
```

Optional parameters (all have safe defaults):

- `-ExplorerAutoRespawnWaitSeconds <int>` — wait after the elevated kill (default 5).
- `-LCoreInitializationWaitSeconds <int>` — wait after each LCore relaunch before checking responsiveness (default 5).
- `-LCoreRelaunchAttemptCount <int>` — number of LCore stop+launch cycles to perform (default 2). Always runs the full count.

## When to use

- LCore tray icon missing (also confirmed absent from the overflow `^` chevron).
- LCore process is running but the tray icon never appears.
- After resume from sleep, system restart, or a Logitech service crash that leaves LCore in a half-loaded state.

## Fallback (if the script does not restore the icon)

If `/logifix` reports that UAC was canceled, or LCore is still not responding after both relaunch cycles:

1. **Ctrl+Shift+Esc** → Task Manager.
2. Find **Windows Explorer** → right-click → **Restart**.
3. Re-run `/logifix`.

The Task Manager restart path is guaranteed to hit the correct interactive session and elevation context regardless of how the calling shell was launched. In Session 2, elevated calls from Claude Code's PowerShell tool could not be confirmed to reach the user's interactive Session 1 — Task Manager bypasses that ambiguity.

## Source

Procedure verified during Session 2 (Logitech Tray Icon Fix Recurrence), 2026-04-25. The session log lists the verified command set, the gotcha catalog, and the final process/service state.

The "always run the full relaunch count" behavior was added on 2026-04-26 after `/logifix` reported success on the first responsive attempt but the tray icon never appeared — the original early-break optimization conflicted with documented Session 2 gotcha #2 (responsive LCore, no tray icon).
