[CmdletBinding()]
param(
    [Parameter(HelpMessage = 'Process id to keep (0 = kill every matching AutoHotkey instance).')]
    [int] $KeepProcessId = 0
)

$scriptMarker = 'cursor-agents-continue.ahk'
$processes = Get-CimInstance Win32_Process -Filter "Name='AutoHotkey64.exe'" |
    Where-Object { $_.CommandLine -like "*$scriptMarker*" }

foreach ($eachProcess in $processes) {
    if ($KeepProcessId -ne 0 -and $eachProcess.ProcessId -eq $KeepProcessId) {
        continue
    }
    Stop-Process -Id $eachProcess.ProcessId -Force -ErrorAction SilentlyContinue
}
