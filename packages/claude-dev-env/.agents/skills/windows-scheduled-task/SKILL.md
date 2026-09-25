---
name: windows-scheduled-task
description: >-
  Register a repeating headless Windows scheduled task from PowerShell, with endless repetition, an S4U or Interactive principal, absolute action paths, and a documented teardown. Use when creating, repairing, or removing a repeating Task Scheduler task, including a task that fails to register.
---

# Windows scheduled task

## Contents

- Principle
- Gotchas
- When this applies
- Process
- Endless repetition
- Headless principal
- Absolute paths in the action
- Settings
- Placement outside managed paths
- Status
- Removal and teardown
- Self-modification warning
- Handing the elevated step to the operator
- Verification
- Files

## Principle

A registered task carries four decisions. How it repeats, which principal runs it, which absolute
executable it starts, and where its target files sit. Settle all four at registration time, then
prove the task by the artifact it changes.

## Gotchas

- `New-ScheduledTaskTrigger -RepetitionDuration ([TimeSpan]::MaxValue)` fails the task XML schema with `The task XML contains a value which is incorrectly formatted or out of range. (10,42):Duration:P99999999DT23H59M59S`.
- `-LogonType S4U` requires an elevated shell. An unelevated `Register-ScheduledTask` ends with `Access is denied.`
- Task Scheduler inherits none of the shell PATH. A bare executable name in the action fails at run time.
- A helper under an installer-managed path deletes itself during an installer run.
- `LastTaskResult: 0` from a run that took the idle branch says nothing about the branch that acts.
- A `#Requires -RunAsAdministrator` line pasted at a prompt checks nothing. It applies only to a script file.
- An elevated window opens in `C:\WINDOWS\system32`. A prompt in the user's home folder is usually unelevated.

## When this applies

Use this skill for a repeating Windows task registered from PowerShell through the ScheduledTasks
module. Register the task in an elevated shell when the task must run while the user is signed out.

## Process

1. Resolve every executable in the action with `Get-Command <name>` and read `.Source`.
2. Read `files[]` in `~/.claude/.claude-dev-env-manifest.json` and pick a directory that list omits.
3. Build the action with the absolute executable path and `-WindowStyle Hidden` inside the argument string.
4. Build a `-Once` trigger with a repetition interval and no duration, then clear the duration on the trigger object.
5. Build the settings set.
6. Register with an S4U principal, catch the registration failure, and register with an Interactive principal.
7. Report which principal the registered task holds.
8. Drive the branch that does the work and read the artifact it changes.
9. Document the removal command beside the task.

## Endless repetition

```powershell
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)
$Trigger.Repetition.Duration = ''
$Trigger.Repetition.StopAtDurationEnd = $false
```

An empty duration string on the trigger object registers a repetition that keeps firing. Build the
trigger without a duration argument and set the two properties afterward.

## Headless principal

```powershell
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U
try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force -ErrorAction Stop
    $PrincipalKind = 'S4U'
} catch {
    $Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force
    $PrincipalKind = 'Interactive'
}
```

S4U runs the task with no window whether or not the user is signed in, and its registration needs an
elevated shell. The Interactive principal with `-WindowStyle Hidden` in the action runs windowless
while the user is signed in. Report `$PrincipalKind` so the operator knows which one the task holds.

## Absolute paths in the action

```powershell
$PwshPath = (Get-Command pwsh).Source
$Action = New-ScheduledTaskAction -Execute $PwshPath -Argument "-NoProfile -WindowStyle Hidden -File ""$ScriptPath"""
```

Resolve each executable at registration time and store the absolute path in the action. Give the
script an absolute path too.

## Settings

```powershell
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 1)
```

These settings keep the task firing on battery power, catch up a missed run, drop an overlapping
start, and cap a hung run.

## Placement outside managed paths

The claude-dev-env installer records every managed path in `~/.claude/.claude-dev-env-manifest.json`
under `files[]`, and `--update` removes those paths before it reinstalls from the package. A helper
that a task starts from a managed directory disappears mid-run. Read `files[]`, then place the
helper and its state files in a directory the manifest omits, such as a path under `<user home>`
outside `~/.claude`.

## Status

```powershell
$Info = Get-ScheduledTaskInfo -TaskName $TaskName
$Info.LastRunTime
$Info.LastTaskResult
$Info.NextRunTime
```

## Removal and teardown

```powershell
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
```

Put this command in the same document that describes the task.

## Self-modification warning

A task that installs updates of the agent rules, hooks, and skills rewrites the running session
instructions on a timer. A major upgrade can land mid-session while the agent holds the older text.
Give the operator the teardown command, name the interval, and keep the interval wide enough for a
session to finish between runs.

## Handing the elevated step to the operator

The operator runs the elevated part by hand, so hand it over as one block they paste into an
Administrator window. Put the block in the message itself. A file to download adds a step and a
path the browser can rename.

Wrap the block in `& { ... }` and open it with an elevation check, so an unelevated paste stops
with a clear line and changes nothing:

```powershell
& {
$ErrorActionPreference = 'Stop'
$IsAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $IsAdmin) { Write-Host 'NOT ELEVATED. Open PowerShell with Run as administrator and paste again.' -ForegroundColor Red; return }
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Principal $Principal -Force
}
```

The script block scopes `$ErrorActionPreference` and lets `return` end the paste. End the block
with a status print the operator copies back, so the next step reads the result.

## Verification

A run that takes the idle branch reports `LastTaskResult: 0`, and that result covers the idle branch
alone. Prove the acting branch: create the condition the task acts on, wait one interval, then read
the artifact the task changes and its timestamp.

## Files

- `SKILL.md`. Registration rules, worked examples, status, and teardown.

`packages/claude-dev-env/scripts/Install-SweepEmptyDirs.ps1` is the working model in this repository
for the install, `-Remove`, and `-Status` parameter sets and symmetric teardown.

```text
windows-scheduled-task/
└── SKILL.md
```
