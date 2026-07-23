# scripts/tests

pytest suite for the Python scripts and Pester suite for the PowerShell scripts in `scripts/`.

## Test files

| File | Covers |
|---|---|
| `test_setup_project_paths.py` | `setup_project_paths.py` — discovery, filtering, and `project-paths.json` writing |
| `test_setup_project_paths_config.py` | Configuration constants used by `setup_project_paths.py` |
| `test_sweep_empty_dirs.py` | `sweep_empty_dirs.py` — age check, one-shot mode, and continuous-watch behavior |
| `test_sync_to_cursor.py` | `sync_to_cursor/` package — mapping, hashing, manifest, and path resolution |

## PowerShell test files

| File | Covers |
|---|---|
| `Get-SessionAccount.Tests.ps1` | `Get-SessionAccount.ps1` — noise filtering, profile-storage email recovery, CLI-vs-desktop account resolution, and output formatting |
| `Show-Asset.Tests.ps1` | `Show-Asset.ps1` — parent-death exit within 5s after a live parent dies, no early exit when parent is already dead at start, max-lifetime auto-exit (Escape dismissal is interactive-only, verified manually) |

## Running

Python scripts (pytest):

```bash
python -m pytest packages/claude-dev-env/scripts/tests/
```

PowerShell scripts (Pester 5+, `*.Tests.ps1`):

```powershell
Invoke-Pester -Path packages/claude-dev-env/scripts/tests/
```
