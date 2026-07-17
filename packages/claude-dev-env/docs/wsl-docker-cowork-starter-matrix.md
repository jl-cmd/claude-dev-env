# WSL / Docker / Cowork starter matrix

Attribution and policy surface for host memory consumers that sit under WSL2, Docker Desktop, and the Claude Cowork HCS VM. Source evidence: forensic capture summarized on [issue #256](https://github.com/jl-cmd/claude-dev-env/issues/256) (`results/05-wsl-who-started.md` in the local ram-process-sprawl evidence pack). This file records supported starters, whether each component is required for day-to-day agent work, and how to shut it down. It does **not** apply a `.wslconfig` memory cap.

## Hard rules

1. **No unmeasured `.wslconfig` memory cap.** Do not set `memory=` (or other hard caps) in `%UserProfile%\.wslconfig` until (a) the owner of the WSL VM commit is known for the workload under test and (b) a before/after private-working-set measurement is recorded on the same host boot window. A blind cap is out of scope for this matrix.
2. **Proven starters only.** Rows below use only process-parent, service, HCS owner, registry, and product-log evidence from the capture. Proximity without a parent edge is labeled **unknown**, not a starter claim.
3. **Two HCS VMs are not one.** Owner=`WSL` maps to `vmmemWSL`. Owner=`cowork-vm-*` maps to plain `vmmem`. Treat them as separate shutdown and policy targets.

## Starter matrix

| Component | Starter / owner (supported) | Required for daily agent work? | Shutdown / stop |
|-----------|----------------------------|--------------------------------|-----------------|
| **WSLService** (`wslservice.exe`) | Windows service **WSLService**, StartMode=Auto, parent `services.exe` since boot | **Platform yes** if any WSL2 distro is used; leave Auto unless WSL is retired on the host | `Stop-Service WSLService` only when deliberately disabling WSL; normal idle path is distro shutdown, not service kill |
| **`vmmemWSL`** (WSL2 utility VM) | HCS VM Owner=`WSL`; worker chain `vmcompute` → `vmwp` → `vmmemWSL` | **Yes while any distro is Running** (`wsl -l -v`) | `wsl --shutdown` (stops all WSL2 distros and the WSL utility VM; disrupts Docker's WSL backend too) |
| **First user wake of WSL VM** | **Unknown** in the capture (no Security 4688; no surviving user `wsl.exe` from the create second). Docker was **not** up yet at that create time | N/A — attribution gap | Same as `vmmemWSL` once running |
| **Docker Desktop / `com.docker.backend`** | Docker Desktop launches backend (product log). **HKCU Run** key registers Docker Desktop for logon. Windows service `com.docker.service` was **Stopped** / Manual — engine path is Desktop/backend user-mode | **Only when containers or Docker tooling are in active use** | Quit Docker Desktop (tray → Quit); confirm `com.docker.backend` gone. Optional: remove or disable the HKCU Run value named `Docker Desktop` so logon does not relaunch it |
| **Live `wsl.exe` for `docker-desktop` + Ubuntu integration** | Parent **`com.docker.backend.exe` (services)** | Same as Docker Desktop | Stop Docker Desktop; or `wsl --shutdown` (broader blast radius) |
| **Live `wsl.exe` for `code-index-mcp`** | Parent **`codex.exe`** ← **ChatGPT.exe** ← explorer. Command shape: `wsl.exe …/code-index-mcp` | **Only while Codex/ChatGPT needs the Ubuntu MCP indexer** | Exit Codex / ChatGPT app-server session; confirm no `wsl.exe` whose command line is `code-index-mcp` |
| **Plain `vmmem` (cowork HCS VM)** | HCS VM Owner=`cowork-vm-*` (name match). Chain `vmcompute` → `vmwp` → `vmmem`. **Exact user process that created the VM is unknown** (no live parent edge). Claude Desktop cmdlines carry `cowork-*` schemes; that is label association, not a proven create edge | **Only while Claude Cowork VM features are in use** | Quit Claude Desktop / Cowork UI that owns the session; if the HCS VM remains Running, treat full stop as an open procedure (see open questions). Do **not** assume `wsl --shutdown` stops this VM — it is not Owner=`WSL` |
| **grok as WSL parent** | **None** in the capture (high-confidence negative) | N/A | N/A |
| **claude as parent of live `wsl.exe`** | **None** in the capture (high-confidence negative) | N/A for WSL shells; see cowork row for the separate HCS VM | N/A for `wsl.exe` |

### Capture facts that stay fixed for this matrix

These are host-capture facts the matrix must not rewrite:

- Docker autostart capability is the **HKCU `Run` key** entry for Docker Desktop (not the stopped `com.docker.service`).
- **Codex `code-index-mcp`** is a live holder of `wsl.exe`; it is not the create-time owner of `vmmemWSL` when Codex starts hours later.
- **cowork-vm** is a **separate** HCS VM and plain `vmmem` consumer; it is not `vmmemWSL`.
- **grok** and **claude** were **not** parents of any live `wsl.exe` in the capture.

## Open questions

Named gaps only — do not fill these with guesses in policy or code:

1. **Exact user-mode process that first woke the WSL VM** at the `vmmemWSL` create second (Security 4688 / Sysmon not available in the capture).
2. **Exact process that created HCS `cowork-vm-*` / plain `vmmem`** (parent chain ends at `vmwp` / `vmcompute`).
3. **Whether a given Docker start was pure logon Run vs interactive tray open** (Run key proves capability; a dead parent PID on the backend does not by itself prove which path fired).
4. **Identity of dead parents** of mid-session Ubuntu `wslhost` processes whose PPID is already recycled.
5. **Documented, safe idle-stop for the cowork HCS VM** when Claude UI is gone but `hcsdiag` still lists Owner=`cowork-vm-*` Running.
6. **Whether historical sessions of grok/claude started WSL earlier in a boot** — unprovable without process-creation audit history; live snapshot negatives do not extend backward.

To close (1), (2), (4), or (6): enable process-creation audit (Security 4688) or Sysmon with filters on `wsl.exe`, `vmwp.exe`, and Docker/Claude/Codex image paths, then re-capture on a clean boot.

## Policy options (with costs)

Choose explicitly. None of these options includes an unmeasured `.wslconfig` `memory=` write.

| Option | Action | RAM / sprawl effect (directional) | Cost / risk |
|--------|--------|-----------------------------------|-------------|
| **P0 — Observe only** | Keep matrix; no host change | None until a component is stopped | Continues dual-VM + Docker + Codex WSL hold when those apps run |
| **P1 — Docker on demand** | Remove or disable HKCU Run `Docker Desktop`; start Desktop only when containers are needed | Avoids Docker backend + docker-desktop/Ubuntu integration `wsl.exe` on boots/sessions that never use Docker | Manual start latency; first container work pays cold start; any script that assumes Docker is already up fails until launch |
| **P2 — Docker fully off when idle** | Quit Docker Desktop after use; optional P1 | Frees backend private set and Docker-held WSL distro activity | Must re-open Desktop before compose/build; `wsl -l -v` may still show Running until `wsl --shutdown` or Docker stops holding distros |
| **P3 — Codex indexer off when idle** | Exit ChatGPT/Codex app-server when not reviewing; disable code-index MCP if product settings allow | Drops Codex-held `wsl.exe … code-index-mcp` edges | Codex features that need the Ubuntu indexer fail until restart; does **not** by itself tear down `vmmemWSL` if Docker or another client still holds a distro |
| **P4 — WSL idle shutdown** | When no Docker/Codex/other WSL client is needed: `wsl --shutdown` | Tears down Ubuntu + docker-desktop distros and `vmmemWSL` | **Breaks** any live Docker WSL backend and any in-distro MCP until restart; never use mid-task if containers or WSL MCP are active |
| **P5 — Cowork VM idle policy** | Quit Claude Cowork/Desktop when the VM is not needed; re-check `hcsdiag list` for Owner=`cowork-vm-*` | Targets plain `vmmem` (~multi-GB private in the capture) without touching Owner=`WSL` | Create/stop procedure for a leftover Running cowork VM is still an open question; wrong kill path can disrupt Cowork artifacts |
| **P6 — Process-creation audit** | Turn on 4688 or Sysmon for wsl/vmwp/Docker/Claude/Codex | No direct RAM win; closes open questions (1)(2)(4)(6) | Audit volume, privacy review, and storage for event logs |
| **P7 — `.wslconfig` memory cap** | Set `memory=` under `[wsl2]` | Caps WSL utility VM commit **only after** measured before/after on this host | **Blocked here until measured.** Risk: OOM inside distros, Docker backend instability, false “fix” that leaves cowork `vmmem` untouched |

### Measurement gate for P7 (and any memory cap)

Before any `.wslconfig` memory write:

1. Record `wsl -l -v`, `hcsdiag list`, and private working set for `vmmemWSL` / plain `vmmem` / `com.docker.backend`.
2. Name which component the cap is meant to bound (Owner=`WSL` only — cowork is outside `.wslconfig`).
3. Apply cap; reboot or `wsl --shutdown` + re-start workload as required for the setting to apply.
4. Re-record the same counters under the same workload.
5. Commit the before/after note next to the policy decision (issue comment or evidence pack). Without that note, leave `.wslconfig` without a memory cap.

## Quick identification commands

Read-only checks agents and operators use on Windows:

```text
wsl -l -v
hcsdiag list
Get-CimInstance Win32_Service -Filter "Name='WSLService'"
Get-ItemProperty HKCU:\Software\Microsoft\Windows\CurrentVersion\Run
Get-CimInstance Win32_Process -Filter "Name='wsl.exe'" | Select ProcessId, ParentProcessId, CommandLine
```

Resolve each `wsl.exe` ParentProcessId to an image name before blaming an agent binary. A missing parent is **unknown**, not proof of a named starter.

## Related

- Issue: [jl-cmd/claude-dev-env#256](https://github.com/jl-cmd/claude-dev-env/issues/256) (child of epic #252)
- Local forensic write-up: `results/05-wsl-who-started.md` under the host evidence pack path named in the issue body
