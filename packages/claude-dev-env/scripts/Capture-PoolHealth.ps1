<#
.SYNOPSIS
Captures Windows pool counters, handle pressure, and kernel pool tags for host health checks.

.DESCRIPTION
Reads memory pool counters, total handle/thread counts, processes over the handle alert
threshold, and top kernel pool tags via NtQuerySystemInformation (class 22). Prints a
threshold verdict so an operator can re-run the same recipe from a clean shell.

Alert thresholds (defaults):
  - Pool Nonpaged Bytes  > 2 GB
  - Any process Handles  > 2000
  - Process(_Total) handles > 500000

Attribution context (evidence pack results/04-pool-tags.md): dominant tags File (nonpaged)
and Toke (paged) mean process-object / object-manager pressure. Remediate via RC2 (MCP
lifecycle), RC3 (Show-Asset orphans), RC4 (Git find handle storms) — not a single driver.

.PARAMETER TopTagCount
How many pool tags to print per nonpaged and paged ranking. Default 20.

.PARAMETER TopProcessCount
How many high-handle processes to list. Default 15.

.PARAMETER OutPath
Optional file path. When set, the full report is also written there as UTF-8 text.

.PARAMETER NonpagedAlertBytes
Nonpaged pool alert threshold in bytes. Default 2147483648 (2 GB).

.PARAMETER ProcessHandleAlert
Per-process handle alert threshold. Default 2000.

.PARAMETER TotalHandleAlert
System-wide handle alert threshold. Default 500000.

.EXAMPLE
pwsh -NoProfile -File "$HOME\.claude\scripts\Capture-PoolHealth.ps1"

.EXAMPLE
pwsh -NoProfile -File .\Capture-PoolHealth.ps1 -OutPath "$env:TEMP\pool-health.txt"
#>
[CmdletBinding()]
param(
    [int]$TopTagCount = 20,
    [int]$TopProcessCount = 15,
    [string]$OutPath = '',
    [long]$NonpagedAlertBytes = 2147483648,
    [int]$ProcessHandleAlert = 2000,
    [int]$TotalHandleAlert = 500000
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$script:ReportLines = [System.Collections.Generic.List[string]]::new()

function Write-ReportLine {
    param([string]$Text = '')
    $script:ReportLines.Add($Text)
    Write-Output $Text
}

function Format-BytesAsGigabytes {
    param([long]$ByteCount)
    return ('{0:N3} GB' -f ($ByteCount / 1GB))
}

function Get-MemoryAndHandleCounters {
    # One source of truth for the counters: request order and lookup key both
    # derive from this map, so a name never has to be restated at the call site.
    $counterPathByName = [ordered]@{
        NonpagedBytes   = '\Memory\Pool Nonpaged Bytes'
        PagedBytes      = '\Memory\Pool Paged Bytes'
        CommittedBytes  = '\Memory\Committed Bytes'
        CommitLimit     = '\Memory\Commit Limit'
        AvailableMBytes = '\Memory\Available MBytes'
        TotalHandles    = '\Process(_Total)\Handle Count'
        TotalThreads    = '\Process(_Total)\Thread Count'
    }
    $sample = Get-Counter -Counter @($counterPathByName.Values) -ErrorAction Stop
    $valueByName = @{}
    $index = 0
    foreach ($eachName in $counterPathByName.Keys) {
        $valueByName[$eachName] = [int64]$sample.CounterSamples[$index++].CookedValue
    }
    return $valueByName
}

function Get-HighHandleProcessReport {
    param(
        [int]$HandleThreshold,
        [int]$MaximumRows
    )
    $allHotProcesses = @(
        Get-Process -ErrorAction SilentlyContinue |
            Where-Object { $_.HandleCount -gt $HandleThreshold } |
            Sort-Object -Property HandleCount -Descending
    )
    $topProcesses = @($allHotProcesses | Select-Object -First $MaximumRows)
    $cimByProcessId = @{}
    if ($topProcesses.Count -gt 0) {
        $processIdFilter = @($topProcesses | ForEach-Object { "ProcessId=$($_.Id)" }) -join ' OR '
        try {
            foreach ($eachCimProcess in @(
                    Get-CimInstance -ClassName Win32_Process -Filter $processIdFilter `
                        -ErrorAction SilentlyContinue)) {
                $cimByProcessId[[int]$eachCimProcess.ProcessId] = $eachCimProcess
            }
        }
        catch {
            $null = $_
        }
    }
    $topRows = foreach ($eachProcess in $topProcesses) {
        $commandLine = ''
        $parentProcessId = 0
        $cimProcess = $cimByProcessId[[int]$eachProcess.Id]
        if ($cimProcess) {
            $commandLine = [string]$cimProcess.CommandLine
            $parentProcessId = [int]$cimProcess.ParentProcessId
        }
        [pscustomobject]@{
            ProcessId       = $eachProcess.Id
            Name            = $eachProcess.ProcessName
            HandleCount     = $eachProcess.HandleCount
            ParentProcessId = $parentProcessId
            CommandLine     = $commandLine
        }
    }
    return [pscustomobject]@{
        TotalCount = $allHotProcesses.Count
        TopRows    = @($topRows)
    }
}

function Ensure-PoolTagCaptureType {
    if ('PoolTagCapture' -as [type]) {
        return
    }
    $source = @'
using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;

public static class PoolTagCapture {
    const int SystemPoolTagInformation = 22;

    [DllImport("ntdll.dll")]
    static extern int NtQuerySystemInformation(
        int systemInformationClass,
        IntPtr systemInformation,
        int systemInformationLength,
        out int returnLength);

    [StructLayout(LayoutKind.Explicit, Size = 40)]
    struct SYSTEM_POOLTAG {
        [FieldOffset(0)] public byte Tag0;
        [FieldOffset(1)] public byte Tag1;
        [FieldOffset(2)] public byte Tag2;
        [FieldOffset(3)] public byte Tag3;
        [FieldOffset(4)] public uint PagedAllocs;
        [FieldOffset(8)] public uint PagedFrees;
        [FieldOffset(16)] public ulong PagedUsed;
        [FieldOffset(24)] public uint NonPagedAllocs;
        [FieldOffset(28)] public uint NonPagedFrees;
        [FieldOffset(32)] public ulong NonPagedUsed;
    }

    public static string Capture(int topN) {
        int size = 2 * 1024 * 1024;
        int retLen = 0;
        int status = -1;
        IntPtr buffer = IntPtr.Zero;
        try {
            for (int attempt = 0; attempt < 10; attempt++) {
                buffer = Marshal.AllocHGlobal(size);
                status = NtQuerySystemInformation(
                    SystemPoolTagInformation, buffer, size, out retLen);
                if (unchecked((uint)status) == 0xC0000004u) {
                    Marshal.FreeHGlobal(buffer);
                    buffer = IntPtr.Zero;
                    size = Math.Max(retLen + 8192, size * 2);
                    continue;
                }
                break;
            }
            if (status != 0) {
                return "NTSTATUS=0x" + unchecked((uint)status).ToString("X8")
                    + " retLen=" + retLen;
            }
            int count = Marshal.ReadInt32(buffer);
            int baseOff = 8;
            var tags = new List<SYSTEM_POOLTAG>();
            for (int i = 0; i < count; i++) {
                int offset = baseOff + i * 40;
                if (offset + 40 > retLen) break;
                tags.Add(Marshal.PtrToStructure<SYSTEM_POOLTAG>(
                    IntPtr.Add(buffer, offset)));
            }
            long sumNonPaged = 0;
            long sumPaged = 0;
            foreach (var eachTag in tags) {
                sumNonPaged += (long)eachTag.NonPagedUsed;
                sumPaged += (long)eachTag.PagedUsed;
            }
            var report = new StringBuilder();
            report.AppendLine("retLen=" + retLen + " count=" + count
                + " sizeof_tag=40 status=0 baseOff=" + baseOff);
            report.AppendLine(string.Format(
                "SUM NonPaged={0} ({1:N3} GB) Paged={2} ({3:N3} GB)",
                sumNonPaged, sumNonPaged / 1073741824.0,
                sumPaged, sumPaged / 1073741824.0));
            report.AppendLine(string.Format(
                "{0,-6} {1,14} {2,14}", "Tag", "NonPaged", "Paged"));
            report.AppendLine("--- TOP BY NONPAGED ---");
            foreach (var eachTag in tags.OrderByDescending(t => t.NonPagedUsed).Take(topN)) {
                report.AppendLine(FormatTag(eachTag));
            }
            report.AppendLine("--- TOP BY PAGED ---");
            foreach (var eachTag in tags.OrderByDescending(t => t.PagedUsed).Take(topN)) {
                report.AppendLine(FormatTag(eachTag));
            }
            var watchTagNames = new[] { "File", "IoFE", "Toke", "Key", "FMfn" };
            var watchNames = new HashSet<string>(watchTagNames, StringComparer.Ordinal);
            report.AppendLine("--- WATCHLIST " + string.Join(" ", watchTagNames) + " ---");
            foreach (var eachTag in tags) {
                string cleanedName = TagName(eachTag).TrimEnd(' ', '.', '\0');
                if (watchNames.Contains(cleanedName)) {
                    report.AppendLine(FormatTag(eachTag));
                }
            }
            return report.ToString().TrimEnd();
        }
        finally {
            if (buffer != IntPtr.Zero) {
                Marshal.FreeHGlobal(buffer);
            }
        }
    }

    static string TagName(SYSTEM_POOLTAG tag) {
        return string.Concat(CharOf(tag.Tag0), CharOf(tag.Tag1),
            CharOf(tag.Tag2), CharOf(tag.Tag3));
    }

    static char CharOf(byte value) {
        return (value >= 32 && value < 127) ? (char)value : '.';
    }

    static string FormatTag(SYSTEM_POOLTAG tag) {
        return string.Format("{0,-6} {1,14} {2,14}",
            TagName(tag), tag.NonPagedUsed, tag.PagedUsed);
    }
}
'@
    Add-Type -TypeDefinition $source -Language CSharp
}

function Get-PoolTagReport {
    param([int]$TopCount)
    Ensure-PoolTagCaptureType
    return [PoolTagCapture]::Capture($TopCount)
}

function Get-ThresholdAlerts {
    param(
        [int64]$NonpagedBytes,
        [int64]$TotalHandles,
        [int]$HighHandleProcessCount,
        [long]$NonpagedAlert,
        [int]$ProcessHandleAlert,
        [int]$TotalHandleAlert
    )
    $allAlerts = [System.Collections.Generic.List[string]]::new()
    if ($NonpagedBytes -gt $NonpagedAlert) {
        $allAlerts.Add((
            "ALERT nonpaged={0} threshold={1}" -f `
                (Format-BytesAsGigabytes $NonpagedBytes),
                (Format-BytesAsGigabytes $NonpagedAlert)
        ))
    }
    if ($TotalHandles -gt $TotalHandleAlert) {
        $allAlerts.Add((
            "ALERT total_handles={0} threshold={1}" -f $TotalHandles, $TotalHandleAlert
        ))
    }
    if ($HighHandleProcessCount -gt 0) {
        $allAlerts.Add((
            "ALERT processes_over_{0}_handles={1}" -f `
                $ProcessHandleAlert, $HighHandleProcessCount
        ))
    }
    return , $allAlerts
}

# --- main ---
$timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'
Write-ReportLine "TIMESTAMP: $timestamp"
Write-ReportLine "HOST: $env:COMPUTERNAME"
Write-ReportLine (
    "THRESHOLDS: nonpaged>{0}; process_handles>{1}; total_handles>{2}" -f `
        (Format-BytesAsGigabytes $NonpagedAlertBytes),
        $ProcessHandleAlert,
        $TotalHandleAlert
)

Write-ReportLine ''
Write-ReportLine '=== COUNTERS ==='
$counterByName = Get-MemoryAndHandleCounters
$nonpagedBytes = $counterByName['NonpagedBytes']
$pagedBytes = $counterByName['PagedBytes']
$committedBytes = $counterByName['CommittedBytes']
$commitLimitBytes = $counterByName['CommitLimit']
$availableMBytes = $counterByName['AvailableMBytes']
$totalHandles = $counterByName['TotalHandles']
$totalThreads = $counterByName['TotalThreads']

Write-ReportLine ("Pool Nonpaged Bytes = {0} ({1})" -f $nonpagedBytes, (Format-BytesAsGigabytes $nonpagedBytes))
Write-ReportLine ("Pool Paged Bytes    = {0} ({1})" -f $pagedBytes, (Format-BytesAsGigabytes $pagedBytes))
Write-ReportLine ("Committed Bytes     = {0} ({1})" -f $committedBytes, (Format-BytesAsGigabytes $committedBytes))
Write-ReportLine ("Commit Limit        = {0} ({1})" -f $commitLimitBytes, (Format-BytesAsGigabytes $commitLimitBytes))
Write-ReportLine ("Available MBytes    = {0}" -f $availableMBytes)
Write-ReportLine ("Handle Count Total  = {0}" -f $totalHandles)
Write-ReportLine ("Thread Count Total  = {0}" -f $totalThreads)

Write-ReportLine ''
Write-ReportLine ("=== PROCESSES WITH HANDLES > {0} ===" -f $ProcessHandleAlert)
$highHandleReport = Get-HighHandleProcessReport `
    -HandleThreshold $ProcessHandleAlert `
    -MaximumRows $TopProcessCount
if ($highHandleReport.TopRows.Count -eq 0) {
    Write-ReportLine '(none)'
}
else {
    foreach ($eachProcess in $highHandleReport.TopRows) {
        $commandPreview = ''
        if ($eachProcess.CommandLine) {
            $commandPreview = $eachProcess.CommandLine
            if ($commandPreview.Length -gt 120) {
                $commandPreview = $commandPreview.Substring(0, 117) + '...'
            }
        }
        Write-ReportLine (
            "PID={0} Name={1} Handles={2} Parent={3} Cmd={4}" -f `
                $eachProcess.ProcessId,
                $eachProcess.Name,
                $eachProcess.HandleCount,
                $eachProcess.ParentProcessId,
                $commandPreview
        )
    }
}

$highHandleProcessCount = $highHandleReport.TotalCount
Write-ReportLine ("High-handle process count (all): {0}" -f $highHandleProcessCount)

Write-ReportLine ''
Write-ReportLine '=== POOL TAGS (NtQuerySystemInformation class 22) ==='
try {
    Write-ReportLine (Get-PoolTagReport -TopCount $TopTagCount)
}
catch {
    Write-ReportLine ("POOL TAG CAPTURE FAILED: {0}" -f $_.Exception.Message)
}

Write-ReportLine ''
Write-ReportLine '=== REMEDIATION MAP (process-object pressure) ==='
Write-ReportLine 'Dominant tags File (nonpaged) + Toke (paged) -> object-manager sprawl, not a lone driver leak.'
Write-ReportLine 'RC2 #255  Cap MCP servers (mcpvault/playwright/serena spawn-without-reap) -> cuts File/Toke/Thre'
Write-ReportLine 'RC3 #254  Show-Asset.ps1 exit on parent death + timeout -> cuts orphan UI process handles'
Write-ReportLine 'RC4 #253  Block Git find walks; es.exe primary; kill find with handles >2k -> cuts Key/handle storms'
Write-ReportLine 'RC5 #256  Attribute WSL/Docker starters only after measurement (VdMm secondary)'
Write-ReportLine 'Optional: install WDK poolmon.exe for stock binary snapshots (this script needs no WDK).'

$allThresholdAlerts = Get-ThresholdAlerts `
    -NonpagedBytes $nonpagedBytes `
    -TotalHandles $totalHandles `
    -HighHandleProcessCount $highHandleProcessCount `
    -NonpagedAlert $NonpagedAlertBytes `
    -ProcessHandleAlert $ProcessHandleAlert `
    -TotalHandleAlert $TotalHandleAlert
Write-ReportLine ''
Write-ReportLine '=== THRESHOLD VERDICT ==='
if ($allThresholdAlerts.Count -eq 0) {
    Write-ReportLine 'OK - all thresholds clear'
    $thresholdExitCode = 0
}
else {
    foreach ($eachAlert in $allThresholdAlerts) {
        Write-ReportLine $eachAlert
    }
    Write-ReportLine 'REMEDIATE: process-object pressure (File/Toke tags) -> RC2 #255, RC3 #254, RC4 #253'
    $thresholdExitCode = 1
}

if ($OutPath) {
    $destinationDirectory = Split-Path -Parent $OutPath
    if ($destinationDirectory -and -not (Test-Path -LiteralPath $destinationDirectory)) {
        New-Item -ItemType Directory -Path $destinationDirectory -Force | Out-Null
    }
    $script:ReportLines -join [Environment]::NewLine |
        Set-Content -LiteralPath $OutPath -Encoding utf8
    Write-Output ""
    Write-Output "Wrote report: $OutPath"
}

exit $thresholdExitCode
