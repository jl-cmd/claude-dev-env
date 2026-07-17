# Host pool health monitor

Operator recipe for kernel pool counters, handle pressure, and pool tags on a Windows host that runs Claude Code / agent tooling. Ships as `scripts/Capture-PoolHealth.ps1` (installed to `~/.claude/scripts/`).

## Verdict this monitor tracks

Evidence capture (`results/04-pool-tags.md` in the ram-process-sprawl plan pack) shows:

| Tag | Pool | Role |
|-----|------|------|
| **File** | nonpaged (~multi-GB when bad) | File objects |
| **IoFE** | nonpaged | I/O / file-object adjacent |
| **Toke** | paged (~multi-GB when bad) | Security token objects |
| **Key** | paged | Registry key objects (often Git `find` storms) |

**Primary story:** process-object / object-manager pressure from agent sprawl — not a single third-party driver leak. Fix sprawl with RC2 / RC3 / RC4; re-run this recipe after those land to confirm File/Toke fall.

## Alert thresholds

| Signal | Alert when |
|--------|------------|
| `\Memory\Pool Nonpaged Bytes` | **> 2 GB** |
| Any process `HandleCount` | **> 2000** |
| `\Process(_Total)\Handle Count` | **> 500000** |

Also watch pool tags **File**, **Toke**, **IoFE**, **Key**, **FMfn** whenever any threshold fires.

## Clean-shell re-run

From a new PowerShell window (no profile, no prior session state):

```powershell
# After package install (npx claude-dev-env / node bin/install.mjs)
pwsh -NoProfile -File "$HOME\.claude\scripts\Capture-PoolHealth.ps1"

# Or from a checkout
pwsh -NoProfile -File "packages\claude-dev-env\scripts\Capture-PoolHealth.ps1"

# Save a snapshot
pwsh -NoProfile -File "$HOME\.claude\scripts\Capture-PoolHealth.ps1" `
  -OutPath "$env:TEMP\pool-health-$(Get-Date -Format yyyyMMdd-HHmmss).txt"
```

Exit code: `0` = all thresholds clear; `1` = one or more alerts; non-zero also on hard capture failure.

### What the script prints

1. **Counters** — nonpaged/paged pool, commit, available MB, total handles/threads  
2. **High-handle processes** — every process over the handle threshold (top N by default)  
3. **Pool tags** — top nonpaged, top paged, plus File/IoFE/Toke/Key/FMfn watchlist via `NtQuerySystemInformation` class 22 (same source PoolMon uses; no admin and no WDK required)  
4. **Threshold verdict** — `OK` or `ALERT ...` lines  
5. **Remediation map** — RC issue pointers below  

### Counters-only one-liner (no tags)

```powershell
pwsh -NoProfile -Command "
  Get-Date -Format 'yyyy-MM-dd HH:mm:ss zzz'
  Get-Counter '\Memory\Pool Nonpaged Bytes','\Memory\Pool Paged Bytes',
    '\Memory\Committed Bytes','\Memory\Available MBytes',
    '\Process(_Total)\Handle Count','\Process(_Total)\Thread Count' |
    Select-Object -ExpandProperty CounterSamples |
    Format-Table Path, CookedValue -AutoSize
"
```

## Remediation map

When nonpaged, handles, or File/Toke tags are high, apply the sprawl fixes — not a random driver unload.

| RC | Issue | What it cuts | Expected pool/handle effect |
|----|-------|--------------|-----------------------------|
| **RC2** | [#255](https://github.com/jl-cmd/claude-dev-env/issues/255) Cap MCP servers — stop per-session mcpvault/playwright/serena spawn-without-reap | Extra `node`/MCP process trees | Lower **File** / **Toke** / **Thre** object pressure |
| **RC3** | [#254](https://github.com/jl-cmd/claude-dev-env/issues/254) `Show-Asset.ps1` exit on parent death + timeout | Orphan UI/`Application.Run` processes | Lower process count and handle tables |
| **RC4** | [#253](https://github.com/jl-cmd/claude-dev-env/issues/253) Block Git `find` filesystem walks; `es.exe` primary; kill runaway `find` (>2k handles) | Orphan `Git\usr\bin\find.exe` with 10^5–10^6 **Key** handles | Sharp drop in total handles and **Key** paged; secondary relief on object manager |
| **RC5** | [#256](https://github.com/jl-cmd/claude-dev-env/issues/256) Attribute WSL/Docker/cowork VM starters | `vmmem*` / **VdMm** | Secondary only — measure first; no blind `.wslconfig` memory cap |

**Do not** treat multi-GB **File**/**Toke** as “install poolmon and hunt NVRM.” NVRM/VdMm appear as tens of MB in the evidence pack; the multi-GB leaders are object-class tags.

### Emergency: runaway `find.exe`

```powershell
Get-CimInstance Win32_Process -Filter "Name='find.exe'" |
  Select-Object ProcessId, ParentProcessId, HandleCount, CommandLine
# If HandleCount > 2000 and parent is dead → stop the process (RC4 policy)
```

## After RC2 / RC3 / RC4 land

1. Idle the agent host (no active find storms, no orphan Show-Asset, MCP set capped).  
2. Re-run `Capture-PoolHealth.ps1` from a clean shell.  
3. Confirm: nonpaged trend down, total handles under 500k when idle, **File**/**Toke** tag bytes down vs the 04-pool-tags baseline.  

## Optional: stock `poolmon.exe`

This recipe does **not** need the WDK. Operators who prefer the Microsoft binary can install Windows Driver Kit tools and run elevated `poolmon -b` snapshots. Tag names still map through `pooltag.txt` under Windows Kits Debuggers when present.

## Related

- Parent epic: [#252](https://github.com/jl-cmd/claude-dev-env/issues/252)  
- This child: [#257](https://github.com/jl-cmd/claude-dev-env/issues/257)  
- Script: `packages/claude-dev-env/scripts/Capture-PoolHealth.ps1`  
