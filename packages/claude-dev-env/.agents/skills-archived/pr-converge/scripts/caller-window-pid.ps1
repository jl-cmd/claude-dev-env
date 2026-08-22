[CmdletBinding()]
param()

$DESKTOP_SHELL_TERMINATOR_NAME = 'explorer'
$MAXIMUM_PARENT_WALK_DEPTH     = 24

if (-not ('CallerWindowPid.Win32ForegroundWindowQuery' -as [type])) {
    Add-Type -Namespace 'CallerWindowPid' -Name 'Win32ForegroundWindowQuery' -MemberDefinition @'
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        public static extern System.IntPtr GetForegroundWindow();
        [System.Runtime.InteropServices.DllImport("user32.dll")]
        public static extern uint GetWindowThreadProcessId(System.IntPtr hWnd, out uint processId);
'@
}

function Get-ParentProcessId {
    param([int]$ChildProcessId)
    try {
        return (Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$ChildProcessId" -ErrorAction Stop).ParentProcessId
    } catch {
        return 0
    }
}

function Resolve-NearestGuiAncestorPid {
    param([int]$StartingProcessId)

    $visited_process_ids = @{}
    $current_process_id  = $StartingProcessId
    $walk_depth          = 0

    while ($walk_depth -lt $MAXIMUM_PARENT_WALK_DEPTH) {
        $walk_depth++
        if ($visited_process_ids.ContainsKey($current_process_id)) {
            return $null
        }
        $visited_process_ids[$current_process_id] = $true

        $parent_process_id = Get-ParentProcessId -ChildProcessId $current_process_id
        if (-not $parent_process_id -or $parent_process_id -eq 0) {
            return $null
        }

        try {
            $parent_process = Get-Process -Id $parent_process_id -ErrorAction Stop
        } catch {
            return $null
        }

        if ($parent_process.ProcessName -eq $DESKTOP_SHELL_TERMINATOR_NAME) {
            return $null
        }

        if ($parent_process.MainWindowHandle -ne [IntPtr]::Zero) {
            return $parent_process.Id
        }

        $current_process_id = $parent_process_id
    }

    return $null
}

function Resolve-ForegroundWindowPid {
    $foreground_window_handle = [CallerWindowPid.Win32ForegroundWindowQuery]::GetForegroundWindow()
    if ($foreground_window_handle -eq [IntPtr]::Zero) {
        return $null
    }
    $foreground_window_pid = [uint32]0
    [void][CallerWindowPid.Win32ForegroundWindowQuery]::GetWindowThreadProcessId($foreground_window_handle, [ref]$foreground_window_pid)
    if ($foreground_window_pid -eq 0) {
        return $null
    }
    return [int]$foreground_window_pid
}

$resolved_pid = Resolve-NearestGuiAncestorPid -StartingProcessId $PID
if ($null -eq $resolved_pid) {
    $resolved_pid = Resolve-ForegroundWindowPid
}
if ($null -eq $resolved_pid) {
    Write-Error "Could not resolve a GUI process from PID $PID or the foreground window."
    exit 1
}

Write-Output $resolved_pid
