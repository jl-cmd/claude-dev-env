<#
.SYNOPSIS
Opens files on screen, sizing each image window to the image's own dimensions.

.DESCRIPTION
For every path given, an image opens in a window whose client area matches the
image's pixel size, scaled down to fit the primary screen's working area when the
image is larger than the screen. A small image gets a usable minimum window with
the picture centered at native size. Non-image files open in their registered
default application, and any file that cannot be loaded as an image falls back to
that default application too. Escape or the close button dismisses a window; the
process exits once every window is closed.

Callers often launch this script with Start-Process and do not wait. The script
therefore watches its parent process and a max lifetime so orphan viewers cannot
outlive a dead agent parent or run indefinitely:

- Parent-death watch: poll the parent PID on an interval (default 1s). When the
  parent is gone, all forms close and the process exits.
- Max lifetime: after the configured span (default 30 minutes) forms close and
  the process exits even if windows remain open.

.PARAMETER Paths
One or more file paths to open.

.PARAMETER ParentProcessId
Process id to watch for death. When 0 (default), the script's own parent process
id is used. Pass an explicit id in tests.

.PARAMETER MaxLifetimeSeconds
Maximum seconds the viewer may stay open (default 1800 = 30 minutes). When the
span elapses, forms close and the process exits.

.PARAMETER ParentPollIntervalMilliseconds
How often to poll the parent process and max lifetime (default 1000 ms).
#>
param(
    [ValidateRange(0, [int]::MaxValue)]
    [int]$ParentProcessId = 0,

    [ValidateRange(1, 86400)]
    [int]$MaxLifetimeSeconds = 1800,

    [ValidateRange(250, 10000)]
    [int]$ParentPollIntervalMilliseconds = 1000,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Paths
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

try {
    [System.Windows.Forms.Application]::SetHighDpiMode([System.Windows.Forms.HighDpiMode]::PerMonitorV2) | Out-Null
}
catch {
    $null = $_
}
[System.Windows.Forms.Application]::EnableVisualStyles()

$imageExtensions = @('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp', '.tif', '.tiff', '.ico')
$screenMargin = 80
$minimumClientWidth = 220
$minimumClientHeight = 160
$openWindowCount = 0
$allOpenForms = New-Object 'System.Collections.Generic.List[System.Windows.Forms.Form]'
$sessionStartedAtUtc = [datetime]::UtcNow
$maxLifetime = [timespan]::FromSeconds($MaxLifetimeSeconds)

function Get-OwnParentProcessId {
    try {
        $ownProcessRecord = Get-CimInstance -ClassName Win32_Process -Filter "ProcessId=$PID" -ErrorAction Stop
        return [int]$ownProcessRecord.ParentProcessId
    }
    catch {
        return 0
    }
}

function Test-ProcessIsAlive {
    param(
        [int]$ProcessId
    )
    if ($ProcessId -le 0) {
        return $true
    }
    try {
        $null = Get-Process -Id $ProcessId -ErrorAction Stop
        return $true
    }
    catch {
        return $false
    }
}

function Stop-ShowAssetSession {
    if ($null -ne $script:watchTimer) {
        $script:watchTimer.Stop()
    }
    foreach ($eachForm in @($script:allOpenForms.ToArray())) {
        if (-not $eachForm.IsDisposed) {
            $eachForm.Close()
        }
    }
    [System.Windows.Forms.Application]::Exit()
}

function Test-ShouldEndShowAssetSession {
    $isParentAlive = Test-ProcessIsAlive -ProcessId $script:watchedParentProcessId
    if (-not $isParentAlive) {
        return $true
    }
    $elapsedLifetime = [datetime]::UtcNow - $script:sessionStartedAtUtc
    if ($elapsedLifetime -ge $script:maxLifetime) {
        return $true
    }
    return $false
}

if ($ParentProcessId -gt 0) {
    $watchedParentProcessId = $ParentProcessId
}
else {
    $watchedParentProcessId = Get-OwnParentProcessId
}

foreach ($path in $Paths) {
    if (-not (Test-Path -LiteralPath $path)) { continue }
    $fullPath = (Resolve-Path -LiteralPath $path).Path
    $extension = [System.IO.Path]::GetExtension($fullPath).ToLowerInvariant()

    if ($imageExtensions -notcontains $extension) {
        Invoke-Item -LiteralPath $fullPath
        continue
    }

    try {
        $imageBytes = [System.IO.File]::ReadAllBytes($fullPath)
        $imageStream = New-Object System.IO.MemoryStream(, $imageBytes)
        $loadedImage = [System.Drawing.Image]::FromStream($imageStream)
        $image = New-Object System.Drawing.Bitmap($loadedImage)
        $loadedImage.Dispose()
        $imageStream.Dispose()
    }
    catch {
        Invoke-Item -LiteralPath $fullPath
        continue
    }

    $workingArea = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
    $maximumWidth = $workingArea.Width - $screenMargin
    $maximumHeight = $workingArea.Height - $screenMargin
    $scale = [Math]::Min(1.0, [Math]::Min($maximumWidth / $image.Width, $maximumHeight / $image.Height))

    $pictureBox = New-Object System.Windows.Forms.PictureBox
    $pictureBox.Dock = [System.Windows.Forms.DockStyle]::Fill
    $pictureBox.Image = $image

    if ($scale -lt 1.0) {
        $pictureBox.SizeMode = [System.Windows.Forms.PictureBoxSizeMode]::Zoom
        $clientWidth = [int][Math]::Round($image.Width * $scale)
        $clientHeight = [int][Math]::Round($image.Height * $scale)
    }
    else {
        $pictureBox.SizeMode = [System.Windows.Forms.PictureBoxSizeMode]::CenterImage
        $clientWidth = [Math]::Max($minimumClientWidth, $image.Width)
        $clientHeight = [Math]::Max($minimumClientHeight, $image.Height)
    }

    $form = New-Object System.Windows.Forms.Form
    $form.Text = [System.IO.Path]::GetFileName($fullPath)
    $form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::None
    $form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
    $form.ClientSize = New-Object System.Drawing.Size($clientWidth, $clientHeight)
    $form.KeyPreview = $true
    $form.BackColor = [System.Drawing.Color]::FromArgb(24, 24, 24)
    $form.Controls.Add($pictureBox)

    $form.Add_KeyDown({
            param($sender, $eventArguments)
            if ($eventArguments.KeyCode -eq [System.Windows.Forms.Keys]::Escape) { $sender.Close() }
        })
    $form.Add_FormClosed({
            param($sender, $eventArguments)
            [void]$script:allOpenForms.Remove($sender)
            $script:openWindowCount--
            if ($script:openWindowCount -le 0) { [System.Windows.Forms.Application]::Exit() }
        })

    $openWindowCount++
    [void]$allOpenForms.Add($form)
    $form.Show()
}

if ($openWindowCount -gt 0) {
    $watchTimer = New-Object System.Windows.Forms.Timer
    $watchTimer.Interval = $ParentPollIntervalMilliseconds
    $watchTimer.Add_Tick({
            if (Test-ShouldEndShowAssetSession) {
                Stop-ShowAssetSession
            }
        })
    $watchTimer.Start()
    [System.Windows.Forms.Application]::Run()
}
