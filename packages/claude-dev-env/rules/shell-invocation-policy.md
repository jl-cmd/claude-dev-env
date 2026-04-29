# Shell Invocation Policy (pwsh-only)

**When this applies:** Every shell command issued through the `Bash` tool on Windows.

## What to use

### Pattern A — Run a `.ps1` script with named arguments

```
pwsh -NoProfile -File 'Y:\absolute\path\to\Build-Skyline.ps1' -RunTests -Tag staging
```

Use this when a `.ps1` script accepts named parameters. The `-File` form exposes the script path as a flat token, so `permissions.allow` rules of the form `Bash(pwsh -NoProfile -File *)` match the invocation directly.

### Pattern B — Run an inline expression

```
pwsh -NoProfile -Command "Get-Date -Format o"
```

Use this for one or two lines of work that does not need a script file. Quote the entire `-Command` argument with double quotes; use single quotes inside for embedded strings.

### Pattern C — Multi-line inline script with a here-string

```
pwsh -NoProfile -Command @'
$projects = Get-ChildItem -Path 'Y:\Projects\LLM Plugins' -Directory
$projects | Where-Object Name -Like 'claude*' | Select-Object FullName
'@
```

Use this for multi-line logic without a separate `.ps1` file. The `@'...'@` form is literal — variables and backticks inside are not expanded.

### Pattern D — The built-in `PowerShell` tool

Use the `PowerShell` tool directly when the entire workflow is PowerShell and does not pipe through external `Bash`-tool-native commands. The built-in tool already runs PowerShell 7+ from `C:\Program Files\PowerShell\7\pwsh.exe`. It supports `run_in_background` for long-running tasks, which `Bash` invocations of `pwsh` do not.

## Migration mapping (replace left with right)

| Existing pattern | Replacement |
|---|---|
| `powershell -Command "X"` | `pwsh -NoProfile -Command "X"` |
| `powershell.exe -Command "X"` | `pwsh -NoProfile -Command "X"` |
| `powershell -File path.ps1` | `pwsh -NoProfile -File 'path.ps1'` |
| `powershell.exe -File path.ps1` | `pwsh -NoProfile -File 'path.ps1'` |
| `powershell -Command "& 'path.ps1' -A v"` | `pwsh -NoProfile -File 'path.ps1' -A v` |
| `bash -c "X"` | `pwsh -NoProfile -Command "X"` |
| `cmd /c X` | `pwsh -NoProfile -Command "X"` |
| `cmd.exe /c X` | `pwsh -NoProfile -Command "X"` |
| `Bash(powershell:*)` (settings.json) | `Bash(pwsh:*)` |
| `Bash(powershell.exe:*)` (settings.json) | `Bash(pwsh:*)` |

## Common operations in pwsh

| Task | pwsh syntax |
|---|---|
| List directory names | `Get-ChildItem -Path 'X' -Directory -Name` |
| Read a whole file | `Get-Content -Path 'X' -Raw` |
| Write file (UTF-8 no BOM) | `[IO.File]::WriteAllText('X', $content, [Text.UTF8Encoding]::new($false))` |
| Test a path | `Test-Path 'X'` |
| Remove a directory | `Remove-Item -Path 'X' -Recurse -Force` |
| Activate a venv | `& 'Y:\path\.venv\Scripts\Activate.ps1'` |
| Run venv-Python | `& 'Y:\path\.venv\Scripts\python.exe' script.py` |
| Set env var (current process) | `$env:NAME = 'value'` |
| Pipe to ripgrep | `Get-ChildItem | Select-String -Pattern 'X'` |
| First match in a stream | `Select-Object -First 1` |

The `&` call operator is appropriate for invoking an executable at a path — for example, `& '<venv>\Scripts\python.exe' script.py`. The forbidden form is wrapping a script path inside `pwsh -Command "& 'X' -A v"`, where the call operator is inside a `-Command` payload and breaks `permissions.allow` matching. Use `pwsh -File 'X' -A v` instead for that case.

## External binaries usable from pwsh

Invoke these directly without wrapping:

- `git` — `git status`, `git log --oneline -10`, `git -C 'path' status`
- `gh` — `gh pr create`, `gh issue list`
- `python`, `pip` (via venv path: `& '.venv\Scripts\python.exe'`)
- `node`, `npm`, `npx`
- `rg` (ripgrep), `fd`, `es.exe` (Everything search)
- `pytest`, `mypy`, `pyright` (via venv)

## Verification

To confirm pwsh is correctly installed and routed:

```
pwsh -NoProfile -Command "$PSVersionTable.PSVersion.ToString()"
```

Expected output: `7.x.x.x` or higher. The verified install at the time of writing this rule is `7.5.5.0` at `C:\Program Files\PowerShell\7\pwsh.exe`.

## Permission allowlist (settings.json `permissions.allow`)

These entries pre-approve canonical pwsh invocations:

```
Bash(pwsh -NoProfile -File *)
Bash(pwsh -File *)
Bash(pwsh -NoProfile -Command *)
Bash(pwsh -Command *)
Bash(pwsh:*)
PowerShell
```

The `PowerShell` entry auto-approves the built-in tool.

## Permission denylist (settings.json `permissions.deny`)

These entries block legacy shells:

```
Bash(powershell *)
Bash(powershell.exe *)
Bash(powershell:*)
Bash(powershell.exe:*)
Bash(bash -c *)
Bash(bash --login *)
Bash(bash --rcfile *)
Bash(bash --init-file *)
Bash(cmd /c *)
Bash(cmd.exe /c *)
```

## Migration scripts

Two scripts ship with this rule, located at `packages/claude-dev-env/scripts/`:

- `Audit-ShellPolicy.ps1` — scans `settings*.json` files under the configured project roots and prints one summary line: `POLICY: OK` or `POLICY: VIOLATIONS=<count> IN=<n> FILES`. Exit code 0 when clean, 1 when violations remain. Use this as a check before merging.
- `Migrate-ShellPolicy.ps1` — applies the migration mapping to `settings*.json` files in place. Defaults to dry-run; pass `-Apply` to write changes. Prints one summary line: `MIGRATED: <count> rules IN=<n> FILES` or `DRY RUN: would migrate <count> rules IN=<n> FILES`.

Run order: audit → migrate (dry run) → migrate (apply) → audit.

## Enforcement layers

1. **`permissions.allow`** pre-approves the canonical patterns so Claude never gets a prompt for them.
2. **`permissions.deny`** blocks the legacy patterns at the permission layer.
3. **`pwsh_enforcer.py`** PreToolUse hook catches edge cases that wildcard syntax misses (compound commands, process wrappers, alternate spellings). Source: `packages/claude-dev-env/hooks/blocking/pwsh_enforcer.py`.
4. **Migration scripts** keep existing `settings.local.json` files in compliance.

## Precedent

This rule mirrors the convention from [ProteoWizard/pwiz-ai](https://github.com/ProteoWizard/pwiz-ai) `CLAUDE.md`:

> "Always use `pwsh` (PowerShell 7), never `powershell` (5.1). The Bash tool uses Git Bash, which has limited Windows tool access. Route commands through PowerShell when needed."
> "Never use the `&` call operator — it breaks permissions matching. Use `-File` instead, which supports arguments directly."
