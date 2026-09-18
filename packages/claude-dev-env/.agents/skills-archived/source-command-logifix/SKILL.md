---
name: "source-command-logifix"
description: "Restore the Logitech Gaming Software (LCore) tray icon when it disappears on Windows"
---

# source-command-logifix

Use this skill when the user asks to run the migrated source command `logifix`.

## Command Template

Run the logifix recovery script to restore the LCore tray icon. The procedure is verified in `sessions/System Support/2. Logitech Tray Icon Fix Recurrence.md` (2026-04-25).

Execute the script via PowerShell 7+:

```
pwsh -NoProfile -File "$HOME\.Codex\skills\logifix\scripts\logifix.ps1"
```

The script will prompt for UAC once. Approve it. After it finishes, ask the user to confirm the tray icon is now visible.

If the script reports that UAC was canceled, or LCore did not respond after both relaunch attempts, instruct the user:

1. Press **Ctrl+Shift+Esc** to open Task Manager.
2. Find **Windows Explorer** in the process list.
3. Right-click → **Restart**.
4. Re-run `/logifix`.

The Task Manager Explorer restart is the guaranteed-correct fallback because it always hits the user's interactive session and the right elevation context, regardless of how the calling shell was launched.
